from pipeline.batch import run_batch
from core import new_moons
from geometry.central_path import central_path
from infrastructure.ephemeris import get_context
from geometry.eclipse_band import (
    build_totality_limits,
)

def get_real_eclipse(target_date: str):
    try:
        year = int(target_date[:4])
    except ValueError:
        return None

    eph, ts = get_context()

    t_start = ts.utc(year, 1, 1)
    t_end = ts.utc(year, 12, 31)

    moons = new_moons(
        eph,
        t_start,
        t_end,
    )

    eclipses = run_batch(moons)

    selected = None

    for eclipse in eclipses:
        eclipse_date = (
            eclipse["MAX"]
            .utc_datetime()
            .date()
            .isoformat()
        )

        if eclipse_date == target_date:
            selected = eclipse
            break

    if selected is None:
        return None

    if (
        selected["C2"] is None
        or
        selected["C3"] is None
    ):
        return None

    path = central_path(
        eph=eph,
        ts=ts,
        t_start=selected["C1"],
        t_end=selected["C4"],
        step_minutes=0.5,
    )

    best_index = None
    best_point = None

    if path:
        best_index, best_point = min(
            enumerate(path),
            key=lambda item: abs(
                item[1][2].tt - selected["MAX"].tt
            ),
        )

    central_path_data = [
        {
            "lat": lat,
            "lon": lon,
            "time": time.utc_strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
        }
        for lat, lon, time in path
    ]

    # print(
    #     "Central path:",
    #     len(path)
    # )
    #
    # north_limit, south_limit = (
    #     build_totality_limits(
    #         eph,
    #         ts,
    #         path,
    #     )
    # )
    return {
        "date": target_date,

        "centralPath": central_path_data,

        "bestObservation": (
            {
                "lat": best_point[0],
                "lon": best_point[1],
                "time": best_point[2].utc_strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
                "index": best_index,
            }
            if best_point is not None
            else None
        ),
    }
