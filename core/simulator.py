"""
core/simulator.py
------------------
Step 3 of the pipeline: turn confirmed sweeps into simulated trades.

Rules:
  - Entry: next bar's open after the sweep is confirmed (close back inside zone).
  - Stop-loss: just beyond the sweep wick (the "swept" extreme), plus a small buffer.
  - Take-profit: risk * risk_reward_ratio away from entry.
  - Position size: risk_per_trade_pct of current equity / stop distance.
  - Walk forward bar by bar; whichever of SL/TP is hit first closes the trade.
    If both could be hit on the same bar (gap), we conservatively assume the
    stop-loss is hit first.
"""

from dataclasses import dataclass
from typing import List, Literal, Optional
import pandas as pd

from .sweeps import Sweep


@dataclass
class Trade:
    direction: Literal["long", "short"]
    entry_bar: int
    entry_price: float
    stop_price: float
    target_price: float
    exit_bar: Optional[int] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None  # "target", "stop", "eod" (ran off the end of data)
    size: float = 0.0
    pnl: float = 0.0
    equity_after: float = 0.0


def simulate_trades(df: pd.DataFrame, sweeps: List[Sweep], config: dict) -> List[Trade]:
    rr = config["risk_reward_ratio"]
    stop_buffer = config["stop_buffer_pct"]
    risk_pct = config["risk_per_trade_pct"]

    equity = config["starting_capital"]
    trades: List[Trade] = []
    n = len(df)

    for sweep in sweeps:
        entry_bar = sweep.confirm_bar + 1
        if entry_bar >= n:
            continue  # sweep happened too close to the end of the dataset

        entry_price = df.iloc[entry_bar].open

        if sweep.direction == "bearish":
            direction = "short"
            stop_price = sweep.sweep_price * (1 + stop_buffer)
            risk_per_unit = stop_price - entry_price
            if risk_per_unit <= 0:
                continue
            target_price = entry_price - rr * risk_per_unit
        else:
            direction = "long"
            stop_price = sweep.sweep_price * (1 - stop_buffer)
            risk_per_unit = entry_price - stop_price
            if risk_per_unit <= 0:
                continue
            target_price = entry_price + rr * risk_per_unit

        risk_amount = equity * risk_pct
        size = risk_amount / risk_per_unit

        trade = Trade(
            direction=direction,
            entry_bar=entry_bar,
            entry_price=entry_price,
            stop_price=stop_price,
            target_price=target_price,
            size=size,
        )

        # walk forward bar by bar to find the exit
        for j in range(entry_bar, n):
            bar = df.iloc[j]

            if direction == "short":
                hit_stop = bar.high >= stop_price
                hit_target = bar.low <= target_price
            else:
                hit_stop = bar.low <= stop_price
                hit_target = bar.high >= target_price

            if hit_stop and hit_target:
                # conservative assumption: stop hit first on the same bar
                trade.exit_bar, trade.exit_price, trade.exit_reason = j, stop_price, "stop"
                break
            elif hit_stop:
                trade.exit_bar, trade.exit_price, trade.exit_reason = j, stop_price, "stop"
                break
            elif hit_target:
                trade.exit_bar, trade.exit_price, trade.exit_reason = j, target_price, "target"
                break

        if trade.exit_bar is None:
            # trade never resolved before data ran out -> close at last available price
            trade.exit_bar = n - 1
            trade.exit_price = df.iloc[-1].close
            trade.exit_reason = "eod"

        if direction == "short":
            trade.pnl = (trade.entry_price - trade.exit_price) * trade.size
        else:
            trade.pnl = (trade.exit_price - trade.entry_price) * trade.size

        equity += trade.pnl
        trade.equity_after = equity
        trades.append(trade)

    return trades
