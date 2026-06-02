import numpy as np
from skyfield.api import wgs84

from core.constants import R_SUN_KM, R_MOON_KM


def compute_surface_max_magnitude(eph, ts, t_center, lat, lon):
    earth = eph["earth"]
    sun = eph["sun"]
    moon = eph["moon"]

    observer = earth + wgs84.latlon(lat, lon)

    t0 = t_center.utc_datetime()
    offsets = np.arange(-180, 180, 3)

    times = ts.utc(
        t0.year,
        t0.month,
        t0.day,
        t0.hour,
        t0.minute,
        t0.second + offsets
    )

    ast = observer.at(times)

    sun_ast = ast.observe(sun).apparent()
    moon_ast = ast.observe(moon).apparent()

    sep = sun_ast.separation_from(moon_ast).radians
    idx = np.argmin(sep)

    delta = sep[idx]

    rs = np.arcsin(R_SUN_KM / sun_ast.distance().km[idx])
    rm = np.arcsin(R_MOON_KM / moon_ast.distance().km[idx])

    if delta >= rs + rm:
        return 0.0

    if delta <= abs(rs - rm):
        return rm / rs

    return (rs + rm - delta) / (2 * rs)
