from matplotlib.colors import BoundaryNorm, ListedColormap


def get_obscuration_colormap(max_obsc):
    if max_obsc < 1.0:

        colors = [
            "#ffffcc",
            "#ffeda0",
            "#feb24c",
            "#fd8d3c",
            "#f03b20",
            "#bd0026",
        ]

        levels = [
            0.0,
            0.10,
            0.25,
            0.50,
            0.75,
            0.90,
            1.0
        ]

        labels = [
            "<10%",
            "<25%",
            "<50%",
            "<75%",
            "<90%",
            "<99%"
        ]

    else:

        colors = [
            "#ffffcc",
            "#ffeda0",
            "#feb24c",
            "#fd8d3c",
            "#f03b20",
            "#bd0026",
            "#0033cc",
        ]

        levels = [
            0.0,
            0.10,
            0.25,
            0.50,
            0.75,
            0.90,
            0.999,
            1.0
        ]

        labels = [
            "<10%",
            "<25%",
            "<50%",
            "<75%",
            "<90%",
            "<99%",
            "100%"
        ]

    cmap = ListedColormap(colors)

    norm = BoundaryNorm(
        levels,
        cmap.N
    )

    return (
        cmap,
        norm,
        levels,
        labels
    )
