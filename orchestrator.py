import argparse
import sys
from datetime import date
from multiprocessing import Pool, cpu_count

from core import (
    new_moons,
    classify_eclipse,
    eclipse_title,
    compute_local_circumstances,
)
from core.magnitude import compute_surface_max_magnitude
from geometry import (
    central_path,
    eclipse_obscuration_map,
    eclipse_bounding_box,
    export_eclipse_geojson,
    export_eclipse_kml,
)
from infrastructure.config import OUTPUT_DIR, EPHEMERIS_PATH
from infrastructure.ephemeris import get_context
from pipeline.batch import run_batch
from plotting import plot_obscuration_map
from plotting import plot_local_sky_view
from utils.timer import Timer

DEFAULT_START_DATE = date(2027, 1, 1)
DEFAULT_END_DATE = date(2027, 12, 31)


def configure_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Use o formato AAAA-MM-DD.") from exc


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
    parser.add_argument(
        "--lat",
        type=float,
        default=None,
        help="Latitude do local para circunstâncias locais.",
    )
    parser.add_argument(
        "--lon",
        type=float,
        default=None,
        help="Longitude do local para circunstâncias locais.",
    )
    parser.add_argument(
        "--eclipse-date",
        type=parse_date,
        default=None,
        help="Data do eclipse a analisar no formato AAAA-MM-DD.",
    )
    parser.add_argument(
        "--export-geojson",
        action="store_true",
        help="Exporta o eclipse selecionado para GeoJSON.",
    )
    parser.add_argument(
        "--export-kml",
        action="store_true",
        help="Exporta o eclipse selecionado para KML.",
    )

    args = parser.parse_args()

    if args.start_date > args.end_date:
        parser.error("A data inicial deve ser menor ou igual a data final.")

    if (args.lat is None) ^ (args.lon is None):
        parser.error("Informe --lat e --lon juntos.")

    if args.eclipse_date is not None and (args.lat is None or args.lon is None):
        parser.error("Use --eclipse-date junto com --lat e --lon.")

    return args


def find_eclipse_by_date(eclipses, target_date):
    if target_date is None:
        return eclipses[0] if eclipses else None

    for eclipse in eclipses:
        if eclipse["MAX"].utc_datetime().date() == target_date:
            return eclipse

    return None


def print_local_circumstances(eph, ts, eclipse, lat, lon):
    local = compute_local_circumstances(
        eph=eph,
        ts=ts,
        t_max=eclipse["MAX"],
        lat=lat,
        lon=lon,
    )

    print(f"\nCircunstancias locais para lat={lat:.4f}, lon={lon:.4f}")
    print(f"  C1: {local['C1']}")
    print(f"  C2: {local['C2']}")
    print(f"  MAX: {local['MAX']}")
    print(f"  C3: {local['C3']}")
    print(f"  C4: {local['C4']}")
    print(f"  Separacao minima: {local['min_separation_deg']:.4f} deg")
    print(f"  Obscuracao maxima: {local['max_obscuration']:.4f}")
    print(
        f"  Sol alt/az: {local['sun_alt_deg']:.2f} / {local['sun_az_deg']:.2f} deg"
    )
    print(
        f"  Lua alt/az: {local['moon_alt_deg']:.2f} / {local['moon_az_deg']:.2f} deg"
    )


def run_simulation(start_date: date, end_date: date):
    print("\nIniciando simulacao...\n")

    eph, ts = get_context()
    print("Buscando luas novas...")

    t_start = ts.utc(start_date.year, start_date.month, start_date.day)
    t_end = ts.utc(end_date.year, end_date.month, end_date.day)

    moons = new_moons(eph, t_start, t_end)
    print(f"{len(moons)} luas novas encontradas.\n")

    print("Processando possiveis eclipses...\n")

    with Timer("Batch (deteccao)"):
        eclipses = run_batch(moons)

    if not eclipses:
        print("Nenhum eclipse encontrado.")
        return []

    print("Eclipses encontrados:\n")
    for e in eclipses:
        print(e["date"])

    print("\nProcessando dados fisicos...\n")

    with Pool(processes=max(1, cpu_count() - 1)) as pool:
        for e in eclipses:
            print(f"Processando {e['date']}...")

            with Timer("Bounding box"):
                lat_min, lat_max, lon_min, lon_max = eclipse_bounding_box(
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

            with Timer("Mapa de obscuracao"):
                points = eclipse_obscuration_map(
                    eph_path=str(EPHEMERIS_PATH),
                    t_start=e["C1"],
                    t_end=e["C4"],
                    lat_step=0.25,
                    lon_step=0.25,
                    time_chunks=20,
                    lat_range=(lat_min, lat_max),
                    lon_range=(lon_min, lon_max),
                    pool=pool,
                    eph=eph,
                    ts=ts,
                )

                if not points:
                    print("Nenhum ponto de sombra encontrado.")
                    continue

            with Timer("Linha central"):
                if e["C2"] is not None and e["C3"] is not None:
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
                mid = len(e["central_path"]) // 2
                lat_m, lon_m, _ = e["central_path"][mid]
            else:
                lat_m, lon_m, _ = max(points, key=lambda p: p[2])

            max_point = (lat_m, lon_m, None)

            with Timer("Magnitude"):
                e["magnitude"] = compute_surface_max_magnitude(
                    eph,
                    ts,
                    e["MAX"],
                    lat_m,
                    lon_m,
                )

            max_obsc = max(p[2] for p in points)
            e["type"] = classify_eclipse(
                eph=eph,
                central_times=[e["MAX"]],
                max_obscuration=max_obsc,
            )

            output_file = OUTPUT_DIR / f"Eclipse_Solar_{e['type']}_{e['date']}.png"

            with Timer("Plot"):
                plot_obscuration_map(
                    points=points,
                    title=eclipse_title(e["type"], e["date"]),
                    output=str(output_file),
                    central_path=e["central_path"] if e["central_path"] else None,
                    max_point=max_point,
                    eclipse_type=e["type"],
                    eclipse_data=e,
                )

    print("\nSimulacao finalizada.\n")
    return eclipses


def run_local_report(start_date, end_date, eclipse_date, lat, lon, export_geojson=False, export_kml=False):
    eph, ts = get_context()
    t_start = ts.utc(start_date.year, start_date.month, start_date.day)
    t_end = ts.utc(end_date.year, end_date.month, end_date.day)

    moons = new_moons(eph, t_start, t_end)
    eclipses = run_batch(moons)
    eclipse = find_eclipse_by_date(eclipses, eclipse_date)

    if eclipse is None:
        print("Nenhum eclipse encontrado para a data informada.")
        return None

    print(f"Eclipse selecionado: {eclipse['date']}")

    with Pool(processes=max(1, cpu_count() - 1)) as pool:
        lat_min, lat_max, lon_min, lon_max = eclipse_bounding_box(
            eph_path=str(EPHEMERIS_PATH),
            t_start=eclipse["C1"],
            t_end=eclipse["C4"],
            coarse_step=5.0,
            threshold=0.001,
            time_chunks=4,
            pool=pool,
            eph=eph,
            ts=ts,
        )

        points = eclipse_obscuration_map(
            eph_path=str(EPHEMERIS_PATH),
            t_start=eclipse["C1"],
            t_end=eclipse["C4"],
            lat_step=0.25,
            lon_step=0.25,
            time_chunks=20,
            lat_range=(lat_min, lat_max),
            lon_range=(lon_min, lon_max),
            pool=pool,
            eph=eph,
            ts=ts,
        )

    local = compute_local_circumstances(
        eph=eph,
        ts=ts,
        t_max=eclipse["MAX"],
        lat=lat,
        lon=lon,
    )

    print_local_circumstances(eph, ts, eclipse, lat, lon)
    sky_path = plot_local_sky_view(
        local=local,
        eclipse_date=eclipse["date"],
    )
    print(f"Visualizacao local salva em: {sky_path}")

    if export_geojson:
        geojson_path = export_eclipse_geojson(eclipse, local=local, points=points)
        print(f"GeoJSON salvo em: {geojson_path}")

    if export_kml:
        kml_path = export_eclipse_kml(eclipse, local=local, points=points)
        print(f"KML salvo em: {kml_path}")

    return eclipse


if __name__ == "__main__":
    configure_console()
    args = parse_args()

    if args.lat is not None and args.lon is not None:
        run_local_report(
            args.start_date,
            args.end_date,
            args.eclipse_date,
            args.lat,
            args.lon,
            export_geojson=args.export_geojson,
            export_kml=args.export_kml,
        )
    else:
        run_simulation(
            args.start_date,
            args.end_date,
        )
