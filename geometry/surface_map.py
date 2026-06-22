from multiprocessing import Pool, cpu_count

import numpy as np
from skyfield.api import load, load_file

from core.constants import R_SUN_KM, R_MOON_KM
from .geodesy import geodetic_to_ecef
from .obscuration import eclipse_obscuration_vec

TIME_SAMPLES_PER_CHUNK = 20
INTERSECTION_EPSILON = 1e-15

_EPH = None
_TS = None


def _get_context(eph_path):
    global _EPH, _TS

    if _TS is None:
        _TS = load.timescale()

    if _EPH is None:
        _EPH = load_file(eph_path)

    return _EPH, _TS


def _time_sample_values(t_start, t_end, time_chunks):
    if time_chunks <= 0:
        return np.array([], dtype=float)

    t_edges = np.linspace(
        t_start.tt,
        t_end.tt,
        time_chunks + 1
    )
    sample_blocks = []

    for i in range(time_chunks):
        values = np.linspace(
            t_edges[i],
            t_edges[i + 1],
            TIME_SAMPLES_PER_CHUNK
        )

        if i > 0:
            values = values[1:]

        sample_blocks.append(values)

    return np.concatenate(sample_blocks)


def _ephemeris_samples(eph_path, t_start, t_end, time_chunks, eph=None, ts=None):
    if eph is None or ts is None:
        eph, ts = _get_context(eph_path)

    time_values = _time_sample_values(
        t_start,
        t_end,
        time_chunks
    )

    if len(time_values) == 0:
        empty_vecs = np.empty((0, 3), dtype=float)
        return (
            np.array([], dtype=float),
            empty_vecs,
            empty_vecs,
            np.array([], dtype=float),
            np.array([], dtype=float),
        )

    times = ts.tt_jd(time_values)
    earth_at_t = eph["earth"].at(times)

    sun_vec_all = earth_at_t.observe(
        eph["sun"]
    ).apparent().position.km.T
    moon_vec_all = earth_at_t.observe(
        eph["moon"]
    ).apparent().position.km.T

    # Keep the same scalar GMST path that the worker previously used.
    theta_values = np.radians(
        np.array(
            [times[i].gmst for i in range(len(time_values))],
            dtype=float
        )
        * 15.0
    )

    sun_dist_all = np.sqrt(
        np.einsum("ij,ij->i", sun_vec_all, sun_vec_all)
    )
    moon_dist_all = np.sqrt(
        np.einsum("ij,ij->i", moon_vec_all, moon_vec_all)
    )

    return (
        theta_values,
        sun_vec_all,
        moon_vec_all,
        sun_dist_all,
        moon_dist_all,
    )


def _worker(args):
    (
        lat_start,
        latitudes,
        lons,
        theta_values,
        sun_vec_all,
        moon_vec_all,
        sun_dist_all,
        moon_dist_all,
    ) = args

    T = len(theta_values)
    lat_grid, lon_grid = np.meshgrid(latitudes, lons, indexing="ij")
    lat_flat = lat_grid.ravel()
    lon_flat = lon_grid.ravel()

    ecef = geodetic_to_ecef(lat_flat, lon_flat)
    P = len(lat_flat)

    if P == 0:
        return (
            lat_start,
            np.zeros((len(latitudes), len(lons)), dtype=float)
        )

    ecef_x = ecef[:, 0]
    ecef_y = ecef[:, 1]
    ecef_z = ecef[:, 2]
    ecef_norm = np.linalg.norm(ecef, axis=1)
    max_ecef_norm = ecef_norm.max()
    max_obsc = np.zeros(P)

    for i in range(T):
        theta = theta_values[i]
        c = np.cos(theta)
        s = np.sin(theta)

        obs_x = c * ecef_x - s * ecef_y
        obs_y = s * ecef_x + c * ecef_y
        obs_z = ecef_z

        sun_vec = sun_vec_all[i]
        moon_vec = moon_vec_all[i]

        # Same horizon test as sun_alt > 0, without computing arcsin.
        sun_dot_up = (
            (
                obs_x * sun_vec[0]
                + obs_y * sun_vec[1]
                + obs_z * sun_vec[2]
            )
            / ecef_norm
            - ecef_norm
        )
        day_idx = np.flatnonzero(sun_dot_up > 0.0)

        if len(day_idx) == 0:
            continue

        day_obs_x = obs_x[day_idx]
        day_obs_y = obs_y[day_idx]
        day_obs_z = obs_z[day_idx]

        sun_topo_x = sun_vec[0] - day_obs_x
        sun_topo_y = sun_vec[1] - day_obs_y
        sun_topo_z = sun_vec[2] - day_obs_z

        moon_topo_x = moon_vec[0] - day_obs_x
        moon_topo_y = moon_vec[1] - day_obs_y
        moon_topo_z = moon_vec[2] - day_obs_z

        sun_norm = np.sqrt(
            sun_topo_x * sun_topo_x
            + sun_topo_y * sun_topo_y
            + sun_topo_z * sun_topo_z
        )
        moon_norm = np.sqrt(
            moon_topo_x * moon_topo_x
            + moon_topo_y * moon_topo_y
            + moon_topo_z * moon_topo_z
        )

        cosang = (
            sun_topo_x * moon_topo_x
            + sun_topo_y * moon_topo_y
            + sun_topo_z * moon_topo_z
        ) / (sun_norm * moon_norm)
        cosang = np.clip(cosang, -1.0, 1.0)

        max_disc_sum = (
            np.arcsin(
                R_SUN_KM
                / (sun_dist_all[i] - max_ecef_norm)
            )
            + np.arcsin(
                R_MOON_KM
                / (moon_dist_all[i] - max_ecef_norm)
            )
        )

        possible_idx = np.flatnonzero(
            cosang >= np.cos(max_disc_sum) - INTERSECTION_EPSILON
        )

        if len(possible_idx) == 0:
            continue

        possible_cosang = cosang[possible_idx]
        possible_sun_norm = sun_norm[possible_idx]
        possible_moon_norm = moon_norm[possible_idx]

        Rs = np.arcsin(R_SUN_KM / possible_sun_norm)
        Rm = np.arcsin(R_MOON_KM / possible_moon_norm)

        # Avoid arccos for points where the solar/lunar discs cannot overlap.
        maybe_intersect = (
            possible_cosang
            >= np.cos(Rs + Rm) - INTERSECTION_EPSILON
        )

        if not np.any(maybe_intersect):
            continue

        candidate_idx = day_idx[possible_idx[maybe_intersect]]
        d = np.arccos(possible_cosang[maybe_intersect])
        obsc = eclipse_obscuration_vec(
            d,
            Rs[maybe_intersect],
            Rm[maybe_intersect]
        )

        max_obsc[candidate_idx] = np.maximum(
            max_obsc[candidate_idx],
            obsc
        )

    return (
        lat_start,
        max_obsc.reshape(len(latitudes), len(lons))
    )


def eclipse_obscuration_map(
        eph_path,
        t_start,
        t_end,
        lat_step=1.5,
        lon_step=1.5,
        time_chunks=6,
        processes=None,
        lat_range=(-90, 90),
        lon_range=(-180, 180),
        pool=None,
        eph=None,
        ts=None,
):
    """
    Calcula a obscuração máxima do Sol na superfície
    durante o intervalo [t_start, t_end].
    """
    if pool is None:
        if processes is None:
            processes = max(1, cpu_count() - 1)

        if processes == 1:
            local_pool = None
            close_pool = False
        else:
            local_pool = Pool(processes=processes)
            close_pool = True

    else:
        local_pool = pool
        close_pool = False

    if local_pool is not None:
        worker_count = getattr(local_pool, "_processes", None)
    else:
        worker_count = processes

    if worker_count is None:
        worker_count = max(1, cpu_count() - 1)

    worker_count = max(1, int(worker_count))

    lat_min, lat_max = lat_range
    lon_min, lon_max = lon_range

    lats = np.arange(lat_min, lat_max + lat_step, lat_step)
    lons = np.arange(lon_min, lon_max + lon_step, lon_step)
    lat_chunk_count = max(1, len(lats) // 30)

    if len(lats) > 0:
        lat_chunk_count = max(
            lat_chunk_count,
            min(len(lats), worker_count)
        )

    lat_index_chunks = np.array_split(
        np.arange(len(lats)),
        lat_chunk_count
    )
    (
        theta_values,
        sun_vec_all,
        moon_vec_all,
        sun_dist_all,
        moon_dist_all,
    ) = _ephemeris_samples(
        eph_path,
        t_start,
        t_end,
        time_chunks,
        eph=eph,
        ts=ts,
    )

    tasks = [
        (
            int(lat_idx[0]),
            lats[lat_idx],
            lons,
            theta_values,
            sun_vec_all,
            moon_vec_all,
            sun_dist_all,
            moon_dist_all,
        )
        for lat_idx in lat_index_chunks
        if len(lat_idx) > 0
    ]

    final_grid = np.zeros(
        (len(lats), len(lons)),
        dtype=float
    )

    try:
        if local_pool is None:
            results = map(_worker, tasks)
        elif hasattr(local_pool, "imap_unordered"):
            results = local_pool.imap_unordered(
                _worker,
                tasks
            )
        else:
            results = local_pool.map(_worker, tasks)

        for lat_start, block in results:
            lat_stop = lat_start + block.shape[0]
            final_grid[lat_start:lat_stop, :] = np.maximum(
                final_grid[lat_start:lat_stop, :],
                block
            )

    finally:
        if close_pool and local_pool is not None:
            local_pool.close()
            local_pool.join()

    lat_idx, lon_idx = np.nonzero(final_grid > 0.0)

    return [
        (
            lats[i],
            lons[j],
            final_grid[i, j]
        )
        for i, j in zip(lat_idx, lon_idx)
    ]


def _eclipse_obscuration_points_for_coords(
        eph,
        when,
        lat_flat,
        lon_flat,
        min_obscuration,
):
    if len(lat_flat) == 0:
        return []

    ecef = geodetic_to_ecef(lat_flat, lon_flat)
    ecef_x = ecef[:, 0]
    ecef_y = ecef[:, 1]
    ecef_z = ecef[:, 2]
    ecef_norm = np.linalg.norm(ecef, axis=1)
    max_ecef_norm = ecef_norm.max()

    theta = np.radians(when.gmst * 15.0)
    c = np.cos(theta)
    s = np.sin(theta)

    obs_x = c * ecef_x - s * ecef_y
    obs_y = s * ecef_x + c * ecef_y
    obs_z = ecef_z

    earth_at_t = eph["earth"].at(when)
    sun_vec = earth_at_t.observe(
        eph["sun"]
    ).apparent().position.km
    moon_vec = earth_at_t.observe(
        eph["moon"]
    ).apparent().position.km

    sun_distance = np.linalg.norm(sun_vec)
    moon_distance = np.linalg.norm(moon_vec)

    sun_dot_up = (
        (
            obs_x * sun_vec[0]
            + obs_y * sun_vec[1]
            + obs_z * sun_vec[2]
        )
        / ecef_norm
        - ecef_norm
    )
    day_idx = np.flatnonzero(sun_dot_up > 0.0)

    if len(day_idx) == 0:
        return []

    day_obs_x = obs_x[day_idx]
    day_obs_y = obs_y[day_idx]
    day_obs_z = obs_z[day_idx]

    sun_topo_x = sun_vec[0] - day_obs_x
    sun_topo_y = sun_vec[1] - day_obs_y
    sun_topo_z = sun_vec[2] - day_obs_z

    moon_topo_x = moon_vec[0] - day_obs_x
    moon_topo_y = moon_vec[1] - day_obs_y
    moon_topo_z = moon_vec[2] - day_obs_z

    sun_norm = np.sqrt(
        sun_topo_x * sun_topo_x
        + sun_topo_y * sun_topo_y
        + sun_topo_z * sun_topo_z
    )
    moon_norm = np.sqrt(
        moon_topo_x * moon_topo_x
        + moon_topo_y * moon_topo_y
        + moon_topo_z * moon_topo_z
    )

    cosang = (
        sun_topo_x * moon_topo_x
        + sun_topo_y * moon_topo_y
        + sun_topo_z * moon_topo_z
    ) / (sun_norm * moon_norm)
    cosang = np.clip(cosang, -1.0, 1.0)

    max_disc_sum = (
        np.arcsin(
            R_SUN_KM
            / (sun_distance - max_ecef_norm)
        )
        + np.arcsin(
            R_MOON_KM
            / (moon_distance - max_ecef_norm)
        )
    )
    possible_idx = np.flatnonzero(
        cosang >= np.cos(max_disc_sum) - INTERSECTION_EPSILON
    )

    if len(possible_idx) == 0:
        return []

    Rs = np.arcsin(
        R_SUN_KM / sun_norm[possible_idx]
    )
    Rm = np.arcsin(
        R_MOON_KM / moon_norm[possible_idx]
    )
    possible_cosang = cosang[possible_idx]
    maybe_intersect = (
        possible_cosang
        >= np.cos(Rs + Rm) - INTERSECTION_EPSILON
    )

    if not np.any(maybe_intersect):
        return []

    candidate_idx = day_idx[possible_idx[maybe_intersect]]
    d = np.arccos(possible_cosang[maybe_intersect])
    obsc = eclipse_obscuration_vec(
        d,
        Rs[maybe_intersect],
        Rm[maybe_intersect],
    )
    keep = obsc >= min_obscuration

    if not np.any(keep):
        return []

    candidate_idx = candidate_idx[keep]
    obsc = obsc[keep]

    return [
        (
            float(lat_flat[i]),
            float(lon_flat[i]),
            float(value),
        )
        for i, value in zip(candidate_idx, obsc)
    ]


def eclipse_obscuration_frame(
        eph,
        ts,
        when,
        lat_step=2.0,
        lon_step=2.0,
        min_obscuration=0.001,
):
    """
    Calcula a sombra instantanea da Lua na superficie da Terra.
    Retorna apenas pontos onde os discos aparentes do Sol e da Lua se sobrepoem.
    """
    lat_step = max(0.5, float(lat_step))
    lon_step = max(0.5, float(lon_step))
    min_obscuration = max(0.0, float(min_obscuration))

    lats = np.arange(-90.0, 90.0 + lat_step, lat_step)
    lons = np.arange(-180.0, 180.0 + lon_step, lon_step)

    lat_grid, lon_grid = np.meshgrid(lats, lons, indexing="ij")
    lat_flat = lat_grid.ravel()
    lon_flat = lon_grid.ravel()

    points = _eclipse_obscuration_points_for_coords(
        eph,
        when,
        lat_flat,
        lon_flat,
        min_obscuration,
    )

    if not points:
        return []

    center_lat, center_lon, _ = max(
        points,
        key=lambda item: item[2],
    )
    fine_lat_step = max(
        0.15,
        lat_step / 3.0,
    )
    fine_lon_step = max(
        0.15,
        lon_step / 3.0,
    )
    lat_radius = max(4.0, lat_step * 8.0)
    lon_radius = max(4.0, lon_step * 8.0)
    fine_lats = np.arange(
        max(-90.0, center_lat - lat_radius),
        min(90.0, center_lat + lat_radius) + fine_lat_step,
        fine_lat_step,
    )
    fine_lons = np.arange(
        center_lon - lon_radius,
        center_lon + lon_radius + fine_lon_step,
        fine_lon_step,
    )
    fine_lons = ((fine_lons + 180.0) % 360.0) - 180.0
    fine_lat_grid, fine_lon_grid = np.meshgrid(
        fine_lats,
        fine_lons,
        indexing="ij",
    )
    fine_points = _eclipse_obscuration_points_for_coords(
        eph,
        when,
        fine_lat_grid.ravel(),
        fine_lon_grid.ravel(),
        min_obscuration,
    )

    merged = {}
    precision = 4
    for lat, lon, obsc in points + fine_points:
        key = (
            round(lat, precision),
            round(lon, precision),
        )
        previous = merged.get(key)
        if previous is None or obsc > previous:
            merged[key] = obsc

    return [
        (
            lat,
            lon,
            obsc,
        )
        for (lat, lon), obsc in merged.items()
    ]
