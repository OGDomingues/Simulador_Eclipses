import numpy as np
from multiprocessing import Pool, cpu_count
from collections import defaultdict
from skyfield.api import load, load_file

from core.constants import R_SUN_KM, R_MOON_KM
from .geodesy import geodetic_to_ecef, ecef_to_gcrs
from .obscuration import angle_between, eclipse_obscuration_vec


# =====================================================
# Cache por processo (evita recarregar efemérides)
# =====================================================
_EPH = None
_TS = None


# =====================================================
# WORKER GEOMÉTRICO
# =====================================================
def _worker(args):
    latitudes, lons, t0, t1, eph_path = args

    global _EPH, _TS

    if _EPH is None:
        _TS = load.timescale()
        _EPH = load_file(eph_path)

    eph = _EPH
    ts = _TS

    earth = eph["earth"]
    sun = eph["sun"]
    moon = eph["moon"]

    # =====================
    # TEMPO
    # =====================
    times = ts.tt_jd(np.linspace(t0, t1, 20))

    earth_at_t = earth.at(times)

    sun_vec_all = earth_at_t.observe(sun).apparent().position.km.T
    moon_vec_all = earth_at_t.observe(moon).apparent().position.km.T

    T = len(times)

    # =====================
    # GRID
    # =====================
    lat_grid, lon_grid = np.meshgrid(latitudes, lons, indexing="ij")
    lat_flat = lat_grid.ravel()
    lon_flat = lon_grid.ravel()

    ecef = geodetic_to_ecef(lat_flat, lon_flat)
    P = len(lat_flat)

    # =====================
    # ROTACIONAR OBSERVADOR PARA TODOS OS TEMPOS
    # =====================
    obsc_all = np.zeros((T, P))

    for i in range(T):

        theta = np.radians(times[i].gmst * 15.0)
        obs_vec = ecef_to_gcrs(ecef, theta)

        sun_topo = sun_vec_all[i] - obs_vec
        moon_topo = moon_vec_all[i] - obs_vec

        up = obs_vec / np.linalg.norm(obs_vec, axis=1)[:, None]
        sun_norm = np.linalg.norm(sun_topo, axis=1)

        cos_z = np.einsum("ij,ij->i", sun_topo, up) / sun_norm
        sun_alt = np.arcsin(np.clip(cos_z, -1.0, 1.0))

        day_mask = sun_alt > 0

        d = angle_between(sun_topo, moon_topo)

        Rs = np.arcsin(R_SUN_KM / np.linalg.norm(sun_topo, axis=1))
        Rm = np.arcsin(R_MOON_KM / np.linalg.norm(moon_topo, axis=1))

        obsc = eclipse_obscuration_vec(d, Rs, Rm)
        obsc[~day_mask] = 0.0

        obsc_all[i] = obsc

    max_obsc = obsc_all.max(axis=0)

    result = {}
    for i, val in enumerate(max_obsc):
        if val > 0:
            result[(lat_flat[i], lon_flat[i])] = val

    return result


# =====================================================
# FUNÇÃO PRINCIPAL
# =====================================================
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
):
    """
    Calcula a obscuração máxima do Sol na superfície
    durante o intervalo [t_start, t_end].
    """

    # -------------------------------------------------
    # Pool externo ou interno
    # -------------------------------------------------
    if pool is None:
        if processes is None:
            processes = max(1, cpu_count() - 1)

        local_pool = Pool(processes=processes)
        close_pool = True

    else:
        local_pool = pool
        close_pool = False

    lat_min, lat_max = lat_range
    lon_min, lon_max = lon_range

    lats = np.arange(lat_min, lat_max + lat_step, lat_step)
    lons = np.arange(lon_min, lon_max + lon_step, lon_step)

    # Dividir latitude em blocos
    lat_chunks = np.array_split(
        lats,
        max(1, len(lats) // 30)
    )

    # Dividir tempo
    t_edges = np.linspace(
        t_start.tt,
        t_end.tt,
        time_chunks + 1
    )

    tasks = [
        (lc, lons, t_edges[i], t_edges[i + 1], eph_path)
        for lc in lat_chunks
        for i in range(time_chunks)
    ]

    results = local_pool.map(_worker, tasks)

    # -------------------------------------------------
    # Combinar blocos
    # -------------------------------------------------
    final = defaultdict(float)

    for block in results:
        for k, v in block.items():
            if v > final[k]:
                final[k] = v

    if close_pool:
        local_pool.close()
        local_pool.join()

    return [
        (lat, lon, obsc)
        for (lat, lon), obsc in final.items()
    ]