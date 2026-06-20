from pipeline.batch import run_batch
from core import new_moons
from geometry import central_path
from infrastructure.ephemeris import get_context
from geometry.eclipse_band import (
    build_totality_limits,
)

def get_real_eclipse(target_date: str):
    eph, ts = get_context()

    year = int(target_date[:4])

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

        "centralPath": [
            {
                "lat": lat,
                "lon": lon,
                "time": time.utc_strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
            }
            for lat, lon, time in path
        ]
    }