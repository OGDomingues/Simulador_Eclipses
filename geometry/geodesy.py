import numpy as np
A = 6378.137
F = 1 / 298.257223563
E2 = F * (2 - F)


def geodetic_to_ecef(lat, lon):
    lat = np.radians(lat)
    lon = np.radians(lon)

    N = A / np.sqrt(1 - E2 * np.sin(lat) ** 2)

    x = N * np.cos(lat) * np.cos(lon)
    y = N * np.cos(lat) * np.sin(lon)
    z = N * (1 - E2) * np.sin(lat)

    return np.vstack((x, y, z)).T


def ecef_to_gcrs(ecef, theta):
    c = np.cos(theta)
    s = np.sin(theta)

    R = np.array([
        [c, -s, 0],
        [s, c, 0],
        [0, 0, 1]
    ])

    return (R @ ecef.T).T
