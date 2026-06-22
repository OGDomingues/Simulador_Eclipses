import numpy as np
from skyfield.api import wgs84
from datetime import timedelta

from .contacts import _find_contact
from .constants import R_SUN_KM, R_MOON_KM


def _disc_obscuration(separation_deg, sun_radius_deg, moon_radius_deg):
    if separation_deg >= sun_radius_deg + moon_radius_deg:
        return 0.0

    delta = np.radians(separation_deg)
    rs = np.radians(sun_radius_deg)
    rm = np.radians(moon_radius_deg)

    if delta <= abs(rs - rm):
        return float(min(1.0, (rm / rs) ** 2))

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
    return float((part1 + part2 - part3) / (np.pi * rs**2))


def _magnitude(separation_deg, sun_radius_deg, moon_radius_deg):
    if sun_radius_deg <= 0.0:
        return 0.0
    value = (sun_radius_deg + moon_radius_deg - separation_deg) / (
        2.0 * sun_radius_deg
    )
    return float(max(0.0, value))


def compute_local_circumstances_at(eph, when, lat, lon):
    earth = eph["earth"]
    sun = eph["sun"]
    moon = eph["moon"]

    observer = earth + wgs84.latlon(lat, lon)

    ast = observer.at(when)
    ast_s = ast.observe(sun).apparent()
    ast_m = ast.observe(moon).apparent()

    separation_deg = float(ast_s.separation_from(ast_m).degrees)
    sun_distance_km = ast_s.distance().km
    moon_distance_km = ast_m.distance().km

    sun_radius_deg = float(np.degrees(np.arcsin(R_SUN_KM / sun_distance_km)))
    moon_radius_deg = float(np.degrees(np.arcsin(R_MOON_KM / moon_distance_km)))

    alt_s, az_s, _ = ast_s.altaz()
    alt_m, az_m, _ = ast_m.altaz()

    return {
        "MAX": when,
        "separation_deg": separation_deg,
        "sun_radius_deg": sun_radius_deg,
        "moon_radius_deg": moon_radius_deg,
        "max_obscuration": _disc_obscuration(
            separation_deg,
            sun_radius_deg,
            moon_radius_deg,
        ),
        "magnitude": _magnitude(
            separation_deg,
            sun_radius_deg,
            moon_radius_deg,
        ),
        "sun_alt_deg": alt_s.degrees,
        "sun_az_deg": az_s.degrees,
        "moon_alt_deg": alt_m.degrees,
        "moon_az_deg": az_m.degrees,
    }


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
    sun_r_max = float(sun_r[idx])
    moon_r_max = float(moon_r[idx])
    max_obsc = 0.0
    if min_sep < limit[idx]:
        max_obsc = _disc_obscuration(
            min_sep,
            sun_r_max,
            moon_r_max,
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

    def duration_seconds(t_start, t_end):
        if t_start is None or t_end is None:
            return None
        return float((t_end.tt - t_start.tt) * 86400.0)

    eclipse_duration_sec = duration_seconds(C1, C4)
    totality_duration_sec = duration_seconds(C2, C3)

    magnitude = _magnitude(
        min_sep,
        sun_r_max,
        moon_r_max,
    )

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
        "separation_deg": min_sep,
        "sun_radius_deg": sun_r_max,
        "moon_radius_deg": moon_r_max,
        "max_obscuration": max_obsc,
        "magnitude": magnitude,
        "eclipse_duration_sec": eclipse_duration_sec,
        "totality_duration_sec": totality_duration_sec,
        "sun_alt_deg": alt_s.degrees,
        "sun_az_deg": az_s.degrees,
        "moon_alt_deg": alt_m.degrees,
        "moon_az_deg": az_m.degrees,
    }
