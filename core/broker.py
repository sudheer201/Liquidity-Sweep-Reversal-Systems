"""
core/broker.py
---------------
Thin wrapper around Alpaca's API for:
  - Pulling recent live/historical bars for a ticker
  - Checking current account equity and open positions
  - Submitting bracket orders (entry + stop-loss + take-profit in one call)

Uses environment variables for API keys — NEVER hardcode keys in source
files. Set them before running:

  Windows (PowerShell):
    $env:ALPACA_API_KEY = "your_key"
    $env:ALPACA_SECRET_KEY = "your_secret"

  Mac/Linux:
    export ALPACA_API_KEY="your_key"
    export ALPACA_SECRET_KEY="your_secret"
"""

import os
import sys
import pandas as pd

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, StopLossRequest, TakeProfitRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass, QueryOrderStatus
from alpaca.data.historical import StockHistoricalDataClient, CryptoHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit


class AlpacaBroker:
    def __init__(self, paper: bool = True):
        api_key = os.environ.get("ALPACA_API_KEY")
        secret_key = os.environ.get("ALPACA_SECRET_KEY")

        if not api_key or not secret_key:
            print("ERROR: ALPACA_API_KEY / ALPACA_SECRET_KEY environment variables not set.")
            print("Set them before running (see core/broker.py header for the exact commands).")
            sys.exit(1)

        self.trading_client = TradingClient(api_key, secret_key, paper=paper)
        self.data_client = StockHistoricalDataClient(api_key, secret_key)
        self.crypto_data_client = CryptoHistoricalDataClient()  # crypto market data needs no keys
        self.paper = paper

    def is_market_open(self) -> bool:
        clock = self.trading_client.get_clock()
        return clock.is_open

    def get_equity(self) -> float:
        account = self.trading_client.get_account()
        return float(account.equity)

    def has_open_position(self, ticker: str) -> bool:
        positions = self.trading_client.get_all_positions()
        return any(p.symbol == ticker for p in positions)

    def get_recent_bars(self, ticker: str, minutes_back: int = 5, lookback_bars: int = 300) -> pd.DataFrame:
        """
        Pulls the most recent N bars at the given minute granularity for a
        ticker and returns a DataFrame matching the system's expected
        columns (date, open, high, low, close, volume, bar_index).
        """
        request = StockBarsRequest(
            symbol_or_symbols=ticker,
            timeframe=TimeFrame(minutes_back, TimeFrameUnit.Minute),
            limit=lookback_bars,
        )
        bars = self.data_client.get_stock_bars(request)
        df = bars.df.reset_index()
        df = df[df["symbol"] == ticker].copy()

        df = df.rename(columns={"timestamp": "date"})
        df = df[["date", "open", "high", "low", "close", "volume"]]
        df = df.sort_values("date").reset_index(drop=True)
        df["bar_index"] = df.index
        return df

    def get_last_exit_fill(self, ticker: str, exit_side: str):
        """
        After a bracket order's stop/target leg fills and closes a position,
        this looks up that closing order's actual fill price — needed to
        log real P&L, since bracket exits happen automatically on Alpaca's
        side without this script explicitly placing/tracking that order.
        Returns (fill_price, fill_qty) or (None, None) if nothing found.
        """
        request = GetOrdersRequest(
            status=QueryOrderStatus.CLOSED,
            symbols=[ticker],
            limit=10,
            direction="desc",
        )
        orders = self.trading_client.get_orders(filter=request)
        target_side = OrderSide.BUY if exit_side == "buy" else OrderSide.SELL

        for o in orders:
            if o.side == target_side and o.filled_avg_price is not None:
                return float(o.filled_avg_price), float(o.filled_qty)
        return None, None

    def submit_bracket_order(self, ticker: str, side: str, qty: float,
                              stop_price: float, target_price: float):
        """
        side: "buy" (long) or "sell" (short)
        Submits a market entry with an attached stop-loss and take-profit
        (a bracket order) — Alpaca manages the OCO exit legs automatically.
        """
        order_side = OrderSide.BUY if side == "buy" else OrderSide.SELL

        order_data = MarketOrderRequest(
            symbol=ticker,
            qty=round(qty, 4),
            side=order_side,
            time_in_force=TimeInForce.DAY,
            order_class=OrderClass.BRACKET,
            stop_loss=StopLossRequest(stop_price=round(stop_price, 2)),
            take_profit=TakeProfitRequest(limit_price=round(target_price, 2)),
        )

        order = self.trading_client.submit_order(order_data=order_data)
        return order

    # ---- Crypto-specific methods ----
    # Crypto trades 24/7 (no market-hours gating) but Alpaca does NOT reliably
    # support bracket/OCO orders for crypto, so entry and exit are handled as
    # two separate plain market orders, with stop/target watched manually.

    def get_recent_crypto_bars(self, symbol: str, minutes_back: int = 5, lookback_bars: int = 300) -> pd.DataFrame:
        """symbol format: 'BTC/USD', 'ETH/USD', etc."""
        request = CryptoBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame(minutes_back, TimeFrameUnit.Minute),
            limit=lookback_bars,
        )
        bars = self.crypto_data_client.get_crypto_bars(request)
        df = bars.df.reset_index()
        df = df[df["symbol"] == symbol].copy()

        df = df.rename(columns={"timestamp": "date"})
        df = df[["date", "open", "high", "low", "close", "volume"]]
        df = df.sort_values("date").reset_index(drop=True)
        df["bar_index"] = df.index
        return df

    def submit_crypto_market_order(self, symbol: str, side: str, qty: float):
        """Plain market order — no bracket support for crypto, so no stop/target attached here."""
        order_side = OrderSide.BUY if side == "buy" else OrderSide.SELL
        order_data = MarketOrderRequest(
            symbol=symbol,
            qty=round(qty, 6),
            side=order_side,
            time_in_force=TimeInForce.GTC,
        )
        return self.trading_client.submit_order(order_data=order_data)

    def get_position_qty(self, symbol: str) -> float:
        positions = self.trading_client.get_all_positions()
        for p in positions:
            if p.symbol.replace("/", "") == symbol.replace("/", ""):
                return float(p.qty)
        return 0.0

    def close_crypto_position(self, symbol: str):
        return self.trading_client.close_position(symbol_or_asset_id=symbol)
