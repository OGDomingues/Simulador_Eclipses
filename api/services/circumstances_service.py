from core import (
    new_moons,
    compute_local_circumstances,
)

from infrastructure.ephemeris import (
    get_context,
)

from pipeline.batch import run_batch


def serialize_time(t):
    if t is None:
        return None

    return t.utc_strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )


def get_circumstances(
    eclipse_date: str,
    lat: float,
    lon: float,
):
    eph, ts = get_context()

    year = int(eclipse_date[:4])

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
        current_date = (
            eclipse["MAX"]
            .utc_datetime()
            .date()
            .isoformat()
        )

        if current_date == eclipse_date:
            selected = eclipse
            break

    if selected is None:
        return None

    local = compute_local_circumstances(
        eph=eph,
        ts=ts,
        t_max=selected["MAX"],
        lat=lat,
        lon=lon,
    )

    return {
        "obscuration":
            local["max_obscuration"],

        "c1":
            serialize_time(local["C1"]),

        "c2":
            serialize_time(local["C2"]),

        "max":
            serialize_time(local["MAX"]),

        "c3":
            serialize_time(local["C3"]),

        "c4":
            serialize_time(local["C4"]),

        "sun_alt":
            local["sun_alt_deg"],

        "sun_az":
            local["sun_az_deg"],
    }