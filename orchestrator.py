import argparse
import sys
from datetime import date
from multiprocessing import Pool, cpu_count

from core import (
    new_moons,
    classify_eclipse,
    eclipse_title,
)
from core.magnitude import compute_surface_max_magnitude
from geometry import (
    central_path,
    eclipse_obscuration_map,
    eclipse_bounding_box,
)
from infrastructure.config import OUTPUT_DIR, EPHEMERIS_PATH
from infrastructure.ephemeris import get_context
from pipeline.batch import run_batch
from plotting import plot_obscuration_map
from utils.timer import Timer

DEFAULT_START_DATE = date(2027, 1, 1)
DEFAULT_END_DATE = date(2027, 12, 31)


def configure_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(
                encoding="utf-8",
                errors="replace"
            )


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Use o formato AAAA-MM-DD."
        ) from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Executa a simulacao de eclipses solares."
    )
    parser.add_argument(
        "start_date",
        nargs="?",
        type=parse_date,
        default=DEFAULT_START_DATE,
        help=(
            "Data inicial no formato AAAA-MM-DD "
            f"(padrao: {DEFAULT_START_DATE.isoformat()})."
        ),
    )
    parser.add_argument(
        "end_date",
        nargs="?",
        type=parse_date,
        default=DEFAULT_END_DATE,
        help=(
            "Data final no formato AAAA-MM-DD "
            f"(padrao: {DEFAULT_END_DATE.isoformat()})."
        ),
    )

    args = parser.parse_args()

    if args.start_date > args.end_date:
        parser.error("A data inicial deve ser menor ou igual a data final.")

    return args


def run_simulation(start_date: date, end_date: date):
    print("\n🔭 Iniciando simulação...\n")

    eph, ts = get_context()
    print("🔎 Buscando luas novas...")

    t_start = ts.utc(
        start_date.year,
        start_date.month,
        start_date.day
    )

    t_end = ts.utc(
        end_date.year,
        end_date.month,
        end_date.day
    )

    moons = new_moons(
        eph,
        t_start,
        t_end
    )

    print(f"🌓 {len(moons)} luas novas encontradas.\n")

    print("⚙️ Processando possíveis eclipses...\n")

    with Timer("Batch (detecção)"):
        eclipses = run_batch(moons)

    if not eclipses:
        print("❌ Nenhum eclipse encontrado.")
        return []

    print("✔ Eclipses encontrados:\n")

    for e in eclipses:
        print(e["date"])

    print("\n")
    print("🌍 Processando dados físicos...\n")

    with Pool(
            processes=max(1, cpu_count() - 1)
    ) as pool:

        for e in eclipses:

            print(f"Processando {e['date']}...")
            with Timer("Bounding box"):

                lat_min, lat_max, lon_min, lon_max = (
                    eclipse_bounding_box(
                        eph_path=str(EPHEMERIS_PATH),
                        t_start=e["C1"],
                        t_end=e["C4"],
                        coarse_step=5.0,
                        threshold=0.001,
                        time_chunks=4,
                        pool=pool,
                        eph=eph,
                        ts=ts,
                    )
                )
            with Timer("Mapa obscuração"):

                points = eclipse_obscuration_map(
                    eph_path=str(EPHEMERIS_PATH),
                    t_start=e["C1"],
                    t_end=e["C4"],
                    lat_step=0.25,
                    lon_step=0.25,
                    time_chunks=20,
                    lat_range=(
                        lat_min,
                        lat_max
                    ),
                    lon_range=(
                        lon_min,
                        lon_max
                    ),
                    pool=pool,
                    eph=eph,
                    ts=ts,
                )

                if not points:
                    print(
                        "⚠️ Nenhum ponto de sombra encontrado."
                    )
                    continue
            with Timer("Linha central"):

                if (
                        e["C2"] is not None
                        and
                        e["C3"] is not None
                ):

                    e["central_path"] = central_path(
                        eph=eph,
                        ts=ts,
                        t_start=e["C2"],
                        t_end=e["C3"],
                        step_minutes=0.1,
                    )

                else:

                    e["central_path"] = []
            if e["central_path"]:

                mid = (
                        len(e["central_path"])
                        // 2
                )

                lat_m, lon_m, _ = (
                    e["central_path"][mid]
                )

            else:

                lat_m, lon_m, _ = max(
                    points,
                    key=lambda p: p[2]
                )

            max_point = (
                lat_m,
                lon_m,
                None
            )
            with Timer("Magnitude"):

                e["magnitude"] = (
                    compute_surface_max_magnitude(
                        eph,
                        ts,
                        e["MAX"],
                        lat_m,
                        lon_m,
                    )
                )
            max_obsc = max(
                p[2]
                for p in points
            )

            e["type"] = classify_eclipse(
                eph=eph,
                central_times=[e["MAX"]],
                max_obscuration=max_obsc,
            )
            output_file = (
                    OUTPUT_DIR
                    /
                    f"Eclipse_Solar_{e['type']}_{e['date']}.png"
            )

            with Timer("Plot"):

                plot_obscuration_map(
                    points=points,
                    title=eclipse_title(
                        e["type"],
                        e["date"]
                    ),
                    output=str(output_file),
                    central_path=(
                        e["central_path"]
                        if e["central_path"]
                        else None
                    ),
                    max_point=max_point,
                    eclipse_type=e["type"],
                    eclipse_data=e,
                )

    print("\n✅ Simulação finalizada.\n")

    return eclipses


if __name__ == "__main__":
    configure_console()
    args = parse_args()
    run_simulation(
        args.start_date,
        args.end_date
    )
