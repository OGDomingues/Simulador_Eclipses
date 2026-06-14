import numpy as np
from skyfield.api import wgs84
from datetime import timedelta

from .contacts import _find_contact
from .constants import R_SUN_KM, R_MOON_KM


def compute_local_circumstances(eph, ts, t_max, lat, lon):
    earth = eph["earth"]
    sun = eph["sun"]
    moon = eph["moon"]

    observer = earth + wgs84.latlon(lat, lon)

    t0 = t_max.utc_datetime()
    minutes = np.arange(-240, 240, 0.5)

    times = ts.utc(
        t0.year,
        t0.month,
        t0.day,
        t0.hour,
        t0.minute,
        t0.second + minutes * 60.0
    )

    ast = observer.at(times)
    ast_s = ast.observe(sun).apparent()
    ast_m = ast.observe(moon).apparent()

    sep = ast_s.separation_from(ast_m).degrees
    d_s = ast_s.distance().km
    d_m = ast_m.distance().km

    sun_r = np.degrees(np.arcsin(R_SUN_KM / d_s))
    moon_r = np.degrees(np.arcsin(R_MOON_KM / d_m))
    limit = sun_r + moon_r
    total_limit = np.abs(sun_r - moon_r)

    idx = int(np.argmin(sep))
    t_local_max = times[idx]
    min_sep = float(sep[idx])
    max_obsc = 0.0
    if min_sep < limit[idx]:
        delta = np.radians(min_sep)
        rs = np.radians(sun_r[idx])
        rm = np.radians(moon_r[idx])

        if delta <= abs(rs - rm):
            max_obsc = float(min(1.0, (rm / rs) ** 2))
        else:
            part1 = rm**2 * np.arccos(
                (delta**2 + rm**2 - rs**2) / (2 * delta * rm)
            )
            part2 = rs**2 * np.arccos(
                (delta**2 + rs**2 - rm**2) / (2 * delta * rs)
            )
            part3 = 0.5 * np.sqrt(
                (-delta + rm + rs)
                * (delta + rm - rs)
                * (delta - rm + rs)
                * (delta + rm + rs)
            )
            max_obsc = float(
                (part1 + part2 - part3) / (np.pi * rs**2)
            )

    ast_local_max = observer.at(t_local_max)
    alt_s, az_s, _ = ast_local_max.observe(sun).apparent().altaz()
    alt_m, az_m, _ = ast_local_max.observe(moon).apparent().altaz()

    utc_offset_hours = int(round(lon / 15.0))
    utc_offset_seconds = utc_offset_hours * 3600

    C1 = _find_contact(times, sep, limit)
    C4 = _find_contact(times[::-1], sep[::-1], limit[::-1])
    C2 = _find_contact(times, sep, total_limit)
    C3 = _find_contact(times[::-1], sep[::-1], total_limit[::-1])

    def local_str(t):
        if t is None:
            return "--"
        local_dt = t.utc_datetime() + timedelta(seconds=utc_offset_seconds)
        return local_dt.strftime("%H:%M:%S")

    return {
        "location": {
            "lat": lat,
            "lon": lon,
        },
        "utc_offset_hours": utc_offset_hours,
        "C1": C1,
        "C2": C2,
        "MAX": t_local_max,
        "C3": C3,
        "C4": C4,
        "C1_local": local_str(C1),
        "C2_local": local_str(C2),
        "MAX_local": local_str(t_local_max),
        "C3_local": local_str(C3),
        "C4_local": local_str(C4),
        "min_separation_deg": min_sep,
        "max_obscuration": max_obsc,
        "sun_alt_deg": alt_s.degrees,
        "sun_az_deg": az_s.degrees,
        "moon_alt_deg": alt_m.degrees,
        "moon_az_deg": az_m.degrees,
    }
