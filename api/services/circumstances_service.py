from core import (
    new_moons,
    compute_local_circumstances,
    compute_local_circumstances_at,
)
from core.constants import R_MOON_KM, R_SUN_KM
import numpy as np
from functools import lru_cache
from skyfield.api import wgs84

from infrastructure.ephemeris import (
    get_context,
)

from pipeline.batch import run_batch


def parse_utc_time(ts, value: str | None):
    if not value:
        return None

    cleaned = value.strip().replace("Z", "+00:00")

    from datetime import datetime

    dt = datetime.fromisoformat(cleaned)
    return ts.utc(dt)


def serialize_time(t):
    if t is None:
        return None

    return t.utc_strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )


def disc_fully_below_horizon(
    altitude_deg,
    radius_deg,
):
    return bool(altitude_deg <= -abs(radius_deg or 0.0))


def both_discs_below_horizon(instant):
    return (
        disc_fully_below_horizon(
            instant["sun_alt_deg"],
            instant.get("sun_radius_deg"),
        )
        and disc_fully_below_horizon(
            instant["moon_alt_deg"],
            instant.get("moon_radius_deg"),
        )
    )


def circumstance_payload(local, instant, visible):
    geometric_obscuration = instant["max_obscuration"]
    geometric_magnitude = instant.get("magnitude")
    sun_disc_below_horizon = disc_fully_below_horizon(
        instant["sun_alt_deg"],
        instant.get("sun_radius_deg"),
    )
    moon_disc_below_horizon = disc_fully_below_horizon(
        instant["moon_alt_deg"],
        instant.get("moon_radius_deg"),
    )

    return {
        "obscuration": geometric_obscuration if visible else 0.0,
        "magnitude": geometric_magnitude if visible else 0.0,
        "geometric_obscuration": geometric_obscuration,
        "geometric_magnitude": geometric_magnitude,
        "duration_sec":
            local.get("eclipse_duration_sec"),
        "totality_duration_sec":
            local.get("totality_duration_sec"),

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
            instant["sun_alt_deg"],

        "sun_az":
            instant["sun_az_deg"],

        "moon_alt":
            instant["moon_alt_deg"],

        "moon_az":
            instant["moon_az_deg"],

        "sun_radius_deg":
            instant.get("sun_radius_deg"),

        "moon_radius_deg":
            instant.get("moon_radius_deg"),

        "separation_deg":
            instant.get("separation_deg"),
        "current_time":
            serialize_time(instant["MAX"]),
        "sun_disc_below_horizon": sun_disc_below_horizon,
        "moon_disc_below_horizon": moon_disc_below_horizon,
        "bodies_below_horizon":
            sun_disc_below_horizon and moon_disc_below_horizon,
        "visible": visible,
    }


def is_visible(instant):
    return bool(
        instant["max_obscuration"] > MIN_VISIBLE_OBSCURATION
        and not disc_fully_below_horizon(
            instant["sun_alt_deg"],
            instant.get("sun_radius_deg"),
        )
    )


MIN_VISIBLE_OBSCURATION = 0.0005


@lru_cache(maxsize=64)
def get_selected_eclipse(eclipse_date: str):
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

    for eclipse in eclipses:
        current_date = (
            eclipse["MAX"]
            .utc_datetime()
            .date()
            .isoformat()
        )

        if current_date == eclipse_date:
            return eclipse

    return None


@lru_cache(maxsize=512)
def get_base_local_circumstances(
    eclipse_date: str,
    lat: float,
    lon: float,
):
    selected = get_selected_eclipse(eclipse_date)

    if selected is None:
        return None

    eph, ts = get_context()

    return compute_local_circumstances(
        eph=eph,
        ts=ts,
        t_max=selected["MAX"],
        lat=lat,
        lon=lon,
    )


def get_circumstances(
    eclipse_date: str,
    lat: float,
    lon: float,
    time: str | None = None,
):
    eph, ts = get_context()

    local = get_base_local_circumstances(
        eclipse_date,
        round(lat, 6),
        round(lon, 6),
    )

    if local is None:
        return None

    instant_time = parse_utc_time(ts, time)
    instant = (
        compute_local_circumstances_at(
            eph=eph,
            when=instant_time,
            lat=lat,
            lon=lon,
        )
        if instant_time is not None
        else local
    )

    return circumstance_payload(
        local,
        instant,
        is_visible(instant),
    )


def get_local_maximum(
    eclipse_date: str,
    lat: float,
    lon: float,
):
    return get_cached_local_maximum(
        eclipse_date,
        round(lat, 6),
        round(lon, 6),
    )


def local_time_range(local):
    start = local["C1"]
    end = local["C4"]

    if start is None or end is None:
        center = local["MAX"]
        return (
            center.tt - (2.0 / 24.0),
            center.tt + (2.0 / 24.0),
        )

    padding_days = (90 * 60) / 86400.0
    return (
        start.tt - padding_days,
        end.tt + padding_days,
    )


def both_below_horizon_mask(
    eph,
    ts,
    lat: float,
    lon: float,
    tt_values,
):
    earth = eph["earth"]
    sun = eph["sun"]
    moon = eph["moon"]
    observer = earth + wgs84.latlon(lat, lon)
    times = ts.tt_jd(tt_values)
    ast = observer.at(times)

    sun_ast = ast.observe(sun).apparent()
    moon_ast = ast.observe(moon).apparent()

    sun_alt, _, _ = sun_ast.altaz()
    moon_alt, _, _ = moon_ast.altaz()

    sun_radius_deg = np.degrees(
        np.arcsin(R_SUN_KM / sun_ast.distance().km)
    )
    moon_radius_deg = np.degrees(
        np.arcsin(R_MOON_KM / moon_ast.distance().km)
    )

    return (
        sun_alt.degrees <= -sun_radius_deg
    ) & (
        moon_alt.degrees <= -moon_radius_deg
    )


def find_both_below_horizon_tt(
    eph,
    ts,
    lat: float,
    lon: float,
    start_tt: float,
):
    search_step_days = (10 * 60) / 86400.0
    max_search_days = 1.5
    tt_values = np.arange(
        start_tt,
        start_tt + max_search_days + search_step_days,
        search_step_days,
    )

    below_mask = both_below_horizon_mask(
        eph,
        ts,
        lat,
        lon,
        tt_values,
    )
    below_indices = np.flatnonzero(below_mask)

    if len(below_indices) == 0:
        return start_tt

    first_below_index = int(below_indices[0])

    if first_below_index == 0:
        return start_tt

    low = float(tt_values[first_below_index - 1])
    high = float(tt_values[first_below_index])

    for _ in range(18):
        middle = (low + high) / 2.0
        instant = compute_local_circumstances_at(
            eph=eph,
            when=ts.tt_jd(middle),
            lat=lat,
            lon=lon,
        )

        if both_discs_below_horizon(instant):
            high = middle
        else:
            low = middle

    return high


def build_local_frames(
    eclipse_date: str,
    lat: float,
    lon: float,
    step_seconds: int,
):
    eph, ts = get_context()

    local = get_base_local_circumstances(
        eclipse_date,
        round(lat, 6),
        round(lon, 6),
    )

    if local is None:
        return None

    start_tt, contact_end_tt = local_time_range(local)
    horizon_end_tt = find_both_below_horizon_tt(
        eph,
        ts,
        lat,
        lon,
        contact_end_tt,
    )
    end_tt = max(
        contact_end_tt,
        horizon_end_tt,
    )

    count = int(
        np.ceil(
            (end_tt - start_tt)
            * 86400.0
            / step_seconds
        )
    ) + 1
    count = max(
        2,
        min(count, 720),
    )

    times = ts.tt_jd(
        np.linspace(
            start_tt,
            end_tt,
            count,
        )
    )

    frames = []
    max_frame_index = 0
    max_obscuration = -1.0

    for index, when in enumerate(times):
        instant = compute_local_circumstances_at(
            eph=eph,
            when=when,
            lat=lat,
            lon=lon,
        )
        frame = circumstance_payload(
            local,
            instant,
            is_visible(instant),
        )
        frames.append(frame)

        if instant["max_obscuration"] > max_obscuration:
            max_obscuration = instant["max_obscuration"]
            max_frame_index = index

    return {
        "max_frame_index": max_frame_index,
        "frames": frames,
    }


@lru_cache(maxsize=512)
def get_cached_local_maximum(
    eclipse_date: str,
    lat: float,
    lon: float,
):
    data = build_local_frames(
        eclipse_date,
        lat,
        lon,
        60,
    )

    if data is None:
        return None

    return data["frames"][
        data["max_frame_index"]
    ]


def get_local_animation(
    eclipse_date: str,
    lat: float,
    lon: float,
    step_seconds: int = 120,
):
    step_seconds = max(
        15,
        min(int(step_seconds), 900),
    )

    data = build_local_frames(
        eclipse_date,
        lat,
        lon,
        step_seconds,
    )

    if data is None:
        return None

    return {
        "date": eclipse_date,
        "lat": lat,
        "lon": lon,
        "step_seconds": step_seconds,
        "max_frame_index": data["max_frame_index"],
        "maximum": get_local_maximum(
            eclipse_date,
            lat,
            lon,
        ),
        "frames": data["frames"],
    }
