import numpy as np


def angle_between(u, v):
    dot = np.einsum("ij,ij->i", u, v)

    nu = np.linalg.norm(u, axis=1)
    nv = np.linalg.norm(v, axis=1)

    cosang = dot / (nu * nv)
    cosang = np.clip(cosang, -1.0, 1.0)

    return np.arccos(cosang)


def eclipse_obscuration_vec(d, Rs, Rm):
    o = np.zeros_like(d)

    mask_intersect = d < (Rs + Rm)
    mask_full = d <= np.abs(Rs - Rm)
    if np.any(mask_full):
        o[mask_full] = np.minimum(
            1.0,
            (Rm[mask_full] / Rs[mask_full]) ** 2
        )
    m = mask_intersect & ~mask_full

    if np.any(m):
        d2 = d[m]
        Rs2 = Rs[m]
        Rm2 = Rm[m]

        part1 = (
                Rm2 ** 2 *
                np.arccos(
                    (d2 * d2 + Rm2 * Rm2 - Rs2 * Rs2)
                    /
                    (2 * d2 * Rm2)
                )
        )

        part2 = (
                Rs2 ** 2 *
                np.arccos(
                    (d2 * d2 + Rs2 * Rs2 - Rm2 * Rm2)
                    /
                    (2 * d2 * Rs2)
                )
        )

        part3 = 0.5 * np.sqrt(
            (-d2 + Rm2 + Rs2) *
            (d2 + Rm2 - Rs2) *
            (d2 - Rm2 + Rs2) *
            (d2 + Rm2 + Rs2)
        )

        o[m] = (
                       part1 + part2 - part3
               ) / (
                       np.pi * Rs2 * Rs2
               )

    return o
