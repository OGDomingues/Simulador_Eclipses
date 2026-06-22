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

def get_geojson(
    target_date: str,
):
    from geometry.export import (
        _band_features,
        _limit_features,
    )

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
            "type": "FeatureCollection",
            "features": [],
        }

    points = eclipse_obscuration_map(
        eph_path=str(
            EPHEMERIS_PATH
        ),
        t_start=selected["C1"],
        t_end=selected["C4"],
        lat_step=0.5,
        lon_step=0.5,
        time_chunks=32,
        processes=15,
    )

    features = []

    features.extend(
        _band_features(points)
    )

    features.extend(
        _limit_features(points)
    )

    return {
        "type": "FeatureCollection",
        "properties": {
            "date": target_date,
            "type": selected.get(
                "type"
            ),
        },
        "features": features,
    }
