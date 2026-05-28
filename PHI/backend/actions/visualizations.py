"""Data visualization module for J.A.R.V.I.S.

Generates charts, plots, and advanced data visualizations using matplotlib.
All images saved to static/images/ and returned as URLs.
"""

import asyncio
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

from backend.shared.config import settings

logger = logging.getLogger(__name__)

IMAGES_DIR = Path(__file__).resolve().parent / "static" / "images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
_BASE_URL = f"http://localhost:{settings.action_port}/static/images"

_THEMES = {
    "light": {"face":"white", "axes":"white", "grid":"#e0e0e0", "text":"#333333", "tick":"#555555", "title_weight":"bold"},
    "dark": {"face":"#1a1a2e", "axes":"#16213e", "grid":"#2a2a4a", "text":"#e0e0ff", "tick":"#a0a0c0", "title_weight":"bold"},
    "professional": {"face":"#ffffff", "axes":"#f8f9fa", "grid":"#dee2e6", "text":"#212529", "tick":"#495057", "title_weight":"semibold"},
    "colorblind": {"face":"white", "axes":"white", "grid":"#e0e0e0", "text":"#333333", "tick":"#555555", "title_weight":"bold"},
}

_PALETTES = {
    "default": ["#007AFF","#FF6B6B","#34C759","#FF9500","#AF52DE","#FF2D55","#5856D6","#00C7BE"],
    "pastel": ["#FFB3BA","#BAFFC9","#BAE1FF","#FFFFBA","#E8BAFF","#FFD9BA","#BAFFFA","#FFBAE1"],
    "vivid": ["#FF006E","#8338EC","#3A86FF","#FB5607","#FFBE0B","#00BBF9","#00F5D4","#9B5DE5"],
    "monochrome": ["#1a1a2e","#16213e","#0f3460","#e94560","#533483","#0b8457","#dddddd","#333333"],
    "warm": ["#FF6B35","#F7C59F","#EFEFD0","#004E71","#2B4162","#FA9F42","#E8D5B7","#C6A15B"],
    "cool": ["#004E71","#2B4162","#5B8FA8","#8EC3D0","#B5D6D6","#D4E7E8","#89CFF0","#A8D8EA"],
    "neon": ["#FF007F","#00FF41","#00FFFF","#FF00FF","#FFFF00","#FF6600","#7F00FF","#00FF7F"],
    "earth": ["#8B4513","#A0522D","#CD853F","#DEB887","#D2B48C","#BC8F8F","#6B8E23","#556B2F"],
}

def _apply_theme(ax, theme_name="light"):
    theme = _THEMES.get(theme_name, _THEMES["light"])
    ax.set_facecolor(theme["axes"])
    ax.figure.set_facecolor(theme["face"])
    ax.tick_params(colors=theme["tick"], labelsize=10)
    ax.xaxis.label.set_color(theme["text"])
    ax.yaxis.label.set_color(theme["text"])
    ax.title.set_color(theme["text"])
    for spine in ax.spines.values(): spine.set_color(theme["grid"])
    ax.grid(color=theme["grid"], alpha=0.5)

def _get_palette(name="default", n=8):
    colors = _PALETTES.get(name, _PALETTES["default"])
    return (colors * (n // len(colors) + 1))[:n]

def _check_matplotlib():
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        import matplotlib.ticker as mticker
        import matplotlib.patches as mpatches
        import matplotlib.path as mpath
        import numpy as np
        from matplotlib.colors import LinearSegmentedColormap, to_rgba
        from matplotlib.patches import FancyBboxPatch
        return plt, mdates, mticker, mpatches, np, LinearSegmentedColormap, to_rgba, FancyBboxPatch
    except ImportError:
        return None, None, None, None, None, None, None, None

def _save_plot(fig, name: str = None) -> str:
    filename = f"{name or uuid.uuid4().hex}.png"
    filepath = IMAGES_DIR / filename
    fig.savefig(filepath, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    logger.info(f"Saved plot: {filepath}")
    plt = __import__("matplotlib.pyplot", fromlist=["pyplot"])
    plt.close(fig)
    return f"{_BASE_URL}/{filename}"

# --- Helpers ---
def _exec_sync(fn):
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(None, fn)


async def plot_line(
    x: List,
    y: List,
    title: str = "Line Chart",
    xlabel: str = "X",
    ylabel: str = "Y",
    color: str = "#007AFF",
    filename: str = None,
    theme: str = "light",
    line_width: float = 2,
    marker: str = "o",
    marker_size: int = 4,
    dash_style: str = "solid",
    fill_area: bool = False,
    show_grid: bool = True,
) -> str:
    """Create and save a line chart with styling options."""
    plt, mdates, mticker, mpatches, np, _, _, _ = _check_matplotlib()
    if plt is None: return "Chart unavailable: matplotlib not installed"
    styles = {"solid":"-", "dashed":"--", "dotted":":", "dashdot":"-."}
    def _draw():
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(x, y, color=color, linewidth=line_width, marker=marker, markersize=marker_size, linestyle=styles.get(dash_style, "-"))
        if fill_area: ax.fill_between(range(len(x)), y, alpha=0.15, color=color)
        ax.set_title(title, fontsize=14, fontweight="bold")
        ax.set_xlabel(xlabel); ax.set_ylabel(ylabel)
        _apply_theme(ax, theme)
        if show_grid: ax.grid(True, alpha=0.3)
        fig.tight_layout()
        return _save_plot(fig, filename)
    return await _exec_sync(_draw)


async def plot_multi_line(
    x: List,
    y_series: Dict[str, List[float]],
    title: str = "Multi-Line Chart",
    xlabel: str = "X",
    ylabel: str = "Y",
    filename: str = None,
    theme: str = "light",
    palette: str = "default",
) -> str:
    """Create a multi-series line chart."""
    plt, _, _, _, np, _, _, _ = _check_matplotlib()
    if plt is None: return "Chart unavailable: matplotlib not installed"
    colors = _get_palette(palette, len(y_series))
    markers = ["o","s","^","D","v","<",">","p","h","*"]
    def _draw():
        fig, ax = plt.subplots(figsize=(12, 6))
        for i, (name, vals) in enumerate(y_series.items()):
            ax.plot(x, vals, color=colors[i], linewidth=2, marker=markers[i % len(markers)], markersize=4, label=name)
        ax.set_title(title, fontsize=14, fontweight="bold")
        ax.set_xlabel(xlabel); ax.set_ylabel(ylabel)
        ax.legend(fontsize=10)
        _apply_theme(ax, theme)
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        return _save_plot(fig, filename)
    return await _exec_sync(_draw)


async def plot_bar(
    categories: List[str],
    values: List[float],
    title: str = "Bar Chart",
    xlabel: str = "",
    ylabel: str = "",
    color: str = "#34C759",
    filename: str = None,
    theme: str = "light",
    horizontal: bool = False,
    show_values: bool = True,
) -> str:
    """Create and save a bar chart (vertical or horizontal)."""
    plt, _, _, _, np, _, _, _ = _check_matplotlib()
    if plt is None: return "Chart unavailable: matplotlib not installed"
    def _draw():
        fig, ax = plt.subplots(figsize=(10, 5))
        if horizontal:
            bars = ax.barh(categories, values, color=color, alpha=0.85, edgecolor="white")
            if show_values:
                for bar in bars:
                    ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height()/2,
                            f"{bar.get_width():.1f}", ha="left", va="center", fontsize=9)
            ax.set_xlabel(ylabel or "Value")
            ax.set_ylabel(xlabel or "Category")
        else:
            bars = ax.bar(categories, values, color=color, alpha=0.85, edgecolor="white")
            if show_values:
                for bar in bars:
                    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                            f"{bar.get_height():.1f}", ha="center", va="bottom", fontsize=9)
            ax.set_xlabel(xlabel); ax.set_ylabel(ylabel)
        ax.set_title(title, fontsize=14, fontweight="bold")
        _apply_theme(ax, theme)
        ax.grid(True, alpha=0.3, axis="y" if not horizontal else "x")
        fig.tight_layout()
        return _save_plot(fig, filename)
    return await _exec_sync(_draw)


async def plot_grouped_bar(
    categories: List[str],
    series: Dict[str, List[float]],
    title: str = "Grouped Bar Chart",
    xlabel: str = "",
    ylabel: str = "",
    filename: str = None,
    theme: str = "light",
    palette: str = "default",
) -> str:
    """Create a grouped bar chart with multiple series."""
    plt, _, _, _, np, _, _, _ = _check_matplotlib()
    if plt is None: return "Chart unavailable: matplotlib not installed"
    colors = _get_palette(palette, len(series))
    def _draw():
        fig, ax = plt.subplots(figsize=(10, 5))
        x = np.arange(len(categories))
        n = len(series)
        width = 0.8 / n
        for i, (name, vals) in enumerate(series.items()):
            offset = (i - (n-1)/2) * width
            bars = ax.bar(x + offset, vals, width, label=name, color=colors[i], alpha=0.85, edgecolor="white")
            for bar in bars:
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                        f"{bar.get_height():.1f}", ha="center", va="bottom", fontsize=7)
        ax.set_title(title, fontsize=14, fontweight="bold")
        ax.set_xlabel(xlabel); ax.set_ylabel(ylabel)
        ax.set_xticks(x); ax.set_xticklabels(categories, rotation=30, ha="right")
        ax.legend(fontsize=10)
        _apply_theme(ax, theme)
        ax.grid(True, alpha=0.3, axis="y")
        fig.tight_layout()
        return _save_plot(fig, filename)
    return await _exec_sync(_draw)


async def plot_stacked_bar(
    categories: List[str],
    series: Dict[str, List[float]],
    title: str = "Stacked Bar Chart",
    xlabel: str = "",
    ylabel: str = "",
    filename: str = None,
    theme: str = "light",
    palette: str = "default",
) -> str:
    """Create a stacked bar chart."""
    plt, _, _, _, np, _, _, _ = _check_matplotlib()
    if plt is None: return "Chart unavailable: matplotlib not installed"
    colors = _get_palette(palette, len(series))
    def _draw():
        fig, ax = plt.subplots(figsize=(10, 5))
        x = np.arange(len(categories))
        bottom = np.zeros(len(categories))
        for i, (name, vals) in enumerate(series.items()):
            bars = ax.bar(x, vals, 0.7, bottom=bottom, label=name, color=colors[i], alpha=0.85, edgecolor="white")
            bottom += np.array(vals)
        ax.set_title(title, fontsize=14, fontweight="bold")
        ax.set_xlabel(xlabel); ax.set_ylabel(ylabel)
        ax.set_xticks(x); ax.set_xticklabels(categories, rotation=30, ha="right")
        ax.legend(fontsize=10)
        _apply_theme(ax, theme)
        ax.grid(True, alpha=0.3, axis="y")
        fig.tight_layout()
        return _save_plot(fig, filename)
    return await _exec_sync(_draw)


async def plot_pie(
    labels: List[str],
    values: List[float],
    title: str = "Pie Chart",
    filename: str = None,
    theme: str = "light",
    palette: str = "default",
    explode: bool = False,
    donut: bool = False,
    show_percent: bool = True,
) -> str:
    """Create and save a pie or donut chart."""
    plt, _, _, _, np, _, _, _ = _check_matplotlib()
    if plt is None: return "Chart unavailable: matplotlib not installed"
    colors = _get_palette(palette, len(labels))
    def _draw():
        fig, ax = plt.subplots(figsize=(8, 8))
        ex = [0.05]*len(labels) if explode else None
        wedges, texts, autotexts = ax.pie(
            values, labels=labels, autopct="%1.1f%%" if show_percent else None,
            colors=colors, startangle=90, explode=ex,
            textprops={"fontsize": 10},
        )
        if donut:
            centre = plt.Circle((0,0), 0.6, fc=_THEMES.get(theme, _THEMES["light"])["face"])
            ax.add_artist(centre)
        ax.set_title(title, fontsize=14, fontweight="bold")
        _apply_theme(ax, theme)
        fig.tight_layout()
        return _save_plot(fig, filename)
    return await _exec_sync(_draw)


async def plot_scatter(
    x: List[float],
    y: List[float],
    title: str = "Scatter Plot",
    xlabel: str = "X",
    ylabel: str = "Y",
    filename: str = None,
    theme: str = "light",
    color: str = "#007AFF",
    size: int = 50,
    alpha: float = 0.6,
    regression_line: bool = False,
) -> str:
    """Create and save a scatter plot with optional regression line."""
    plt, _, _, _, np, _, _, _ = _check_matplotlib()
    if plt is None: return "Chart unavailable: matplotlib not installed"
    def _draw():
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.scatter(x, y, c=color, alpha=alpha, s=size, edgecolors="white", linewidth=0.5)
        if regression_line and len(x) > 1:
            m, b = np.polyfit(x, y, 1)
            x_sorted = np.linspace(min(x), max(x), 100)
            ax.plot(x_sorted, m * x_sorted + b, color="#FF6B6B", linewidth=2, label=f"y = {m:.2f}x + {b:.2f}")
            ax.legend(fontsize=10)
        ax.set_title(title, fontsize=14, fontweight="bold")
        ax.set_xlabel(xlabel); ax.set_ylabel(ylabel)
        _apply_theme(ax, theme)
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        return _save_plot(fig, filename)
    return await _exec_sync(_draw)


async def plot_bubble(
    x: List[float],
    y: List[float],
    sizes: List[float],
    labels: Optional[List[str]] = None,
    title: str = "Bubble Chart",
    xlabel: str = "X",
    ylabel: str = "Y",
    filename: str = None,
    theme: str = "light",
    palette: str = "default",
    alpha: float = 0.6,
) -> str:
    """Create a bubble chart (scatter with variable point sizes)."""
    plt, _, _, _, np, _, _, _ = _check_matplotlib()
    if plt is None: return "Chart unavailable: matplotlib not installed"
    colors = _get_palette(palette)
    def _draw():
        fig, ax = plt.subplots(figsize=(10, 7))
        sizes_scaled = [max(20, min(500, s*10)) for s in sizes]
        sc = ax.scatter(x, y, s=sizes_scaled, c=range(len(x)), cmap="viridis", alpha=alpha, edgecolors="white", linewidth=0.5)
        if labels:
            for i, label in enumerate(labels):
                ax.annotate(label, (x[i], y[i]), fontsize=8, alpha=0.8, ha="center", va="bottom")
        cbar = plt.colorbar(sc, ax=ax, shrink=0.8)
        cbar.set_label("Index", fontsize=10)
        ax.set_title(title, fontsize=14, fontweight="bold")
        ax.set_xlabel(xlabel); ax.set_ylabel(ylabel)
        _apply_theme(ax, theme)
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        return _save_plot(fig, filename)
    return await _exec_sync(_draw)


async def plot_area(
    x: List,
    y_series: Dict[str, List[float]],
    title: str = "Area Chart",
    xlabel: str = "X",
    ylabel: str = "Y",
    filename: str = None,
    theme: str = "light",
    palette: str = "default",
    stacked: bool = True,
) -> str:
    """Create a stacked or overlapping area chart."""
    plt, _, _, _, np, _, _, _ = _check_matplotlib()
    if plt is None: return "Chart unavailable: matplotlib not installed"
    colors = _get_palette(palette, len(y_series))
    def _draw():
        fig, ax = plt.subplots(figsize=(12, 6))
        if stacked:
            ax.stackplot(range(len(x)), list(y_series.values()), labels=list(y_series.keys()), colors=colors, alpha=0.7)
            ax.set_xticks(range(len(x)))
            ax.set_xticklabels(x, rotation=30, ha="right")
        else:
            for i, (name, vals) in enumerate(y_series.items()):
                ax.fill_between(range(len(x)), vals, alpha=0.25, color=colors[i], label=name)
                ax.plot(range(len(x)), vals, color=colors[i], linewidth=1.5)
        ax.set_title(title, fontsize=14, fontweight="bold")
        ax.set_xlabel(xlabel); ax.set_ylabel(ylabel)
        ax.legend(fontsize=10)
        _apply_theme(ax, theme)
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        return _save_plot(fig, filename)
    return await _exec_sync(_draw)


async def plot_histogram(
    data: List[float],
    bins: int = 20,
    title: str = "Histogram",
    xlabel: str = "Value",
    ylabel: str = "Frequency",
    filename: str = None,
    theme: str = "light",
    color: str = "#007AFF",
    kde: bool = False,
    cumulative: bool = False,
    show_stats: bool = False,
) -> str:
    """Create and save a histogram with optional KDE overlay and stats."""
    plt, _, _, _, np, _, _, _ = _check_matplotlib()
    if plt is None: return "Chart unavailable: matplotlib not installed"
    def _draw():
        fig, ax = plt.subplots(figsize=(10, 5))
        n, bins_arr, patches = ax.hist(data, bins=bins, color=color, alpha=0.7, edgecolor="white", linewidth=0.5,
                                        density=False, cumulative=cumulative)
        if kde and len(data) > 1:
            from scipy.stats import gaussian_kde
            try:
                kernel = gaussian_kde(data)
                xs = np.linspace(min(data), max(data), 200)
                ax2 = ax.twinx()
                ax2.plot(xs, kernel(xs), color="#FF6B6B", linewidth=2, label="KDE")
                ax2.set_ylabel("Density", color="#FF6B6B", fontsize=10)
                ax2.tick_params(axis="y", colors="#FF6B6B")
            except: pass
        if show_stats and data:
            stats_text = f"n={len(data)}\nμ={np.mean(data):.2f}\nσ={np.std(data):.2f}\nmed={np.median(data):.2f}"
            ax.text(0.95, 0.95, stats_text, transform=ax.transAxes, fontsize=9, verticalalignment="top", horizontalalignment="right",
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8))
        ax.set_title(title, fontsize=14, fontweight="bold")
        ax.set_xlabel(xlabel); ax.set_ylabel(ylabel)
        _apply_theme(ax, theme)
        ax.grid(True, alpha=0.3, axis="y")
        fig.tight_layout()
        return _save_plot(fig, filename)
    return await _exec_sync(_draw)


async def plot_density(
    data_series: Dict[str, List[float]],
    title: str = "Density Plot",
    xlabel: str = "Value",
    filename: str = None,
    theme: str = "light",
    palette: str = "default",
    fill: bool = True,
) -> str:
    """Create KDE density plots for one or more data series."""
    plt, _, _, _, np, _, _, _ = _check_matplotlib()
    if plt is None: return "Chart unavailable: matplotlib not installed"
    colors = _get_palette(palette, len(data_series))
    def _draw():
        from scipy.stats import gaussian_kde
        fig, ax = plt.subplots(figsize=(10, 6))
        for i, (name, vals) in enumerate(data_series.items()):
            if len(vals) < 2: continue
            kernel = gaussian_kde(vals)
            xs = np.linspace(min(vals), max(vals), 300)
            ax.plot(xs, kernel(xs), color=colors[i], linewidth=2, label=name)
            if fill: ax.fill_between(xs, kernel(xs), alpha=0.15, color=colors[i])
        ax.set_title(title, fontsize=14, fontweight="bold")
        ax.set_xlabel(xlabel); ax.set_ylabel("Density")
        ax.legend(fontsize=10)
        _apply_theme(ax, theme)
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        return _save_plot(fig, filename)
    return await _exec_sync(_draw)


async def plot_box(
    data_series: Dict[str, List[float]],
    title: str = "Box Plot",
    ylabel: str = "Value",
    filename: str = None,
    theme: str = "light",
    palette: str = "default",
    show_outliers: bool = True,
    show_means: bool = False,
    horizontal: bool = False,
) -> str:
    """Create a box plot for one or more data series."""
    plt, _, _, _, np, _, _, _ = _check_matplotlib()
    if plt is None: return "Chart unavailable: matplotlib not installed"
    colors = _get_palette(palette, len(data_series))
    def _draw():
        fig, ax = plt.subplots(figsize=(10, 6))
        labels = list(data_series.keys())
        values_list = list(data_series.values())
        bp = ax.boxplot(values_list, labels=labels, patch_artist=True, showmeans=show_means,
                         sym="o" if show_outliers else "", whis=1.5)
        for patch, color in zip(bp["boxes"], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)
        for median in bp["medians"]:
            median.set_color("#FF6B6B")
            median.set_linewidth(2)
        ax.set_title(title, fontsize=14, fontweight="bold")
        ax.set_ylabel(ylabel)
        _apply_theme(ax, theme)
        ax.grid(True, alpha=0.3, axis="y")
        fig.tight_layout()
        return _save_plot(fig, filename)
    return await _exec_sync(_draw)


async def plot_violin(
    data_series: Dict[str, List[float]],
    title: str = "Violin Plot",
    ylabel: str = "Value",
    filename: str = None,
    theme: str = "light",
    palette: str = "default",
    show_medians: bool = True,
) -> str:
    """Create a violin plot showing distribution shape."""
    plt, _, _, _, np, _, _, _ = _check_matplotlib()
    if plt is None: return "Chart unavailable: matplotlib not installed"
    colors = _get_palette(palette, len(data_series))
    def _draw():
        fig, ax = plt.subplots(figsize=(10, 6))
        labels = list(data_series.keys())
        values_list = list(data_series.values())
        parts = ax.violinplot(values_list, showmedians=show_medians, showextrema=True)
        ax.set_xticks(range(1, len(labels) + 1)); ax.set_xticklabels(labels)
        for i, pc in enumerate(parts["bodies"]):
            pc.set_facecolor(colors[i % len(colors)])
            pc.set_alpha(0.7)
            pc.set_edgecolor("white")
        ax.set_title(title, fontsize=14, fontweight="bold")
        ax.set_ylabel(ylabel)
        _apply_theme(ax, theme)
        ax.grid(True, alpha=0.3, axis="y")
        fig.tight_layout()
        return _save_plot(fig, filename)
    return await _exec_sync(_draw)


async def plot_heatmap(
    matrix: List[List[float]],
    row_labels: Optional[List[str]] = None,
    col_labels: Optional[List[str]] = None,
    title: str = "Heatmap",
    filename: str = None,
    theme: str = "light",
    cmap: str = "viridis",
    annotate: bool = True,
    fmt: str = ".2f",
) -> str:
    """Create a heatmap / correlation matrix."""
    plt, _, _, _, np, _, _, _ = _check_matplotlib()
    if plt is None: return "Chart unavailable: matplotlib not installed"
    def _draw():
        import numpy as np
        data = np.array(matrix, dtype=float)
        fig, ax = plt.subplots(figsize=(max(6, len(col_labels or data[0])*0.8), max(5, len(row_labels or data)*0.7)))
        im = ax.imshow(data, cmap=cmap, aspect="auto")
        cbar = plt.colorbar(im, ax=ax, shrink=0.8)
        cbar.set_label("Value", fontsize=10)
        if annotate:
            for i in range(data.shape[0]):
                for j in range(data.shape[1]):
                    ax.text(j, i, f"{data[i,j]:{fmt}}", ha="center", va="center", fontsize=9,
                            color="white" if abs(data[i,j]) > data.max()*0.5 else "black")
        if row_labels: ax.set_yticks(range(len(row_labels))); ax.set_yticklabels(row_labels)
        if col_labels: ax.set_xticks(range(len(col_labels))); ax.set_xticklabels(col_labels, rotation=45, ha="right")
        ax.set_title(title, fontsize=14, fontweight="bold")
        _apply_theme(ax, theme)
        fig.tight_layout()
        return _save_plot(fig, filename)
    return await _exec_sync(_draw)


async def plot_correlation_matrix(
    data: Dict[str, List[float]],
    title: str = "Correlation Matrix",
    filename: str = None,
    theme: str = "light",
) -> str:
    """Create a correlation matrix heatmap from a dict of variables."""
    plt, _, _, _, np, _, _, _ = _check_matplotlib()
    if plt is None: return "Chart unavailable: matplotlib not installed"
    def _draw():
        import numpy as np
        import pandas as pd
        df = pd.DataFrame(data)
        corr = df.corr().values
        labels = list(data.keys())
        fig, ax = plt.subplots(figsize=(max(6, len(labels)*0.9), max(5, len(labels)*0.8)))
        im = ax.imshow(corr, cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")
        cbar = plt.colorbar(im, ax=ax, shrink=0.8)
        cbar.set_label("Correlation", fontsize=10)
        for i in range(len(labels)):
            for j in range(len(labels)):
                ax.text(j, i, f"{corr[i,j]:.2f}", ha="center", va="center", fontsize=9,
                        color="white" if abs(corr[i,j]) > 0.5 else "black")
        ax.set_xticks(range(len(labels))); ax.set_yticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=45, ha="right"); ax.set_yticklabels(labels)
        ax.set_title(title, fontsize=14, fontweight="bold")
        _apply_theme(ax, theme)
        fig.tight_layout()
        return _save_plot(fig, filename)
    return await _exec_sync(_draw)


async def plot_radar(
    categories: List[str],
    series: Dict[str, List[float]],
    title: str = "Radar Chart",
    filename: str = None,
    theme: str = "light",
    palette: str = "default",
) -> str:
    """Create a radar / spider chart for comparing multiple entities."""
    plt, _, _, _, np, _, _, _ = _check_matplotlib()
    if plt is None: return "Chart unavailable: matplotlib not installed"
    colors = _get_palette(palette, len(series))
    def _draw():
        import numpy as np
        n = len(categories)
        angles = np.linspace(0, 2*np.pi, n, endpoint=False).tolist()
        angles += angles[:1]
        fig, ax = plt.subplots(figsize=(8, 8), subplot_kw={"projection":"polar"})
        for i, (name, vals) in enumerate(series.items()):
            values = vals + vals[:1]
            ax.plot(angles, values, color=colors[i], linewidth=2, label=name)
            ax.fill(angles, values, color=colors[i], alpha=0.1)
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(categories, fontsize=10)
        ax.set_title(title, fontsize=14, fontweight="bold", pad=20)
        ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.0), fontsize=10)
        _apply_theme(ax, theme)
        fig.tight_layout()
        return _save_plot(fig, filename)
    return await _exec_sync(_draw)


async def plot_error_bar(
    categories: List[str],
    means: List[float],
    errors: List[float],
    title: str = "Error Bar Chart",
    xlabel: str = "",
    ylabel: str = "",
    filename: str = None,
    theme: str = "light",
    color: str = "#007AFF",
) -> str:
    """Create a bar chart with error bars."""
    plt, _, _, _, np, _, _, _ = _check_matplotlib()
    if plt is None: return "Chart unavailable: matplotlib not installed"
    def _draw():
        fig, ax = plt.subplots(figsize=(10, 5))
        x = np.arange(len(categories))
        ax.bar(x, means, yerr=errors, color=color, alpha=0.8, capsize=5, edgecolor="white")
        ax.set_xticks(x); ax.set_xticklabels(categories, rotation=30, ha="right")
        ax.set_title(title, fontsize=14, fontweight="bold")
        ax.set_xlabel(xlabel); ax.set_ylabel(ylabel)
        _apply_theme(ax, theme)
        ax.grid(True, alpha=0.3, axis="y")
        fig.tight_layout()
        return _save_plot(fig, filename)
    return await _exec_sync(_draw)


async def plot_3d_surface(
    x: List[float],
    y: List[float],
    z_matrix: List[List[float]],
    title: str = "3D Surface Plot",
    xlabel: str = "X",
    ylabel: str = "Y",
    zlabel: str = "Z",
    filename: str = None,
    theme: str = "light",
    cmap: str = "viridis",
) -> str:
    """Create a 3D surface plot from grid data."""
    plt, _, _, _, np, _, _, _ = _check_matplotlib()
    if plt is None: return "Chart unavailable: matplotlib not installed"
    def _draw():
        from mpl_toolkits.mplot3d import Axes3D
        import numpy as np
        X, Y = np.meshgrid(x, y)
        Z = np.array(z_matrix, dtype=float)
        fig = plt.figure(figsize=(12, 8))
        ax = fig.add_subplot(111, projection="3d")
        surf = ax.plot_surface(X, Y, Z, cmap=cmap, alpha=0.9, linewidth=0, antialiased=True)
        fig.colorbar(surf, ax=ax, shrink=0.6, aspect=20)
        ax.set_title(title, fontsize=14, fontweight="bold")
        ax.set_xlabel(xlabel); ax.set_ylabel(ylabel); ax.set_zlabel(zlabel)
        fig.tight_layout()
        return _save_plot(fig, filename)
    return await _exec_sync(_draw)


async def plot_contour(
    x: List[float],
    y: List[float],
    z_matrix: List[List[float]],
    title: str = "Contour Plot",
    xlabel: str = "X",
    ylabel: str = "Y",
    filename: str = None,
    theme: str = "light",
    cmap: str = "viridis",
    filled: bool = True,
) -> str:
    """Create a contour or filled contour plot."""
    plt, _, _, _, np, _, _, _ = _check_matplotlib()
    if plt is None: return "Chart unavailable: matplotlib not installed"
    def _draw():
        import numpy as np
        X, Y = np.meshgrid(x, y)
        Z = np.array(z_matrix, dtype=float)
        fig, ax = plt.subplots(figsize=(10, 7))
        if filled:
            cs = ax.contourf(X, Y, Z, levels=20, cmap=cmap, alpha=0.8)
        else:
            cs = ax.contour(X, Y, Z, levels=15, cmap=cmap, linewidths=1.5)
            ax.clabel(cs, inline=True, fontsize=9)
        fig.colorbar(cs, ax=ax, shrink=0.8)
        ax.set_title(title, fontsize=14, fontweight="bold")
        ax.set_xlabel(xlabel); ax.set_ylabel(ylabel)
        _apply_theme(ax, theme)
        fig.tight_layout()
        return _save_plot(fig, filename)
    return await _exec_sync(_draw)


async def plot_waterfall(
    categories: List[str],
    values: List[float],
    title: str = "Waterfall Chart",
    filename: str = None,
    theme: str = "light",
) -> str:
    """Create a waterfall / bridge chart showing cumulative changes."""
    plt, _, _, _, np, _, _, _ = _check_matplotlib()
    if plt is None: return "Chart unavailable: matplotlib not installed"
    def _draw():
        import numpy as np
        fig, ax = plt.subplots(figsize=(12, 6))
        n = len(values)
        cumulative = [0]
        for v in values[:-1]: cumulative.append(cumulative[-1] + v)
        cumulative[-1] = 0
        x = np.arange(n)
        bottoms = [min(0, values[0])] + [min(cumulative[i], cumulative[i]+values[i]) for i in range(1, n-1)] + [0]
        heights = [abs(values[0])] + [abs(values[i]) for i in range(1, n-1)] + [abs(values[-1])]
        colors = []
        for i, v in enumerate(values):
            if i == 0: colors.append("#007AFF")
            elif i == n-1: colors.append("#34C759")
            elif v >= 0: colors.append("#34C759")
            else: colors.append("#FF6B6B")
        ax.bar(x, heights, bottom=bottoms, color=colors, alpha=0.85, edgecolor="white", width=0.6)
        connector_x = []
        connector_y = []
        running = 0
        for i, v in enumerate(values):
            if i < n-1:
                top = running + v if i > 0 else v
                running = top
                ax.plot([i+0.3, i+0.7], [top, top], color="#999", linewidth=1)
        for i, v in enumerate(values):
            total = sum(values[:i+1]) if i < n-1 else sum(values)
            ax.text(i, (bottoms[i] if i != 0 else 0) + heights[i]/2, f"{v:+.1f}" if i != n-1 else f"{sum(values):.1f}",
                    ha="center", va="center", fontsize=9, fontweight="bold", color="white")
        ax.set_xticks(x); ax.set_xticklabels(categories, rotation=30, ha="right")
        ax.set_title(title, fontsize=14, fontweight="bold")
        _apply_theme(ax, theme)
        ax.grid(True, alpha=0.3, axis="y")
        fig.tight_layout()
        return _save_plot(fig, filename)
    return await _exec_sync(_draw)


async def plot_candlestick(
    dates: List[str],
    opens: List[float],
    highs: List[float],
    lows: List[float],
    closes: List[float],
    title: str = "Candlestick Chart",
    filename: str = None,
    theme: str = "light",
) -> str:
    """Create a candlestick chart for financial data."""
    plt, mdates, _, _, np, _, _, _ = _check_matplotlib()
    if plt is None: return "Chart unavailable: matplotlib not installed"
    def _draw():
        import numpy as np
        parsed = [datetime.fromisoformat(d) if isinstance(d, str) else d for d in dates]
        fig, ax = plt.subplots(figsize=(14, 7))
        xs = np.arange(len(parsed))
        for i, (o, h, l, c) in enumerate(zip(opens, highs, lows, closes)):
            color = "#34C759" if c >= o else "#FF6B6B"
            ax.plot([i, i], [l, h], color=color, linewidth=1)
            ax.plot([i-0.2, i+0.2], [o, o], color=color, linewidth=2.5)
            ax.plot([i-0.2, i+0.2], [c, c], color=color, linewidth=2.5)
        ax.set_xticks(range(len(parsed)))
        ax.set_xticklabels([d[:10] for d in dates], rotation=45, ha="right", fontsize=8)
        ax.set_title(title, fontsize=14, fontweight="bold")
        ax.set_ylabel("Price ($)")
        _apply_theme(ax, theme)
        ax.grid(True, alpha=0.3)
        green = plt.Rectangle((0,0),1,1,fc="#34C759", alpha=0.7); red = plt.Rectangle((0,0),1,1,fc="#FF6B6B", alpha=0.7)
        ax.legend([green, red], ["Up","Down"], loc="upper left", fontsize=10)
        fig.tight_layout()
        return _save_plot(fig, filename)
    return await _exec_sync(_draw)


async def plot_network(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    title: str = "Network Graph",
    filename: str = None,
    theme: str = "light",
) -> str:
    """Create a network / force-directed graph visualization."""
    plt, _, _, _, np, _, _, _ = _check_matplotlib()
    if plt is None: return "Chart unavailable: matplotlib not installed"
    def _draw():
        import numpy as np
        fig, ax = plt.subplots(figsize=(10, 8))
        n = len(nodes)
        angles = np.linspace(0, 2*np.pi, n, endpoint=False)
        pos = {node.get("id", i): (np.cos(a), np.sin(a)) for i, (node, a) in enumerate(zip(nodes, angles))}
        for edge in edges:
            src = pos.get(edge.get("source", edge.get("from")))
            tgt = pos.get(edge.get("target", edge.get("to")))
            if src and tgt:
                ax.plot([src[0], tgt[0]], [src[1], tgt[1]], color="#aaa", linewidth=0.5+edge.get("weight", 1)*0.3, alpha=0.5)
        colors = _get_palette("default", n)
        for i, (node, angle) in enumerate(zip(nodes, angles)):
            x, y = pos[node.get("id", i)]
            ax.scatter(x, y, s=100+node.get("size", 50)*2, c=colors[i % len(colors)], alpha=0.8, edgecolors="white", linewidth=1, zorder=5)
            ax.annotate(node.get("label", node.get("id", f"N{i}")), (x, y), fontsize=8, ha="center", va="bottom", alpha=0.9)
        ax.set_title(title, fontsize=14, fontweight="bold")
        _apply_theme(ax, theme)
        ax.set_aspect("equal")
        ax.axis("off")
        fig.tight_layout()
        return _save_plot(fig, filename)
    return await _exec_sync(_draw)


async def plot_sunburst(
    labels: List[str],
    parents: List[str],
    values: List[float],
    title: str = "Sunburst Chart",
    filename: str = None,
    theme: str = "light",
) -> str:
    """Create a simple hierarchical sunburst-style chart using nested pie."""
    plt, _, _, _, np, _, _, _ = _check_matplotlib()
    if plt is None: return "Chart unavailable: matplotlib not installed"
    def _draw():
        import numpy as np
        fig, ax = plt.subplots(figsize=(10, 10))
        unique_parents = list(set(parents))
        n_levels = len(unique_parents) + 1
        colors = _get_palette("vivid", len(labels))
        radii = np.linspace(0.2, 1.0, n_levels)
        width = radii[1] - radii[0]
        label_positions = {}
        for level in range(n_levels):
            level_labels = []
            level_values = []
            level_colors = []
            parent_map = {}
            for i, (lb, pr, vl) in enumerate(zip(labels, parents, values)):
                if level == 0 and pr == "":
                    level_labels.append(lb); level_values.append(vl); level_colors.append(colors[i % len(colors)])
                elif level > 0 and pr == (unique_parents[level-1] if level-1 < len(unique_parents) else ""):
                    level_labels.append(lb); level_values.append(vl); level_colors.append(colors[i % len(colors)])
            if level_values:
                total = sum(level_values)
                start = 0
                for j, (lb, vl, clr) in enumerate(zip(level_labels, level_values, level_colors)):
                    theta = 2*np.pi * vl / total
                    ax.bar([start], [width], bottom=[radii[level]], width=[theta], color=clr, alpha=0.8, edgecolor="white", linewidth=0.5)
                    mid_angle = start + theta/2
                    label_x = (radii[level] + width/2) * np.cos(mid_angle)
                    label_y = (radii[level] + width/2) * np.sin(mid_angle)
                    ax.text(label_x, label_y, lb, fontsize=7, ha="center", va="center", rotation=np.degrees(mid_angle) if theta > 0.2 else 0)
                    start += theta
        ax.set_title(title, fontsize=14, fontweight="bold")
        ax.set_aspect("equal")
        ax.axis("off")
        fig.tight_layout()
        return _save_plot(fig, filename)
    return await _exec_sync(_draw)


async def plot_step(
    x: List[float],
    y: List[float],
    title: str = "Step Chart",
    xlabel: str = "X",
    ylabel: str = "Y",
    filename: str = None,
    theme: str = "light",
    color: str = "#007AFF",
    where: str = "mid",
) -> str:
    """Create a step chart (pre, post, or mid)."""
    plt, _, _, _, np, _, _, _ = _check_matplotlib()
    if plt is None: return "Chart unavailable: matplotlib not installed"
    def _draw():
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.step(x, y, color=color, linewidth=2, where=where)
        ax.fill_between(x, y, step=where, alpha=0.1, color=color)
        ax.set_title(title, fontsize=14, fontweight="bold")
        ax.set_xlabel(xlabel); ax.set_ylabel(ylabel)
        _apply_theme(ax, theme)
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        return _save_plot(fig, filename)
    return await _exec_sync(_draw)


async def plot_qq(
    data: List[float],
    distribution: str = "normal",
    title: str = "Q-Q Plot",
    filename: str = None,
    theme: str = "light",
) -> str:
    """Create a Q-Q plot to test distribution fit."""
    plt, _, _, _, np, _, _, _ = _check_matplotlib()
    if plt is None: return "Chart unavailable: matplotlib not installed"
    def _draw():
        from scipy import stats
        import numpy as np
        fig, ax = plt.subplots(figsize=(8, 8))
        if distribution == "normal":
            stats.probplot(data, dist="norm", plot=ax)
        else:
            stats.probplot(data, dist=stats.uniform, plot=ax)
        ax.set_title(title, fontsize=14, fontweight="bold")
        _apply_theme(ax, theme)
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        return _save_plot(fig, filename)
    return await _exec_sync(_draw)


async def plot_comparison(
    items: List[str],
    values_a: List[float],
    values_b: List[float],
    label_a: str = "Current",
    label_b: str = "Previous",
    title: str = "Comparison",
    filename: str = None,
    theme: str = "light",
) -> str:
    """Create and save a grouped bar chart comparing two data sets."""
    plt, _, _, _, np, _, _, _ = _check_matplotlib()
    if plt is None: return "Chart unavailable: matplotlib not installed"
    def _draw():
        import numpy as np
        fig, ax = plt.subplots(figsize=(10, 5))
        x = np.arange(len(items))
        width = 0.35
        bars1 = ax.bar(x - width / 2, values_a, width, label=label_a, color="#007AFF", alpha=0.85)
        bars2 = ax.bar(x + width / 2, values_b, width, label=label_b, color="#FF6B6B", alpha=0.85)
        ax.set_title(title, fontsize=14, fontweight="bold")
        ax.set_xticks(x); ax.set_xticklabels(items, rotation=45, ha="right")
        ax.legend(); _apply_theme(ax, theme); ax.grid(True, alpha=0.3, axis="y")
        fig.tight_layout()
        return _save_plot(fig, filename)
    return await _exec_sync(_draw)


async def plot_stock_prices(
    dates: List[str],
    prices: List[float],
    symbol: str,
    title: str = None,
    filename: str = None,
    theme: str = "light",
    volume: Optional[List[float]] = None,
    moving_avg: Optional[int] = None,
) -> str:
    """Create and save a stock price chart with optional volume and moving avg."""
    plt, mdates, _, _, np, _, _, _ = _check_matplotlib()
    if plt is None: return "Chart unavailable: matplotlib not installed"
    def _draw():
        import numpy as np
        parsed = [datetime.fromisoformat(d) if isinstance(d, str) else d for d in dates]
        n_plots = 2 if volume else 1
        fig, ax = plt.subplots(nrows=n_plots, figsize=(12, 6 if not volume else 8), sharex=True)
        if n_plots == 1: ax = [ax]
        ax[0].plot(parsed, prices, color="#007AFF", linewidth=2, marker=".", markersize=3)
        ax[0].fill_between(parsed, prices, alpha=0.1, color="#007AFF")
        if moving_avg and len(prices) >= moving_avg:
            ma = np.convolve(prices, np.ones(moving_avg)/moving_avg, mode="valid")
            ma_dates = parsed[moving_avg-1:]
            ax[0].plot(ma_dates, ma, color="#FF6B6B", linewidth=1.5, label=f"{moving_avg}-day MA")
            ax[0].legend(fontsize=10)
        ax[0].set_title(title or f"{symbol} Price Chart", fontsize=14, fontweight="bold")
        ax[0].set_ylabel("Price ($)")
        ax[0].xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
        _apply_theme(ax[0], theme)
        ax[0].grid(True, alpha=0.3)
        if volume:
            colors = ["#34C759" if prices[i] >= (prices[i-1] if i>0 else 0) else "#FF6B6B" for i in range(len(prices))]
            ax[1].bar(parsed, volume, color=colors, alpha=0.5, width=0.8)
            ax[1].set_ylabel("Volume")
            _apply_theme(ax[1], theme)
            ax[1].grid(True, alpha=0.3, axis="y")
        fig.tight_layout()
        return _save_plot(fig, filename)
    return await _exec_sync(_draw)


async def plot_map(
    locations: List[Dict[str, Any]],
    title: str = "Location Map",
    filename: str = None,
    theme: str = "light",
) -> str:
    """Create a simple map-like scatter plot of geographic coordinates."""
    plt, _, _, _, np, _, _, _ = _check_matplotlib()
    if plt is None: return "Chart unavailable: matplotlib not installed"
    def _draw():
        fig, ax = plt.subplots(figsize=(12, 8))
        lats = [loc.get("lat", 0) for loc in locations]
        lons = [loc.get("lon", 0) for loc in locations]
        names = [loc.get("name", loc.get("label", f"P{i}")) for i, loc in enumerate(locations)]
        sizes = [50 + loc.get("size", 50)*2 for loc in locations]
        colors = _get_palette("default", len(locations))
        sc = ax.scatter(lons, lats, s=sizes, c=colors, alpha=0.7, edgecolors="white", linewidth=0.5, zorder=5)
        for name, lat, lon in zip(names, lats, lons):
            ax.annotate(name, (lon, lat), fontsize=8, ha="center", va="bottom", alpha=0.9)
        ax.set_title(title, fontsize=14, fontweight="bold")
        _apply_theme(ax, theme)
        ax.set_xlabel("Longitude"); ax.set_ylabel("Latitude")
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        return _save_plot(fig, filename)
    return await _exec_sync(_draw)


async def plot_parallel_coordinates(
    data: Dict[str, List[float]],
    class_column: str = None,
    title: str = "Parallel Coordinates",
    filename: str = None,
    theme: str = "light",
) -> str:
    """Create a parallel coordinates plot for multi-dimensional data."""
    plt, _, _, _, np, _, _, _ = _check_matplotlib()
    if plt is None: return "Chart unavailable: matplotlib not installed"
    def _draw():
        import pandas as pd
        import numpy as np
        from pandas.plotting import parallel_coordinates as pd_parallel
        df = pd.DataFrame(data)
        if class_column and class_column in df.columns:
            pd_parallel(df, class_column, ax=plt.gca(), color=_get_palette("default"))
        else:
            for col in df.columns:
                plt.plot(range(len(df)), df[col], marker="o", label=col, alpha=0.7)
        plt.title(title, fontsize=14, fontweight="bold")
        _apply_theme(plt.gca(), theme)
        plt.grid(True, alpha=0.3)
        if class_column: plt.legend(fontsize=8)
        fig = plt.gcf(); fig.set_size_inches(12, 6)
        fig.tight_layout()
        return _save_plot(fig, filename)
    return await _exec_sync(_draw)


async def visualize_data(
    data: Dict[str, Any],
    chart_type: str = "auto",
    title: str = "Data Visualization",
    filename: str = None,
    theme: str = "light",
) -> str:
    """Auto-detect the best chart type for the given data and generate it."""
    if not data or not isinstance(data, dict):
        return "No data to visualize"
    keys = list(data.keys())
    values = [v if isinstance(v, (int, float)) else 0 for v in data.values()]
    if chart_type == "auto":
        if len(keys) <= 6:
            chart_type = "pie"
        else:
            chart_type = "bar"
    if chart_type == "pie":
        return await plot_pie(keys, values, title, filename, theme)
    elif chart_type == "bar":
        return await plot_bar(keys, values, title, "", "Value", filename=filename, theme=theme)
    elif chart_type == "line":
        indices = list(range(len(values)))
        return await plot_line(indices, values, title, "Index", "Value", filename=filename, theme=theme)
    elif chart_type == "radar":
        return await plot_radar(keys, {"Data": values}, title, filename, theme)
    elif chart_type == "area":
        return await plot_area(keys, {"Data": values}, title, filename=filename, theme=theme)
    else:
        return f"Unknown chart type: {chart_type}"
