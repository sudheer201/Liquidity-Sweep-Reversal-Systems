"""
live_trading.py
-----------------
Runs the Liquidity Sweep Reversal strategy LIVE against Alpaca's paper
trading API (real live prices, fake money, real order execution logic).

This reuses the EXACT SAME detection logic as the backtester
(core/zones.py, core/sweeps.py) so what you tested in main.py is what
actually gets traded here — no logic duplication, no drift between
backtest and live behavior.

How it works (runs continuously while the market is open):
  1. Every `poll_seconds`, pull the latest bars for the ticker.
  2. Re-run zone + sweep detection on that rolling window.
  3. If a NEW sweep confirmed on the most recently CLOSED bar, and we don't
     already have a position open, submit a bracket order (entry + stop +
     target) sized by config's risk_per_trade_pct against current equity.
  4. Track already-acted-on sweeps so we never double-enter the same signal.
  5. Skip entirely outside market hours.

SAFETY:
  - Defaults to PAPER trading (paper=True in AlpacaBroker). Do not change
    this to live trading until you've watched this run for weeks on paper
    and are comfortable with the behavior, position sizing, and risk.
  - This is not financial advice, and past backtest performance does not
    guarantee future results, live or otherwise.

Usage:
    python live_trading.py --ticker AAPL
    python live_trading.py --ticker AAPL --poll-seconds 60
"""

import argparse
import os
import time
import sys
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from config import CONFIG
from core.zones import detect_liquidity_zones
from core.sweeps import detect_sweeps
from core.broker import AlpacaBroker
from core.visualize import plot_2d
from core.trade_log import append_trade, load_stats


def save_live_chart(df, zones, sweeps, current_trade, ticker, stats, output_dir="output"):
    """
    Saves output/live_<ticker>.png every poll — same look as the backtest
    charts, with a stats banner (trades, win rate, P&L, equity, position)
    stamped on top, same as the crypto version.
    """
    os.makedirs(output_dir, exist_ok=True)
    save_path = os.path.join(output_dir, f"live_{ticker}.png")

    trades = []
    if current_trade is not None:
        class _LiveTradeMarker:
            pass
        t = _LiveTradeMarker()
        t.direction = "long" if current_trade["side"] == "buy" else "short"
        t.entry_bar = len(df) - 1
        t.entry_price = current_trade["entry_price"]
        t.exit_bar = len(df) - 1
        t.exit_price = current_trade["entry_price"]
        t.pnl = 0
        trades.append(t)

    fig = plot_2d(df, zones, sweeps, trades, save_path=None)

    position_text = "FLAT (no open position)"
    if current_trade is not None:
        position_text = f"OPEN {current_trade['side'].upper()} @ {current_trade['entry_price']:.2f}"

    win_rate_text = f"{stats['win_rate']:.0f}%" if stats["trades_closed"] > 0 else "—"
    pnl_sign = "+" if stats["total_pnl"] >= 0 else ""
    subtitle = (
        f"Trades: {stats['trades_closed']}   |   Win rate: {win_rate_text}   |   "
        f"Total P&L: {pnl_sign}\\${stats['total_pnl']:.2f}   |   "
        f"Equity: \\${stats['equity']:.2f}   |   Position: {position_text}"
    )
    fig.subplots_adjust(top=0.86)
    fig.suptitle(subtitle, fontsize=11, y=0.97, color="#1a1a1a", fontweight="bold")
    fig.text(0.5, 0.925, f"Updated: {datetime.now().strftime('%H:%M:%S')}",
              ha="center", fontsize=8, color="#666666")
    fig.savefig(save_path, dpi=150)
    plt.close(fig)


def run_live(ticker: str, poll_seconds: int, paper: bool = True):
    broker = AlpacaBroker(paper=paper)
    mode = "PAPER" if paper else "*** LIVE REAL MONEY ***"
    print(f"Starting live trading loop for {ticker} — mode: {mode}")
    print(f"Polling every {poll_seconds} seconds. Press Ctrl+C to stop.")
    print(f"Live chart will be saved to output/live_{ticker}.png every poll.\n")

    already_traded_sweep_bars = set()  # avoids re-entering the same sweep repeatedly
    current_trade = None  # tracked only for the chart marker — Alpaca's bracket order handles the real exit

    stats = load_stats(ticker, starting_equity=broker.get_equity())
    if stats["trades_closed"] > 0:
        print(f"Loaded {stats['trades_closed']} past trades from history "
              f"(win rate {stats['win_rate']:.0f}%, total P&L ${stats['total_pnl']:.2f})\n")

    try:
        while True:
            if not broker.is_market_open():
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Market closed. Waiting...")
                time.sleep(poll_seconds)
                continue

            df = broker.get_recent_bars(ticker, minutes_back=1, lookback_bars=1200)
            if len(df) < 30:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Not enough bars yet ({len(df)}). Waiting...")
                time.sleep(poll_seconds)
                continue

            zones = detect_liquidity_zones(df, CONFIG)
            sweeps = detect_sweeps(df, zones, CONFIG)

            # if we no longer hold a position, whatever we were tracking must have
            # closed (hit stop or target) — look up the real fill price and log it
            if current_trade is not None and not broker.has_open_position(ticker):
                exit_side = "sell" if current_trade["side"] == "buy" else "buy"
                fill_price, fill_qty = broker.get_last_exit_fill(ticker, exit_side)

                if fill_price is not None:
                    if current_trade["side"] == "buy":
                        pnl = (fill_price - current_trade["entry_price"]) * fill_qty
                    else:
                        pnl = (current_trade["entry_price"] - fill_price) * fill_qty

                    stats["trades_closed"] += 1
                    if pnl > 0:
                        stats["wins"] += 1
                    stats["total_pnl"] += pnl
                    stats["win_rate"] = (stats["wins"] / stats["trades_closed"]) * 100
                    stats["equity"] = broker.get_equity()

                    append_trade(
                        symbol=ticker, side=current_trade["side"],
                        entry_price=current_trade["entry_price"], exit_price=fill_price,
                        qty=fill_qty, pnl=pnl, exit_reason="closed",
                        equity_after=stats["equity"],
                    )
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                          f"Position closed. P&L: {pnl:+.2f} (logged to trade history)")
                else:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                          f"Position closed but couldn't find the fill price to log it — skipping history entry.")

                current_trade = None

            # only consider the most recently confirmed sweep, and only if it's "fresh"
            # (confirmed on one of the last 2 bars, so we don't act on stale signals)
            recent_sweeps = [s for s in sweeps if s.confirm_bar >= len(df) - 2]

            if not recent_sweeps:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                      f"No fresh sweep. {len(zones)} zones tracked, last close {df.iloc[-1].close:.2f}")

            for sweep in recent_sweeps:
                sweep_key = (sweep.zone.level, sweep.confirm_bar)
                if sweep_key in already_traded_sweep_bars:
                    continue

                if broker.has_open_position(ticker):
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                          f"Sweep detected but already have an open position in {ticker} — skipping.")
                    already_traded_sweep_bars.add(sweep_key)
                    continue

                entry_price = df.iloc[-1].close
                stop_buffer = CONFIG["stop_buffer_pct"]
                rr = CONFIG["risk_reward_ratio"]

                if sweep.direction == "bearish":
                    side = "sell"
                    stop_price = sweep.sweep_price * (1 + stop_buffer)
                    risk_per_unit = stop_price - entry_price
                    target_price = entry_price - rr * risk_per_unit
                else:
                    side = "buy"
                    stop_price = sweep.sweep_price * (1 - stop_buffer)
                    risk_per_unit = entry_price - stop_price
                    target_price = entry_price + rr * risk_per_unit

                if risk_per_unit <= 0:
                    print("Skipping trade — invalid risk calculation (stop on wrong side of entry).")
                    already_traded_sweep_bars.add(sweep_key)
                    continue

                equity = broker.get_equity()
                risk_amount = equity * CONFIG["risk_per_trade_pct"]
                qty = risk_amount / risk_per_unit

                print(f"\n>>> SWEEP CONFIRMED: {sweep.direction} on {ticker} <<<")
                print(f"    Entry ~{entry_price:.2f}  Stop {stop_price:.2f}  Target {target_price:.2f}  Qty {qty:.4f}")

                try:
                    order = broker.submit_bracket_order(ticker, side, qty, stop_price, target_price)
                    print(f"    Order submitted: id={order.id} status={order.status}")
                    current_trade = {"side": side, "entry_price": entry_price}
                except Exception as e:
                    print(f"    ORDER FAILED: {e}")

                already_traded_sweep_bars.add(sweep_key)

            save_live_chart(df, zones, sweeps, current_trade, ticker, stats)
            time.sleep(poll_seconds)

    except KeyboardInterrupt:
        print("\nStopped by user.")
        sys.exit(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Live/paper trading loop for the Liquidity Sweep Reversal System")
    parser.add_argument("--ticker", required=True, help="Stock ticker to trade, e.g. AAPL")
    parser.add_argument("--poll-seconds", type=int, default=60, help="How often to check for new bars/signals")
    parser.add_argument("--live", action="store_true",
                         help="DANGER: submit REAL orders with REAL money instead of paper trading. "
                              "Do not use this until you fully understand and trust the system.")
    args = parser.parse_args()

    if args.live:
        confirm = input(
            "You are about to run this with REAL MONEY (--live flag set). "
            "Type 'I UNDERSTAND THE RISK' exactly to continue: "
        )
        if confirm != "I UNDERSTAND THE RISK":
            print("Confirmation not matched. Exiting without trading.")
            sys.exit(0)

    run_live(args.ticker, args.poll_seconds, paper=not args.live)
