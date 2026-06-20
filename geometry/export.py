from pathlib import Path
import json
from xml.etree.ElementTree import Element, SubElement, tostring

import numpy as np
import matplotlib
from scipy.ndimage import zoom
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.interpolate import splprep, splev


def _time_iso(t):
    if t is None:
        return None
    return t.utc_iso().replace("+00:00", "Z")


def _feature(name, geometry=None, when=None, properties=None):
    props = {"name": name}
    if when is not None:
        props["time"] = _time_iso(when)
    if properties:
        props.update(properties)
    return {
        "type": "Feature",
        "properties": props,
        "geometry": geometry,
    }


def _contour_levels(max_obsc):
    levels = [0.1, 0.25, 0.5, 0.75, 0.9]
    return [level for level in levels if level <= max_obsc]


def _limit_levels(max_obsc):
    levels = [0.999]
    return [level for level in levels if level <= max_obsc]


def _band_style(level):
    palette = [
        (0.10, "#ffffcc", 0.28),
        (0.25, "#ffeda0", 0.32),
        (0.50, "#feb24c", 0.36),
        (0.75, "#fd8d3c", 0.40),
        (0.90, "#f03b20", 0.44),
    ]
    for threshold, color, alpha in palette:
        if level <= threshold:
            return color, alpha
    return "#bd0026", 0.48


def _polygon_coords(segment):
    if len(segment) > 10:
        tck, _ = splprep(
            [segment[:, 0], segment[:, 1]],
            s=0
        )

        u_new = np.linspace(
            0,
            1,
            len(segment) * 8
        )

        x_new, y_new = splev(
            u_new,
            tck
        )

        segment = np.column_stack(
            [x_new, y_new]
        )
    coords = [[float(x), float(y)] for x, y in segment]
    if coords and coords[0] != coords[-1]:
        coords.append(coords[0])
    return coords


def _band_features(points):
    if not points:
        return []

    lats = np.array([p[0] for p in points])
    lons = np.array([p[1] for p in points])
    vals = np.array([p[2] for p in points])

    lat_unique = np.unique(lats)
    lon_unique = np.unique(lons)

    if len(lat_unique) < 2 or len(lon_unique) < 2:
        return []

    grid = np.full(
        (len(lat_unique), len(lon_unique)),
        np.nan,
    )

    lat_index = {
        lat: i
        for i, lat in enumerate(lat_unique)
    }

    lon_index = {
        lon: j
        for j, lon in enumerate(lon_unique)
    }

    for lat, lon, val in points:
        grid[
            lat_index[lat],
            lon_index[lon],
        ] = val

    fig, ax = plt.subplots()

    levels = _contour_levels(
        np.nanmax(vals)
    )

    if not levels:
        plt.close(fig)
        return []

    cs = ax.contour(
        lon_unique,
        lat_unique,
        grid,
        levels=levels,
    )

    plt.close(fig)

    features = []

    for level, segments in zip(
        cs.levels,
        cs.allsegs,
    ):
        color, alpha = _band_style(
            float(level)
        )

        for segment in segments:
            if len(segment) < 2:
                continue

            coords = [
                [float(x), float(y)]
                for x, y in segment
            ]

            features.append(
                _feature(
                    f"obscuration_{level:.0%}",
                    geometry={
                        "type": "LineString",
                        "coordinates": coords,
                    },
                    properties={
                        "level": float(level),
                        "color": color,
                        "alpha": alpha,
                    },
                )
            )

    return features


def _limit_features(points):
    if not points:
        return []

    lats = np.array([p[0] for p in points])
    lons = np.array([p[1] for p in points])
    vals = np.array([p[2] for p in points])

    lat_unique = np.unique(lats)
    lon_unique = np.unique(lons)

    if len(lat_unique) < 2 or len(lon_unique) < 2:
        return []

    grid = np.full(
        (len(lat_unique), len(lon_unique)),
        np.nan,
    )

    lat_index = {
        lat: i
        for i, lat in enumerate(lat_unique)
    }

    lon_index = {
        lon: j
        for j, lon in enumerate(lon_unique)
    }

    for lat, lon, val in points:
        grid[
            lat_index[lat],
            lon_index[lon],
        ] = val

    fig, ax = plt.subplots()

    levels = _limit_levels(
        np.nanmax(vals)
    )

    if not levels:
        plt.close(fig)
        return []

    cs = ax.contour(
        lon_unique,
        lat_unique,
        grid,
        levels=levels,
    )

    plt.close(fig)

    limit_features = []

    for level, segments in zip(
        cs.levels,
        cs.allsegs,
    ):
        for segment in segments:

            if len(segment) < 2:
                continue

            coords = [
                [float(x), float(y)]
                for x, y in segment
            ]

            lats_seg = np.array(
                [c[1] for c in coords]
            )

            mid_lat = (
                lats_seg.min()
                + lats_seg.max()
            ) / 2.0

            north_coords = [
                c
                for c in coords
                if c[1] >= mid_lat
            ]

            south_coords = [
                c
                for c in coords
                if c[1] < mid_lat
            ]

            if len(north_coords) > 2:
                limit_features.append(
                    _feature(
                        "north_limit",
                        geometry={
                            "type": "LineString",
                            "coordinates": north_coords,
                        },
                        properties={
                            "level": float(level),
                        },
                    )
                )

            if len(south_coords) > 2:
                limit_features.append(
                    _feature(
                        "south_limit",
                        geometry={
                            "type": "LineString",
                            "coordinates": south_coords,
                        },
                        properties={
                            "level": float(level),
                        },
                    )
                )

    print(
        "limit features:",
        len(limit_features)
    )

    return limit_features

def export_eclipse_geojson(eclipse, local=None, points=None, output=None):
    if output is None:
        output = Path("outputs") / f"Eclipse_{eclipse['date']}.geojson"
    else:
        output = Path(output)

    features = []

    if eclipse.get("central_path"):
        coords = [
            [lon, lat]
            for lat, lon, _ in eclipse["central_path"]
        ]
        features.append(
            _feature(
                "central_path",
                geometry={
                    "type": "LineString",
                    "coordinates": coords,
                },
            )
        )

    if points:
        features.extend(_band_features(points))
        features.extend(_limit_features(points))

    for label in ("C1", "C2", "MAX", "C3", "C4"):
        if eclipse.get(label) is not None:
            features.append(
                _feature(
                    label,
                    geometry=None,
                    when=eclipse[label],
                )
            )

    if local is not None:
        features.append(
            _feature(
                "observer",
                geometry={
                    "type": "Point",
                    "coordinates": [
                        local["location"]["lon"],
                        local["location"]["lat"],
                    ],
                },
                when=local.get("MAX"),
                properties={
                    "max_obscuration": local.get("max_obscuration"),
                    "c1_local": local.get("C1_local"),
                    "max_local": local.get("MAX_local"),
                    "c4_local": local.get("C4_local"),
                },
            )
        )

    data = {
        "type": "FeatureCollection",
        "properties": {
            "eclipse_date": eclipse["date"],
            "eclipse_type": eclipse.get("type"),
        },
        "features": features,
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(output)


def export_eclipse_kml(eclipse, local=None, points=None, output=None):
    if output is None:
        output = Path("outputs") / f"Eclipse_{eclipse['date']}.kml"
    else:
        output = Path(output)

    kml = Element("kml", xmlns="http://www.opengis.net/kml/2.2")
    doc = SubElement(kml, "Document")
    SubElement(doc, "name").text = f"Eclipse {eclipse['date']}"

    if eclipse.get("central_path"):
        placemark = SubElement(doc, "Placemark")
        SubElement(placemark, "name").text = "Central path"
        line = SubElement(placemark, "LineString")
        SubElement(line, "tessellate").text = "1"
        coords = SubElement(line, "coordinates")
        coords.text = " ".join(
            f"{lon},{lat},0"
            for lat, lon, _ in eclipse["central_path"]
        )

    if local is not None:
        placemark = SubElement(doc, "Placemark")
        SubElement(placemark, "name").text = "Observer"
        description = SubElement(placemark, "description")
        description.text = (
            f"MAX local: {local.get('MAX_local')}<br/>"
            f"Obscuration: {local.get('max_obscuration'):.1%}<br/>"
            f"C1 local: {local.get('C1_local')}<br/>"
            f"C4 local: {local.get('C4_local')}"
        )
        point = SubElement(placemark, "Point")
        coords = SubElement(point, "coordinates")
        coords.text = f"{local['location']['lon']},{local['location']['lat']},0"

    if points:
        folder = SubElement(doc, "Folder")
        SubElement(folder, "name").text = "Obscuration bands"
        for feature in _band_features(points):
            placemark = SubElement(folder, "Placemark")
            SubElement(placemark, "name").text = feature["properties"]["name"]
            style = SubElement(placemark, "Style")
            poly_style = SubElement(style, "PolyStyle")
            color = feature["properties"]["color"].lstrip("#")
            alpha = int(round(feature["properties"]["alpha"] * 255))
            abgr = f"{alpha:02x}{color[4:6]}{color[2:4]}{color[0:2]}"
            SubElement(poly_style, "color").text = abgr
            SubElement(poly_style, "fill").text = "1"
            SubElement(poly_style, "outline").text = "0"
            polygon = SubElement(placemark, "Polygon")
            SubElement(polygon, "tessellate").text = "1"
            outer = SubElement(polygon, "outerBoundaryIs")
            ring = SubElement(outer, "LinearRing")
            coords = SubElement(ring, "coordinates")
            coords.text = " ".join(
                f"{lon},{lat},0"
                for lon, lat in feature["geometry"]["coordinates"][0]
            )

        for feature in _limit_features(points):
            placemark = SubElement(folder, "Placemark")
            SubElement(placemark, "name").text = feature["properties"]["name"]
            style = SubElement(placemark, "Style")
            line_style = SubElement(style, "LineStyle")
            SubElement(line_style, "color").text = "ff0000ff"
            SubElement(line_style, "width").text = "2"
            line = SubElement(placemark, "LineString")
            SubElement(line, "tessellate").text = "1"
            coords = SubElement(line, "coordinates")
            coords.text = " ".join(
                f"{lon},{lat},0"
                for lon, lat in feature["geometry"]["coordinates"]
            )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(tostring(kml, encoding="utf-8", xml_declaration=True))
    return str(output)
