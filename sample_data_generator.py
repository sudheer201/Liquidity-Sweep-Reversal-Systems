"""
sample_data_generator.py
-------------------------
Generates a synthetic ohlc.csv with a random-walk base price plus a handful
of deliberately engineered "equal highs / equal lows -> sweep -> reversal"
patterns, so you have something meaningful to test the system on immediately.

Run:
    python sample_data_generator.py
"""

import numpy as np
import pandas as pd


def generate_sample_ohlc(n_bars: int = 400, seed: int = 42, out_path: str = "ohlc.csv"):
    rng = np.random.default_rng(seed)

    dates = pd.date_range("2024-01-01", periods=n_bars, freq="4h")
    price = 100.0
    closes = []

    for _ in range(n_bars):
        price += rng.normal(0, 0.4)
        closes.append(price)

    closes = np.array(closes)

    opens = np.roll(closes, 1)
    opens[0] = closes[0]

    highs = np.maximum(opens, closes) + rng.uniform(0.05, 0.3, n_bars)
    lows = np.minimum(opens, closes) - rng.uniform(0.05, 0.3, n_bars)
    volumes = rng.uniform(1000, 5000, n_bars)

    df = pd.DataFrame({
        "date": dates, "open": opens, "high": highs,
        "low": lows, "close": closes, "volume": volumes,
    })

    # --- engineer a few clean equal-high -> sweep -> reversal patterns ---
    def inject_resistance_sweep(start_idx, level):
        # two equal highs to form the zone
        for offset in (0, 15):
            i = start_idx + offset
            df.loc[i, "high"] = level
            df.loc[i, ["open", "close"]] = level - rng.uniform(1.5, 2.5)
            df.loc[i, "low"] = df.loc[i, "close"] - rng.uniform(0.3, 0.6)
        # sweep bar: wick above, close back below
        i = start_idx + 30
        df.loc[i, "open"] = level - 1.0
        df.loc[i, "high"] = level + rng.uniform(0.3, 0.6)
        df.loc[i, "close"] = level - rng.uniform(0.8, 1.5)
        df.loc[i, "low"] = df.loc[i, "close"] - rng.uniform(0.2, 0.4)
        # continuation down for a few bars so the reversal trade has room to work
        for k in range(1, 8):
            df.loc[i + k, "close"] = df.loc[i + k - 1, "close"] - rng.uniform(0.3, 0.9)
            df.loc[i + k, "open"] = df.loc[i + k - 1, "close"]
            df.loc[i + k, "high"] = max(df.loc[i + k, "open"], df.loc[i + k, "close"]) + 0.2
            df.loc[i + k, "low"] = min(df.loc[i + k, "open"], df.loc[i + k, "close"]) - 0.2

    def inject_support_sweep(start_idx, level):
        for offset in (0, 15):
            i = start_idx + offset
            df.loc[i, "low"] = level
            df.loc[i, ["open", "close"]] = level + rng.uniform(1.5, 2.5)
            df.loc[i, "high"] = df.loc[i, "close"] + rng.uniform(0.3, 0.6)
        i = start_idx + 30
        df.loc[i, "open"] = level + 1.0
        df.loc[i, "low"] = level - rng.uniform(0.3, 0.6)
        df.loc[i, "close"] = level + rng.uniform(0.8, 1.5)
        df.loc[i, "high"] = df.loc[i, "close"] + rng.uniform(0.2, 0.4)
        for k in range(1, 8):
            df.loc[i + k, "close"] = df.loc[i + k - 1, "close"] + rng.uniform(0.3, 0.9)
            df.loc[i + k, "open"] = df.loc[i + k - 1, "close"]
            df.loc[i + k, "high"] = max(df.loc[i + k, "open"], df.loc[i + k, "close"]) + 0.2
            df.loc[i + k, "low"] = min(df.loc[i + k, "open"], df.loc[i + k, "close"]) - 0.2

    inject_resistance_sweep(40, closes[40] + 4)
    inject_support_sweep(140, closes[140] - 4)
    inject_resistance_sweep(240, closes[240] + 4)
    inject_support_sweep(320, closes[320] - 4)

    df["high"] = df[["open", "close", "high"]].max(axis=1)
    df["low"] = df[["open", "close", "low"]].min(axis=1)

    df.to_csv(out_path, index=False)
    print(f"Sample OHLC data with engineered sweeps written to '{out_path}' ({len(df)} bars)")
    return df


if __name__ == "__main__":
    generate_sample_ohlc()
