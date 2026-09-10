"""
core/visualize.py
------------------
Step 5 of the pipeline: charts.

  - plot_2d(): candlestick-style price chart with liquidity zones (dashed
    lines), sweep markers (X at the wick), and trade entries/exits
    (triangles + connecting lines colored by win/loss).
  - plot_3d(): a 3D view where X = bar index (time), Y = price, and
    Z = a rolling volatility/volume proxy, so you can see how sweeps
    cluster in higher-volatility regions. Trades are plotted as a 3D
    scatter on top.
"""

from typing import List
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401 (registers 3D projection)

from .zones import LiquidityZone
from .sweeps import Sweep
from .simulator import Trade


def _plot_candles(ax, df: pd.DataFrame):
    """Lightweight OHLC candlestick rendering using matplotlib primitives only."""
    width = 0.6
    for i, row in df.iterrows():
        color = "#26a69a" if row.close >= row.open else "#ef5350"
        ax.plot([i, i], [row.low, row.high], color=color, linewidth=0.8, zorder=1)
        ax.add_patch(plt.Rectangle(
            (i - width / 2, min(row.open, row.close)),
            width,
            max(abs(row.close - row.open), 1e-9),
            color=color,
            zorder=2,
        ))


def plot_2d(df: pd.DataFrame, zones: List[LiquidityZone], sweeps: List[Sweep],
            trades: List[Trade], save_path: str = None):
    fig, ax = plt.subplots(figsize=(16, 8))
    _plot_candles(ax, df)

    # liquidity zones
    for zone in zones:
        color = "orange" if zone.kind == "resistance" else "dodgerblue"
        start = min(zone.touches)
        ax.hlines(zone.level, xmin=start, xmax=len(df) - 1,
                   color=color, linestyle="--", linewidth=1, alpha=0.7)
        for t in zone.touches:
            ax.scatter(t, df.iloc[t].high if zone.kind == "resistance" else df.iloc[t].low,
                       marker="o", color=color, s=25, zorder=3)

    # sweeps
    for sweep in sweeps:
        ax.scatter(sweep.sweep_bar, sweep.sweep_price, marker="x", color="black",
                   s=90, linewidths=2, zorder=4,
                   label="Sweep" if sweep is sweeps[0] else None)

    # trades
    for trade in trades:
        win = trade.pnl > 0
        color = "green" if win else "red"
        marker = "^" if trade.direction == "long" else "v"
        ax.scatter(trade.entry_bar, trade.entry_price, marker=marker, color=color,
                   s=80, zorder=5, edgecolors="black", linewidths=0.5)
        ax.scatter(trade.exit_bar, trade.exit_price, marker="s", color=color,
                   s=40, zorder=5, edgecolors="black", linewidths=0.5)
        ax.plot([trade.entry_bar, trade.exit_bar], [trade.entry_price, trade.exit_price],
                color=color, linewidth=0.8, alpha=0.6, zorder=4)

    ax.set_title("Liquidity Sweep Reversal System — Price, Zones, Sweeps & Trades")
    ax.set_xlabel("Bar index")
    ax.set_ylabel("Price")
    handles, labels = ax.get_legend_handles_labels()
    if handles:
        ax.legend(handles, labels, loc="upper left")
    fig.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150)
        print(f"Saved 2D chart to {save_path}")
    return fig


def plot_3d(df: pd.DataFrame, trades: List[Trade], save_path: str = None):
    """
    3D view: X = bar index, Y = close price, Z = rolling volatility
    (high-low range, smoothed) so sweeps/trades in volatile zones stand out.
    Trade entries are overlaid as a colored scatter (green=win, red=loss).
    """
    fig = plt.figure(figsize=(14, 9))
    ax = fig.add_subplot(111, projection="3d")

    x = df["bar_index"].values
    y = df["close"].values
    rolling_range = (df["high"] - df["low"]).rolling(10, min_periods=1).mean().values
    z = rolling_range

    ax.plot(x, y, z, color="steelblue", linewidth=1, alpha=0.8)

    if trades:
        entry_x = [t.entry_bar for t in trades]
        entry_y = [t.entry_price for t in trades]
        entry_z = [rolling_range[t.entry_bar] for t in trades]
        colors = ["green" if t.pnl > 0 else "red" for t in trades]
        ax.scatter(entry_x, entry_y, entry_z, color=colors, s=60, depthshade=True,
                   edgecolors="black", linewidths=0.5)

    ax.set_xlabel("Bar index (time)")
    ax.set_ylabel("Close price")
    ax.set_zlabel("Rolling volatility (avg high-low range)")
    ax.set_title("Liquidity Sweep Reversal System — 3D View")
    fig.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150)
        print(f"Saved 3D chart to {save_path}")
    return fig
