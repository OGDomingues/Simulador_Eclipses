import numpy as np

from .constants import R_SUN_KM, R_MOON_KM, R_EARTH_KM


def is_possible_eclipse(eph, ts, t_nm):
    earth = eph["earth"]
    sun = eph["sun"]
    moon = eph["moon"]

    t0 = t_nm.utc_datetime()

    minutes = np.arange(
        -360,
        360,
        10.0
    )

    times = ts.utc(
        t0.year,
        t0.month,
        t0.day,
        t0.hour,
        t0.minute,
        t0.second + minutes * 60.0
    )

    ast = earth.at(times)

    ast_s = ast.observe(sun).apparent()
    ast_m = ast.observe(moon).apparent()

    sep = ast_s.separation_from(
        ast_m
    ).degrees

    d_s = ast_s.distance().km
    d_m = ast_m.distance().km

    sun_r = np.degrees(
        np.arcsin(R_SUN_KM / d_s)
    )

    moon_r = np.degrees(
        np.arcsin(R_MOON_KM / d_m)
    )

    earth_r = np.degrees(
        np.arcsin(R_EARTH_KM / d_m)
    )

    limit = (
            sun_r
            + moon_r
            + earth_r
            + 0.2
    )

    return np.any(sep < limit)
