"""
fetch_real_data.py
-------------------
Downloads REAL stock price data (5-minute candles) from Yahoo Finance and
saves it as ohlc.csv in exactly the format the Liquidity Sweep Reversal
System expects (date, open, high, low, close, volume).

Requires: pip install yfinance

Usage:
    python fetch_real_data.py                       # defaults to AAPL, last 60 days, 5m
    python fetch_real_data.py --ticker TSLA
    python fetch_real_data.py --ticker MSFT --days 30
    python fetch_real_data.py --ticker AAPL --out aapl_ohlc.csv

IMPORTANT — Yahoo Finance limitation:
    5-minute intraday data is only available for the last ~60 days. If you
    ask for more than that, Yahoo will silently return less than you asked
    for (not an error). For longer history, use --interval 1d instead.
"""

import argparse
import sys

try:
    import yfinance as yf
except ImportError:
    print("yfinance is not installed. Run: pip install yfinance")
    sys.exit(1)

import pandas as pd


def fetch_real_ohlc(ticker: str, days: int, interval: str, out_path: str):
    print(f"Downloading {ticker} — last {days} days, {interval} candles...")

    period = f"{days}d"
    df = yf.download(
        tickers=ticker,
        period=period,
        interval=interval,
        auto_adjust=True,
        progress=False,
    )

    if df.empty:
        print(f"No data returned for '{ticker}'. Check the ticker symbol and "
              f"that the market was open during that window.")
        sys.exit(1)

    # yfinance sometimes returns MultiIndex columns when using tickers= with a single symbol
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.reset_index()

    # the datetime column is named "Datetime" for intraday, "Date" for daily
    date_col = "Datetime" if "Datetime" in df.columns else "Date"

    out = pd.DataFrame({
        "date": df[date_col],
        "open": df["Open"],
        "high": df["High"],
        "low": df["Low"],
        "close": df["Close"],
        "volume": df["Volume"],
    })

    out = out.dropna()
    out.to_csv(out_path, index=False)

    print(f"Saved {len(out)} real candles to '{out_path}'")
    print(f"Range: {out['date'].iloc[0]} to {out['date'].iloc[-1]}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download real stock OHLC data for the system")
    parser.add_argument("--ticker", default="AAPL", help="Stock ticker symbol, e.g. AAPL, TSLA, MSFT")
    parser.add_argument("--days", type=int, default=60, help="How many days back (max ~60 for 5m data)")
    parser.add_argument("--interval", default="5m", help="Candle size: 1m, 5m, 15m, 1h, 1d, etc.")
    parser.add_argument("--out", default="ohlc.csv", help="Output CSV filename")
    args = parser.parse_args()

    fetch_real_ohlc(args.ticker, args.days, args.interval, args.out)
