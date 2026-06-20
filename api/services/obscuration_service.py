from infrastructure.ephemeris import (
    get_context,
)

from infrastructure.config import (
    EPHEMERIS_PATH,
)

from pipeline.batch import (
    run_batch,
)

from core import (
    new_moons,
)

from geometry.surface_map import (
    eclipse_obscuration_map,
)


def get_obscuration_map(
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
        return None

    points = (
        eclipse_obscuration_map(
            eph_path=str(
                EPHEMERIS_PATH
            ),

            t_start=selected["C1"],
            t_end=selected["C4"],

            lat_step=8.0,
            lon_step=8.0,

            time_chunks=40,
            processes=8,
        )
    )

    return {
        "count": len(points),

        "points": [
            {
                "lat": lat,
                "lon": lon,
                "obscuration": obsc,
            }
            for lat, lon, obsc in points
        ],
    }