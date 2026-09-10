"""
core/data.py
------------
Loads and validates OHLC(V) data from a CSV file into a clean pandas DataFrame.
"""

import pandas as pd
import numpy as np


REQUIRED_COLS = ["date", "open", "high", "low", "close"]


def load_ohlc(path: str) -> pd.DataFrame:
    """
    Load OHLC data from CSV.

    Expected columns (case-insensitive): date, open, high, low, close, [volume]

    Returns a DataFrame indexed 0..N-1 with a datetime 'date' column,
    sorted chronologically, with a reset integer index (used everywhere
    downstream for bar-by-bar iteration).
    """
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]

    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(
            f"OHLC file is missing required columns: {missing}. "
            f"Found columns: {list(df.columns)}"
        )

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    if "volume" not in df.columns:
        df["volume"] = np.nan

    if df[["open", "high", "low", "close"]].isnull().any().any():
        bad_rows = df[df[["open", "high", "low", "close"]].isnull().any(axis=1)]
        raise ValueError(f"Found {len(bad_rows)} rows with invalid/non-numeric OHLC values.")

    # sanity check: high must be the max, low must be the min of each bar
    inconsistent = df[(df["high"] < df[["open", "close"]].max(axis=1)) |
                       (df["low"] > df[["open", "close"]].min(axis=1))]
    if len(inconsistent) > 0:
        print(f"Warning: {len(inconsistent)} bars have high/low inconsistent with open/close. "
              f"They will still be used, but check your data source.")

    df["bar_index"] = df.index
    return df
