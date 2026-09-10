"""
main.py
-------
Liquidity Sweep Reversal Trading System (Smart Money Concept)

Pipeline:
  1. Load OHLC data                          -> core/data.py
  2. Detect liquidity zones (equal highs/lows) -> core/zones.py
  3. Detect sweeps (fake breakouts)            -> core/sweeps.py
  4. Simulate reversal trades                  -> core/simulator.py
  5. Compute performance metrics               -> core/metrics.py
  6. Visualize everything (2D + 3D)            -> core/visualize.py

Usage:
    python main.py
    
    python main.py --file my_data.csv
    python main.py --no-show          # save charts to disk without a GUI popup
"""

import argparse
import os
import matplotlib.pyplot as plt

from config import CONFIG
from core.data import load_ohlc
from core.zones import detect_liquidity_zones
from core.sweeps import detect_sweeps
from core.simulator import simulate_trades
from core.metrics import compute_metrics, print_report
from core.visualize import plot_2d, plot_3d


def run(ohlc_path: str, show: bool = True, output_dir: str = "output"):
    os.makedirs(output_dir, exist_ok=True)

    print(f"Loading OHLC data from '{ohlc_path}'...")
    df = load_ohlc(ohlc_path)
    print(f"Loaded {len(df)} bars from {df['date'].iloc[0].date()} to {df['date'].iloc[-1].date()}")

    print("Detecting liquidity zones (equal highs/lows)...")
    zones = detect_liquidity_zones(df, CONFIG)
    print(f"Found {len(zones)} liquidity zones "
          f"({sum(z.kind == 'resistance' for z in zones)} resistance, "
          f"{sum(z.kind == 'support' for z in zones)} support)")

    print("Detecting liquidity sweeps (fake breakouts)...")
    sweeps = detect_sweeps(df, zones, CONFIG)
    print(f"Found {len(sweeps)} confirmed sweeps")

    print("Simulating reversal trades...")
    trades = simulate_trades(df, sweeps, CONFIG)
    print(f"Executed {len(trades)} trades")

    metrics = compute_metrics(trades, CONFIG["starting_capital"])
    print_report(metrics)

    print("Rendering charts...")
    fig_2d = plot_2d(df, zones, sweeps, trades, save_path=os.path.join(output_dir, "chart_2d.png"))
    fig_3d = plot_3d(df, trades, save_path=os.path.join(output_dir, "chart_3d.png"))

    if show:
        plt.show()

    return {"df": df, "zones": zones, "sweeps": sweeps, "trades": trades, "metrics": metrics}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Liquidity Sweep Reversal Trading System")
    parser.add_argument("--file", default=CONFIG["ohlc_file"], help="Path to OHLC CSV file")
    parser.add_argument("--no-show", action="store_true", help="Don't pop up chart windows, just save PNGs")
    args = parser.parse_args()

    run(args.file, show=not args.no_show)
