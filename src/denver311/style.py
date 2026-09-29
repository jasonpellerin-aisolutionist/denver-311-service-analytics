"""Chart style shared by the notebooks: navy, teal, slate, and blue only."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.collections import PatchCollection
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Polygon

from denver311 import FIGURES_DIR

NAVY = "#1e3a5f"
TEAL = "#0f766e"
BLUE = "#2563eb"
SLATE = "#64748b"
LIGHT = "#cbd5e1"
INK = "#0f172a"
BODY = "#334155"

SERIES = [NAVY, TEAL, BLUE, SLATE, "#5b8db8", "#5eada5", LIGHT]

# Sequential ramp from near-white to navy, and a diverging teal / white / navy ramp
# for indexes centered on a typical value.
SEQUENTIAL = LinearSegmentedColormap.from_list("slate_navy", ["#f1f5f9", "#94a3b8", NAVY])
DIVERGING = LinearSegmentedColormap.from_list("teal_navy", [TEAL, "#f8fafc", NAVY])

SOURCE_NOTE = (
    "Source: Denver Open Data Catalog, 311 Service Requests 2019-2025. Analysis: Jason Pellerin."
)


def apply() -> None:
    mpl.rcParams.update(
        {
            "figure.dpi": 110,
            "savefig.dpi": 200,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": LIGHT,
            "axes.labelcolor": BODY,
            "axes.titlecolor": INK,
            "axes.titlesize": 13,
            "axes.titleweight": "bold",
            "axes.titlelocation": "left",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.color": "#e2e8f0",
            "grid.linewidth": 0.8,
            "axes.prop_cycle": mpl.cycler(color=SERIES),
            "xtick.color": BODY,
            "ytick.color": BODY,
            "text.color": BODY,
            "font.family": "sans-serif",
            "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
            "legend.frameon": False,
        }
    )


def subtitle(ax: plt.Axes, text: str) -> None:
    ax.text(0, 1.02, text, transform=ax.transAxes, fontsize=10, color=SLATE, va="bottom")


def save(fig: plt.Figure, name: str, note: str = SOURCE_NOTE) -> Path:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.text(0.01, -0.01, note, fontsize=7.5, color=SLATE, ha="left", va="top")
    path = FIGURES_DIR / f"{name}.png"
    fig.savefig(path, bbox_inches="tight", pad_inches=0.25)
    return path


def plot_neighborhoods(ax: plt.Axes, geojson: Path, values: dict[int, float], cmap, norm) -> None:
    """Draw the 78 statistical neighborhoods colored by `values` (keyed by NBHD_ID)."""
    patches, colors = [], []
    for feature in json.loads(geojson.read_text())["features"]:
        nbhd_id = feature["properties"]["NBHD_ID"]
        geom = feature["geometry"]
        rings = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
        for polygon in rings:
            patches.append(Polygon(polygon[0], closed=True))
            value = values.get(nbhd_id)
            colors.append(cmap(norm(value)) if value is not None else "#f1f5f9")
    ax.add_collection(PatchCollection(patches, facecolor=colors, edgecolor="white", linewidth=0.6))
    ax.autoscale_view()
    ax.set_aspect(1 / 0.77)  # cos(39.7 degrees) keeps Denver from looking stretched
    ax.axis("off")
