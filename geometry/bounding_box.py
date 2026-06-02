import numpy as np

from .surface_map import eclipse_obscuration_map


def eclipse_bounding_box(
        eph_path,
        t_start,
        t_end,
        coarse_step=5.0,
        threshold=0.001,
        time_chunks=2,
        pool=None,
):
    points = eclipse_obscuration_map(
        eph_path=eph_path,
        t_start=t_start,
        t_end=t_end,
        lat_step=coarse_step,
        lon_step=coarse_step,
        time_chunks=time_chunks,
        pool=pool,
    )

    if not points:
        return -90, 90, -180, 180

    filtered = [p for p in points if p[2] > threshold]

    if not filtered:
        return -90, 90, -180, 180

    lats = np.array([p[0] for p in filtered])
    lons = np.array([p[1] for p in filtered])

    expand = coarse_step

    return (
        max(-90, lats.min() - expand),
        min(90, lats.max() + expand),
        max(-180, lons.min() - expand),
        min(180, lons.max() + expand),
    )
