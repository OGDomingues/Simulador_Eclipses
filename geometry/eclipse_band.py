import math

from core.magnitude import (
    compute_surface_max_magnitude,
)

from skyfield.api import wgs84
import numpy as np

from core.constants import (
    R_SUN_KM,
    R_MOON_KM,
)
EARTH_RADIUS_KM = 6371.0


def destination_point(
    lat,
    lon,
    bearing_deg,
    distance_km,
):
    lat1 = math.radians(lat)
    lon1 = math.radians(lon)

    bearing = math.radians(
        bearing_deg
    )

    angular_distance = (
        distance_km
        / EARTH_RADIUS_KM
    )

    lat2 = math.asin(
        math.sin(lat1)
        * math.cos(
            angular_distance
        )
        +
        math.cos(lat1)
        * math.sin(
            angular_distance
        )
        * math.cos(bearing)
    )

    lon2 = lon1 + math.atan2(
        math.sin(bearing)
        * math.sin(
            angular_distance
        )
        * math.cos(lat1),
        math.cos(
            angular_distance
        )
        -
        math.sin(lat1)
        * math.sin(lat2),
    )

    return (
        math.degrees(lat2),
        math.degrees(lon2),
    )


def find_totality_edge(
    eph,
    ts,
    time,
    lat,
    lon,
    bearing,
):
    low = 0.0
    high = 250.0

    for _ in range(12):
        mid = (
            low + high
        ) / 2.0

        test_lat, test_lon = (
            destination_point(
                lat,
                lon,
                bearing,
                mid,
            )
        )

        margin = totality_margin(
            eph,
            time,
            test_lat,
            test_lon,
        )

        if margin > 0:
            low = mid
        else:
            high = mid

    return destination_point(
        lat,
        lon,
        bearing,
        low,
    )


def build_totality_limits(
    eph,
    ts,
    path,
):
    north = []
    south = []

    sparse_path = path[::2]

    print(
        "Calculando faixa:",
        len(sparse_path),
        "pontos"
    )

    for i in range(
        1,
        len(sparse_path) - 1
    ):
        lat_prev, lon_prev, _ = (
            sparse_path[i - 1]
        )

        lat, lon, time = (
            sparse_path[i]
        )

        lat_next, lon_next, _ = (
            sparse_path[i + 1]
        )

        dlat = (
            lat_next - lat_prev
        )

        dlon = (
            lon_next - lon_prev
        )

        heading = math.degrees(
            math.atan2(
                dlon,
                dlat,
            )
        )

        north_bearing = (
            heading + 90.0
        )

        south_bearing = (
            heading - 90.0
        )

        north_point = (
            find_totality_edge(
                eph,
                ts,
                time,
                lat,
                lon,
                north_bearing,
            )
        )

        south_point = (
            find_totality_edge(
                eph,
                ts,
                time,
                lat,
                lon,
                south_bearing,
            )
        )

        north.append(
            list(north_point)
        )

        south.append(
            list(south_point)
        )

        if i % 10 == 0:
            width = haversine(
                north_point[0],
                north_point[1],
                south_point[0],
                south_point[1],
            )

            print(
                f"[{i}/{len(sparse_path)}] "
                f"lat={lat:.2f} "
                f"lon={lon:.2f} "
                f"width={width:.1f} km"
            )

    print(
        "North:",
        len(north)
    )

    print(
        "South:",
        len(south)
    )

    return (
        north,
        south,
    )

def totality_margin(
    eph,
    time,
    lat,
    lon,
):
    earth = eph["earth"]
    sun = eph["sun"]
    moon = eph["moon"]

    observer = (
        earth
        + wgs84.latlon(
            lat,
            lon,
        )
    )

    ast = observer.at(time)

    sun_ast = (
        ast.observe(sun)
        .apparent()
    )

    moon_ast = (
        ast.observe(moon)
        .apparent()
    )

    delta = (
        sun_ast
        .separation_from(
            moon_ast
        )
        .radians
    )

    rs = np.arcsin(
        R_SUN_KM
        / sun_ast.distance().km
    )

    rm = np.arcsin(
        R_MOON_KM
        / moon_ast.distance().km
    )

    return (
        abs(rm - rs)
        - delta
    )

def haversine(
    lat1,
    lon1,
    lat2,
    lon2,
):
    R = 6371.0

    dlat = math.radians(
        lat2 - lat1
    )

    dlon = math.radians(
        lon2 - lon1
    )

    a = (
        math.sin(dlat / 2) ** 2
        +
        math.cos(
            math.radians(lat1)
        )
        *
        math.cos(
            math.radians(lat2)
        )
        *
        math.sin(dlon / 2) ** 2
    )

    c = (
        2
        * math.atan2(
            math.sqrt(a),
            math.sqrt(1 - a),
        )
    )

    return R * c