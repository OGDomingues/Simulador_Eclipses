import numpy as np

from .constants import R_SUN_KM, R_MOON_KM


def apparent_radius_arcsec(radius_km, distance_km):
    return np.degrees(np.arctan(radius_km / distance_km)) * 3600


def classify_eclipse(eph, central_times, max_obscuration, eps_arcsec=0.5):
    if max_obscuration < 0.9:
        return "Parcial"

    earth = eph["earth"]
    sun = eph["sun"]
    moon = eph["moon"]

    deltas = []

    for t in central_times:
        observer = earth.at(t)

        moon_dist = observer.observe(moon).distance().km
        sun_dist = observer.observe(sun).distance().km

        moon_r = apparent_radius_arcsec(R_MOON_KM, moon_dist)
        sun_r = apparent_radius_arcsec(R_SUN_KM, sun_dist)

        deltas.append(moon_r - sun_r)

    deltas = np.array(deltas)

    if np.all(deltas > eps_arcsec):
        return "Total"

    if np.all(deltas < -eps_arcsec):
        return "Anular"

    if np.any(deltas > eps_arcsec) and np.any(deltas < -eps_arcsec):
        return "Total/Anular"

    return "Anular" if np.mean(deltas) < 0 else "Total"


def eclipse_title(eclipse_type: str, date_str: str) -> str:
    nomes = {
        "Parcial": "Eclipse Solar Parcial",
        "Total": "Eclipse Solar Total",
        "Anular": "Eclipse Solar Anular",
        "Total/Anular": "Eclipse Solar Híbrido",
    }

    return f"{nomes.get(eclipse_type, 'Eclipse Solar')} — {date_str}"
