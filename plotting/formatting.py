import numpy as np


def format_time(t):
    if t is None:
        return "--"

    return t.utc_strftime("%H:%M:%S")


def duration_str(t1, t2):
    if t1 is None or t2 is None:
        return "--"

    seconds = (t2.tt - t1.tt) * 86400

    m = int(seconds // 60)
    s = int(seconds % 60)

    return f"{m}m {s}s"


def best_corner_position(max_point):

    lat_m, lon_m, _ = max_point

    north = lat_m >= 0
    east = lon_m >= 0

    if north and east:
        return "lower_left"

    elif north and not east:
        return "lower_right"

    elif not north and east:
        return "upper_left"

    else:
        return "upper_right"