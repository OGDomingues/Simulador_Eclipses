from infrastructure.ephemeris import (
    get_context,
)

from pipeline.batch import (
    run_batch,
)

from core import (
    new_moons,
)

from geometry.central_path import (
    central_path,
)


def get_central_path_data(
    target_date: str,
):
    eph, ts = get_context()

    year = int(
        target_date[:4]
    )

    t_start = ts.utc(
        year,
        1,
        1,
    )

    t_end = ts.utc(
        year,
        12,
        31,
    )

    moons = new_moons(
        eph,
        t_start,
        t_end,
    )

    eclipses = run_batch(
        moons
    )

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
        return {
            "centralPath": []
        }

    path = central_path(
        eph,
        ts,
        selected["C1"],
        selected["C4"],
    )

    return {
        "centralPath": [
            {
                "lat": lat,
                "lon": lon,
                "time": t.utc_iso(),
            }
            for lat, lon, t in path
        ]
    }