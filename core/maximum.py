import numpy as np


def refine_maximum(eph, ts, t_guess):
    earth = eph["earth"]
    sun = eph["sun"]
    moon = eph["moon"]

    t0 = t_guess.utc_datetime()

    # estágio grosso
    minutes = np.arange(-720, 720, 3.0)

    times = ts.utc(
        t0.year, t0.month, t0.day,
        t0.hour, t0.minute,
        t0.second + minutes * 60
    )

    ast = earth.at(times)

    sep = ast.observe(sun).apparent().separation_from(
        ast.observe(moon).apparent()
    ).degrees

    t_coarse = times[np.argmin(sep)]

    # estágio fino
    t1 = t_coarse.utc_datetime()

    minutes = np.arange(-5, 5, 0.02)

    times = ts.utc(
        t1.year, t1.month, t1.day,
        t1.hour, t1.minute,
        t1.second + minutes * 60
    )

    ast = earth.at(times)

    sep = ast.observe(sun).apparent().separation_from(
        ast.observe(moon).apparent()
    ).degrees

    return times[np.argmin(sep)]