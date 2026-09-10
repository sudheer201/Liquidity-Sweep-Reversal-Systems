"""
fetch_huggingface_data.py
--------------------------
Downloads REAL US stock minute-level data from the Hugging Face dataset
"mito0o852/OHLCV-1m" (sourced from Finnhub.io, 1992-2026, thousands of US
tickers), filters it to one ticker, resamples the 1-minute candles up to
5-minute candles, and saves it as ohlc.csv in exactly the format the
Liquidity Sweep Reversal System expects.

Dataset card: https://huggingface.co/datasets/mito0o852/OHLCV-1m
Columns in the source data: timestamp, open, high, low, close, volume, ticker
Data is split into one Parquet file per month (e.g. data/ohlcv_2024-06.parquet)

Requires:
    pip install huggingface_hub pyarrow pandas

Usage:
    python fetch_huggingface_data.py --ticker AAPL --months 2024-05 2024-06
    python fetch_huggingface_data.py --ticker TSLA --months 2024-06 --interval 5min
    python fetch_huggingface_data.py --ticker AAPL --months 2024-06 --out aapl_5min.csv

Notes:
    - Each month's Parquet file covers ALL tickers, so the first download of
      a given month can take a little while (avg ~200MB/month) even though
      you only end up keeping one ticker's rows.
    - Pick --months close to "now" for the most complete recent data; very
      old months (pre-2000) may have sparser coverage for some tickers.
    - --interval accepts any pandas resample rule: "5min", "15min", "1h", "1D"
"""

import argparse
import sys

try:
    from huggingface_hub import hf_hub_download
except ImportError:
    print("huggingface_hub is not installed. Run: pip install huggingface_hub pyarrow")
    sys.exit(1)

import pandas as pd

REPO_ID = "mito0o852/OHLCV-1m"
REPO_TYPE = "dataset"


def download_month(year_month: str) -> pd.DataFrame:
    """Downloads (and caches locally) one month's Parquet file, e.g. '2024-06'."""
    filename = f"data/ohlcv_{year_month}.parquet"
    print(f"Fetching {filename} from Hugging Face (cached after first download)...")
    local_path = hf_hub_download(repo_id=REPO_ID, repo_type=REPO_TYPE, filename=filename)
    return pd.read_parquet(local_path)


def resample_ohlcv(df: pd.DataFrame, interval: str) -> pd.DataFrame:
    """Aggregates 1-minute bars up to the requested interval."""
    df = df.set_index("timestamp").sort_index()
    agg = df.resample(interval).agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    })
    return agg.dropna(subset=["open", "high", "low", "close"])


def fetch_and_build(ticker: str, months: list, interval: str, out_path: str):
    frames = []
    for ym in months:
        month_df = download_month(ym)
        ticker_df = month_df[month_df["ticker"] == ticker].copy()
        if ticker_df.empty:
            print(f"  Warning: no rows found for ticker '{ticker}' in {ym}")
        else:
            frames.append(ticker_df)

    if not frames:
        print(f"No data found for '{ticker}' in any of the requested months: {months}")
        print("Double-check the ticker symbol is correct (case-sensitive, e.g. 'AAPL' not 'aapl').")
        sys.exit(1)

    combined = pd.concat(frames, ignore_index=True)
    combined["timestamp"] = pd.to_datetime(combined["timestamp"])

    resampled = resample_ohlcv(combined, interval)
    resampled = resampled.reset_index().rename(columns={"timestamp": "date"})

    resampled.to_csv(out_path, index=False)
    print(f"Saved {len(resampled)} real {interval} candles for {ticker} to '{out_path}'")
    print(f"Range: {resampled['date'].iloc[0]} to {resampled['date'].iloc[-1]}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download real US stock data from Hugging Face")
    parser.add_argument("--ticker", required=True, help="Stock ticker symbol, e.g. AAPL, TSLA, MSFT")
    parser.add_argument("--months", nargs="+", required=True,
                         help="One or more months in YYYY-MM format, e.g. --months 2024-05 2024-06")
    parser.add_argument("--interval", default="5min",
                         help="Resample target, e.g. 5min, 15min, 1h, 1D (default: 5min)")
    parser.add_argument("--out", default="ohlc.csv", help="Output CSV filename")
    args = parser.parse_args()

    fetch_and_build(args.ticker, args.months, args.interval, args.out)
