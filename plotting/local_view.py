from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Circle

from infrastructure.config import OUTPUT_DIR


def plot_local_sky_view(local, eclipse_date, output=None):
    if output is None:
        safe_date = str(eclipse_date).replace("/", "-")
        output = OUTPUT_DIR / f"Local_View_{safe_date}.png"
    else:
        output = Path(output)

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.set_facecolor("#dfefff")

    horizon_y = 0.24
    ax.add_line(
        Line2D([0.06, 0.94], [horizon_y, horizon_y], color="#444444", linewidth=2.2)
    )

    sun_x = 0.5
    moon_x = 0.5

    scale = 0.42 / 90.0
    sun_y = horizon_y + local["sun_alt_deg"] * scale
    moon_y = horizon_y + local["moon_alt_deg"] * scale

    sun_y = max(0.07, min(0.86, sun_y))
    moon_y = max(0.07, min(0.86, moon_y))

    sun_r = 0.085
    moon_r = 0.070

    overlap = max(0.0, min(1.0, local["max_obscuration"]))
    offset = 0.18 * (1.0 - overlap)
    moon_x = sun_x + offset

    ax.add_patch(
        Circle(
            (sun_x, sun_y),
            sun_r,
            facecolor="#ffcc33",
            edgecolor="#9a6a00",
            linewidth=2.0,
        )
    )
    ax.add_patch(
        Circle(
            (moon_x, moon_y),
            moon_r,
            facecolor="#f5f7fa",
            edgecolor="#222222",
            linewidth=2.0,
        )
    )

    ax.text(
        sun_x,
        sun_y + sun_r + 0.03,
        "Sol",
        ha="center",
        va="bottom",
        fontsize=13,
        weight="bold",
        color="#6c4a00",
    )
    ax.text(
        moon_x,
        moon_y + moon_r + 0.03,
        "Lua",
        ha="center",
        va="bottom",
        fontsize=12,
        color="#222222",
    )

    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)

    ax.set_title(
        f"Visão local do eclipse - {eclipse_date}",
        fontsize=15,
        pad=14,
    )

    ax.text(
        0.06,
        0.94,
        (
            f"C1 local: {local['C1_local']}\n"
            f"MAX local: {local['MAX_local']}\n"
            f"C4 local: {local['C4_local']}\n"
            f"Obscuracao: {local['max_obscuration']:.1%}"
        ),
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=11,
        family="monospace",
        bbox=dict(
            facecolor="white",
            edgecolor="#222222",
            alpha=0.9,
            boxstyle="round,pad=0.35",
        ),
    )

    fig.savefig(output, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return str(output)
