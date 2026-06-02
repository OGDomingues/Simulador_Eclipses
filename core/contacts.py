import numpy as np
from .constants import R_SUN_KM, R_MOON_KM, R_EARTH_KM


def _find_contact(times, sep, limit):
    for i in range(len(times) - 1):

        f1 = sep[i] - limit[i]
        f2 = sep[i + 1] - limit[i + 1]

        if f1 == 0:
            return times[i]

        if f1 * f2 < 0:

            frac = abs(f1) / (
                abs(f1) + abs(f2)
            )

            return (
                times[i]
                +
                (times[i + 1] - times[i]) * frac
            )

    return None


def compute_contacts(eph, ts, t_max):

    earth = eph["earth"]
    sun = eph["sun"]
    moon = eph["moon"]

    t0 = t_max.utc_datetime()

    minutes = np.arange(
        -240,
        240,
        0.5
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

    partial = (
        sun_r
        + moon_r
        + earth_r
    )

    total = (
        np.abs(sun_r - moon_r)
        + earth_r
    )

    C1 = _find_contact(
        times,
        sep,
        partial
    )

    C4 = _find_contact(
        times[::-1],
        sep[::-1],
        partial[::-1]
    )

    C2 = _find_contact(
        times,
        sep,
        total
    )

    C3 = _find_contact(
        times[::-1],
        sep[::-1],
        total[::-1]
    )

    return (
        C1,
        C2,
        t_max,
        C3,
        C4
    )