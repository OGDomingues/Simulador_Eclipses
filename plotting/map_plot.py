import matplotlib

matplotlib.use("Agg")

from pathlib import Path
import urllib.request
import zipfile

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection, PolyCollection
from scipy.ndimage import gaussian_filter, zoom

try:
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature
except ModuleNotFoundError:
    ccrs = None
    cfeature = None

try:
    import shapefile
except ModuleNotFoundError:
    shapefile = None

from .formatting import (
    format_time,
    duration_str,
    best_corner_position,
)

from .colormaps import get_obscuration_colormap

BASE_DIR = Path(__file__).resolve().parent.parent
NATURAL_EARTH_DIR = BASE_DIR / "data" / "natural_earth"
NATURAL_EARTH_FILES = {
    "land": (
        "ne_50m_land",
        "https://naturalearth.s3.amazonaws.com/50m_physical/ne_50m_land.zip",
    ),
    "borders": (
        "ne_50m_admin_0_boundary_lines_land",
        "https://naturalearth.s3.amazonaws.com/50m_cultural/"
        "ne_50m_admin_0_boundary_lines_land.zip",
    ),
}

PLOT_UPSAMPLE_FACTOR = 5
PLOT_PADDING_CELLS = 4
MAX_PLOT_GRID_CELLS = 2_000_000
MIN_VISIBLE_OBSCURATION = 0.0005


def ensure_natural_earth(name):
    stem, url = NATURAL_EARTH_FILES[name]
    shp_path = NATURAL_EARTH_DIR / f"{stem}.shp"

    if shp_path.exists():
        return shp_path

    NATURAL_EARTH_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    zip_path = NATURAL_EARTH_DIR / f"{stem}.zip"

    try:
        print(f"Baixando Natural Earth: {stem}...")
        urllib.request.urlretrieve(
            url,
            zip_path
        )

        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(NATURAL_EARTH_DIR)

    except (OSError, zipfile.BadZipFile) as exc:
        print(
            "[WARN] Nao foi possivel baixar Natural Earth: "
            f"{exc}"
        )
        return None

    finally:
        if zip_path.exists():
            zip_path.unlink()

    return shp_path if shp_path.exists() else None


def shapefile_parts(shp_path):
    reader = shapefile.Reader(str(shp_path))

    for shape in reader.shapes():
        points = shape.points
        parts = list(shape.parts) + [len(points)]

        for start, end in zip(parts[:-1], parts[1:]):
            coords = points[start:end]

            if len(coords) >= 2:
                yield coords


def add_polygon_shapefile(
        ax,
        shp_path,
        facecolor,
        edgecolor,
        linewidth,
        zorder,
):
    polygons = [
        coords
        for coords in shapefile_parts(shp_path)
        if len(coords) >= 3
    ]

    ax.add_collection(
        PolyCollection(
            polygons,
            facecolors=facecolor,
            edgecolors=edgecolor,
            linewidths=linewidth,
            closed=True,
            zorder=zorder,
        )
    )


def add_line_shapefile(
        ax,
        shp_path,
        color,
        linewidth,
        alpha,
        zorder,
):
    lines = list(shapefile_parts(shp_path))

    ax.add_collection(
        LineCollection(
            lines,
            colors=color,
            linewidths=linewidth,
            alpha=alpha,
            zorder=zorder,
        )
    )


def add_plain_map_features(ax):
    if shapefile is None:
        print(
            "[WARN] PyShp indisponivel. "
            "Gerando mapa sem continentes."
        )
        return

    land_path = ensure_natural_earth("land")

    if land_path is not None:
        add_polygon_shapefile(
            ax,
            land_path,
            facecolor="#f4f1de",
            edgecolor="#2f2f2f",
            linewidth=0.25,
            zorder=0,
        )

    borders_path = ensure_natural_earth("borders")

    if borders_path is not None:
        add_line_shapefile(
            ax,
            borders_path,
            color="#555555",
            linewidth=0.35,
            alpha=0.7,
            zorder=4,
        )


def grid_step(values):
    diffs = np.diff(values)
    diffs = diffs[diffs > 0]

    if len(diffs) == 0:
        return 1.0

    return float(np.median(diffs))


def expanded_axis(values, step, min_value, max_value):
    start = values[0] - step * PLOT_PADDING_CELLS
    stop = values[-1] + step * PLOT_PADDING_CELLS

    if start < min_value:
        start += np.ceil((min_value - start) / step) * step

    if stop > max_value:
        stop -= np.ceil((stop - max_value) / step) * step

    if stop < start:
        return values.copy()

    count = int(round((stop - start) / step)) + 1

    return start + np.arange(count) * step


def plot_upsample_factor(shape):
    cell_count = shape[0] * shape[1]

    if cell_count == 0:
        return 1

    max_factor = int(
        np.sqrt(MAX_PLOT_GRID_CELLS / cell_count)
    )

    return max(
        1,
        min(PLOT_UPSAMPLE_FACTOR, max_factor)
    )


def build_smooth_plot_grid(lat_unique, lon_unique, grid):
    lat_step = grid_step(lat_unique)
    lon_step = grid_step(lon_unique)

    plot_lats = expanded_axis(
        lat_unique,
        lat_step,
        -90.0,
        90.0
    )

    plot_lons = expanded_axis(
        lon_unique,
        lon_step,
        -180.0,
        180.0
    )

    plot_grid = np.zeros(
        (len(plot_lats), len(plot_lons)),
        dtype=float
    )

    lat_offset = int(
        round((lat_unique[0] - plot_lats[0]) / lat_step)
    )
    lon_offset = int(
        round((lon_unique[0] - plot_lons[0]) / lon_step)
    )

    values = np.nan_to_num(
        grid,
        nan=0.0
    )

    plot_grid[
        lat_offset:lat_offset + len(lat_unique),
        lon_offset:lon_offset + len(lon_unique)
    ] = values

    smooth = gaussian_filter(
        plot_grid,
        sigma=1.0
    )

    factor = plot_upsample_factor(smooth.shape)

    if factor > 1 and smooth.shape[0] > 1 and smooth.shape[1] > 1:
        smooth = zoom(
            smooth,
            factor,
            order=3,
            mode="nearest"
        )
        smooth = gaussian_filter(
            smooth,
            sigma=0.8
        )

        plot_lats = np.linspace(
            plot_lats[0],
            plot_lats[-1],
            smooth.shape[0]
        )
        plot_lons = np.linspace(
            plot_lons[0],
            plot_lons[-1],
            smooth.shape[1]
        )

    smooth = np.clip(
        smooth,
        0.0,
        None
    )

    smooth = np.ma.masked_where(
        smooth <= MIN_VISIBLE_OBSCURATION,
        smooth
    )

    Lon, Lat = np.meshgrid(
        plot_lons,
        plot_lats
    )

    return Lon, Lat, smooth


def plot_obscuration_map(
        points,
        title,
        output="obscuration.png",
        central_path=None,
        max_point=None,
        eclipse_type=None,
        eclipse_data=None,
):
    if not points:
        print("[WARN] Nenhum ponto para plotar.")
        return
    lats = np.array([p[0] for p in points])
    lons = np.array([p[1] for p in points])
    values = np.array([p[2] for p in points])

    max_obsc = np.nanmax(values)

    lat_unique = np.unique(lats)
    lon_unique = np.unique(lons)

    lat_unique.sort()
    lon_unique.sort()

    grid = np.full(
        (len(lat_unique), len(lon_unique)),
        np.nan
    )

    lat_index = {
        lat: i
        for i, lat in enumerate(lat_unique)
    }

    lon_index = {
        lon: j
        for j, lon in enumerate(lon_unique)
    }

    for lat, lon, v in points:
        grid[
            lat_index[lat],
            lon_index[lon]
        ] = v

    Lon, Lat, smooth = build_smooth_plot_grid(
        lat_unique,
        lon_unique,
        grid
    )
    fig = plt.figure(figsize=(16, 8))

    use_cartopy = ccrs is not None and cfeature is not None

    if use_cartopy:
        ax = plt.axes(
            projection=ccrs.PlateCarree()
        )

        ax.set_global()

        ax.set_facecolor("#a9cce3")

        ax.add_feature(
            cfeature.LAND,
            facecolor="#f4f1de",
            edgecolor="none",
            zorder=0
        )

        ax.stock_img()

        ax.add_feature(
            cfeature.COASTLINE.with_scale("50m"),
            linewidth=0.8,
            edgecolor="#2f2f2f",
            zorder=4
        )

        ax.add_feature(
            cfeature.BORDERS.with_scale("50m"),
            linewidth=0.4,
            edgecolor="#555555",
            alpha=0.7,
            zorder=4
        )

        ax.gridlines(
            draw_labels=False,
            linewidth=0.3,
            color="gray",
            alpha=0.3,
            linestyle="--"
        )

        map_transform = {
            "transform": ccrs.PlateCarree()
        }

    else:
        ax = plt.axes()
        ax.set_facecolor("#a9cce3")
        add_plain_map_features(ax)
        ax.set_xlim(-180, 180)
        ax.set_ylim(-90, 90)
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        ax.grid(
            linewidth=0.3,
            color="gray",
            alpha=0.3,
            linestyle="--"
        )
        map_transform = {}

        print(
            "[WARN] Cartopy indisponivel. "
            "Usando fallback Natural Earth."
        )
    cmap, norm, levels, labels = (
        get_obscuration_colormap(max_obsc)
    )

    ax.contourf(
        Lon,
        Lat,
        smooth,
        levels=levels,
        cmap=cmap,
        norm=norm,
        alpha=0.85,
        antialiased=True,
        zorder=2,
        **map_transform,
    )

    contour_levels = [
        level
        for level in levels[1:]
        if level < max_obsc
    ]

    if contour_levels:
        ax.contour(
            Lon,
            Lat,
            smooth,
            levels=contour_levels,
            colors="black",
            linewidths=0.45,
            alpha=0.35,
            antialiased=True,
            zorder=3,
            **map_transform,
        )
    if central_path and len(central_path) > 1:

        segments = []
        current = [central_path[0]]

        for prev, curr in zip(
                central_path[:-1],
                central_path[1:]
        ):

            if abs(curr[1] - prev[1]) > 180:
                segments.append(current)
                current = [curr]
            else:
                current.append(curr)

        segments.append(current)

        for seg in segments:
            ax.plot(
                [p[1] for p in seg],
                [p[0] for p in seg],
                color="black",
                linewidth=0.6,
                zorder=6,
                **map_transform,
            )
    if max_point:

        lat_m, lon_m, _ = max_point

        if eclipse_type == "Total":
            marker = "*"
            color = "#0033cc"

        elif eclipse_type == "Anular":
            marker = "o"
            color = "#ff6600"

        else:
            marker = "o"
            color = "white"

        ax.scatter(
            lon_m,
            lat_m,
            s=220,
            marker=marker,
            color=color,
            edgecolors="black",
            linewidth=1.2,
            zorder=7,
            **map_transform,
        )
    if (
            eclipse_data is not None
            and
            max_point is not None
    ):
        lat_m, lon_m, _ = max_point

        corner = best_corner_position(
            max_point
        )

        positions = {
            "upper_left":
                (0.03, 0.97, "left", "top"),

            "upper_right":
                (0.97, 0.97, "right", "top"),

            "lower_left":
                (0.03, 0.03, "left", "bottom"),

            "lower_right":
                (0.97, 0.03, "right", "bottom"),
        }

        x, y, ha, va = positions[corner]

        label_width = 9

        info_text = (
            f"{'Tipo':<{label_width}}: {eclipse_data['type']}\n"
            f"{'Magnitude':<{label_width}}: {eclipse_data['magnitude']:.4f}\n"
            f"{'C1':<{label_width}}: {format_time(eclipse_data['C1'])} UTC\n"
            f"{'C2':<{label_width}}: {format_time(eclipse_data['C2'])} UTC\n"
            f"{'MAX':<{label_width}}: {format_time(eclipse_data['MAX'])} UTC\n"
            f"{'C3':<{label_width}}: {format_time(eclipse_data['C3'])} UTC\n"
            f"{'C4':<{label_width}}: {format_time(eclipse_data['C4'])} UTC\n"
            f"{'Dur. Tot.':<{label_width}}: "
            f"{duration_str(eclipse_data['C2'], eclipse_data['C3'])}\n"
            f"{'Máximo':<{label_width}}: "
            f"{lat_m:.2f}°, {lon_m:.2f}°"
        )

        ax.text(
            x,
            y,
            info_text,
            transform=ax.transAxes,
            fontsize=10,
            fontfamily="monospace",
            horizontalalignment=ha,
            verticalalignment=va,
            multialignment="left",
            bbox=dict(
                boxstyle="round",
                facecolor="white",
                alpha=0.92,
                edgecolor="black"
            ),
            zorder=20,
        )
    sm = plt.cm.ScalarMappable(
        cmap=cmap,
        norm=norm
    )

    sm.set_array([])

    cb = plt.colorbar(
        sm,
        ax=ax,
        orientation="horizontal",
        fraction=0.04,
        pad=0.05,
        aspect=30,
    )

    tick_positions = [
        (levels[i] + levels[i + 1]) / 2
        for i in range(len(levels) - 1)
    ]

    cb.set_ticks(tick_positions)
    cb.set_ticklabels(labels)

    cb.set_label(
        "Obscuração do Sol"
    )

    ax.set_title(
        title,
        fontsize=17,
        fontweight="bold"
    )

    plt.savefig(
        output,
        dpi=1200,
        bbox_inches="tight"
    )

    plt.close()

    print(
        f"Mapa salvo em: {output}"
    )
