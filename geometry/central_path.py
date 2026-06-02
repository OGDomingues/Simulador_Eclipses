import numpy as np
from skyfield.api import wgs84
from skyfield.positionlib import ICRF

from core.constants import AU_KM, R_EARTH_KM


def central_path(
        eph,
        ts,
        t_start,
        t_end,
        step_minutes=1,
):
    earth = eph["earth"]
    sun = eph["sun"]
    moon = eph["moon"]

    total_seconds = (t_end.tt - t_start.tt) * 86400.0

    steps = int(
        total_seconds //
        (step_minutes * 60)
    ) + 1

    times = ts.tt_jd(
        np.linspace(
            t_start.tt,
            t_end.tt,
            steps
        )
    )

    ast = earth.at(times)

    sun_vec = np.asarray(
        ast.observe(sun).position.km
    ).T

    moon_vec = np.asarray(
        ast.observe(moon).position.km
    ).T

    path = []

    for i in range(len(times)):

        axis = moon_vec[i] - sun_vec[i]

        norm = np.linalg.norm(axis)

        if norm == 0:
            continue

        axis /= norm

        m = moon_vec[i]

        a = 1.0
        b = 2 * np.dot(m, axis)
        c = np.dot(m, m) - R_EARTH_KM ** 2

        disc = b * b - 4 * a * c

        if disc <= 0:
            continue

        sqrt_disc = np.sqrt(disc)

        lam1 = (-b - sqrt_disc) / (2 * a)
        lam2 = (-b + sqrt_disc) / (2 * a)

        lam = lam1 if abs(lam1) < abs(lam2) else lam2

        hit = m + lam * axis

        pos = ICRF(
            position_au=hit / AU_KM,
            velocity_au_per_d=None,
            t=times[i],
            center=399,
            target=None
        )

        lat, lon = wgs84.latlon_of(pos)

        path.append(
            (
                lat.degrees,
                lon.degrees,
                times[i]
            )
        )

    return path
