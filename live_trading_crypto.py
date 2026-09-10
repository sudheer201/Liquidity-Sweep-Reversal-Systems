"""
live_trading_crypto.py
------------------------
Runs the Liquidity Sweep Reversal strategy on CRYPTO, 24/7, via Alpaca's
paper trading API. Uses the exact same zone/sweep detection as the stock
version and backtester (core/zones.py, core/sweeps.py).

WHY THIS IS A SEPARATE SCRIPT FROM live_trading.py:
Alpaca does not reliably support bracket/OCO orders (automatic attached
stop-loss + take-profit) for crypto the way it does for stocks. So instead:
  - Entry is a plain market order.
  - The stop-loss and take-profit levels are tracked in memory by this
    script, and it manually submits a closing market order the moment
    price crosses either level on a subsequent poll.

This means, unlike the stock version, protection is NOT guaranteed by the
exchange between polls — if the process crashes or your machine sleeps,
an open position has no broker-side safety net until this script is
running again. Keep this in mind, especially before ever using --live.

Crypto trades 24/7, so there's no market-hours check here.

Usage:
    python live_trading_crypto.py --symbol BTC/USD
    python live_trading_crypto.py --symbol ETH/USD --poll-seconds 30
"""

import argparse
import os
import time
import sys
from datetime import datetime

import matplotlib
matplotlib.use("Agg")  # no popup windows — just save to disk
import matplotlib.pyplot as plt

from config import CONFIG
from core.zones import detect_liquidity_zones
from core.sweeps import detect_sweeps
from core.broker import AlpacaBroker
from core.visualize import plot_2d
from core.trade_log import append_trade, load_stats


def save_live_chart(df, zones, sweeps, open_trade, symbol, stats, output_dir="output"):
    """
    Saves a live-updating chart to output/live_<symbol>.png using the same
    plot_2d() the backtester uses, so zones/sweeps look identical to what
    you saw in main.py. Also stamps live performance stats (trades, win
    rate, P&L, equity) directly onto the chart as a subtitle, so anyone
    looking at the image sees the full picture — not just price.
    """
    os.makedirs(output_dir, exist_ok=True)
    safe_name = symbol.replace("/", "")
    save_path = os.path.join(output_dir, f"live_{safe_name}.png")

    trades = []
    if open_trade is not None:
        class _LiveTradeMarker:
            pass
        t = _LiveTradeMarker()
        t.direction = "long" if open_trade["side"] == "buy" else "short"
        t.entry_bar = len(df) - 1
        t.entry_price = open_trade["entry_price"]
        t.exit_bar = len(df) - 1
        t.exit_price = open_trade["entry_price"]
        t.pnl = 0
        trades.append(t)

    # don't let plot_2d save yet — we want to add the stats line first
    fig = plot_2d(df, zones, sweeps, trades, save_path=None)

    position_text = "FLAT (no open position)"
    if open_trade is not None:
        position_text = (f"OPEN {open_trade['side'].upper()} @ {open_trade['entry_price']:.2f} | "
                          f"stop {open_trade['stop_price']:.2f} | target {open_trade['target_price']:.2f}")

    win_rate_text = f"{stats['win_rate']:.0f}%" if stats["trades_closed"] > 0 else "—"
    pnl_sign = "+" if stats["total_pnl"] >= 0 else ""

    # note: "\$" (escaped) not "$" — a bare $ triggers matplotlib's mathtext
    # parser and silently eats surrounding characters/spacing
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


def run_live_crypto(symbol: str, poll_seconds: int, paper: bool = True):
    broker = AlpacaBroker(paper=paper)
    mode = "PAPER" if paper else "*** LIVE REAL MONEY ***"
    print(f"Starting 24/7 crypto trading loop for {symbol} — mode: {mode}")
    print(f"Polling every {poll_seconds} seconds. Press Ctrl+C to stop.")
    safe_name = symbol.replace("/", "")
    print(f"Live chart will be saved to output/live_{safe_name}.png — open it once in VS Code, "
          f"it auto-refreshes every poll.\n")

    already_traded_sweep_bars = set()
    open_trade = None  # dict: {side, entry_price, stop_price, target_price, qty} or None

    # load any past trade history for this symbol so a restart doesn't lose it
    stats = load_stats(symbol, starting_equity=broker.get_equity())
    if stats["trades_closed"] > 0:
        print(f"Loaded {stats['trades_closed']} past trades from history "
              f"(win rate {stats['win_rate']:.0f}%, total P&L ${stats['total_pnl']:.2f})\n")

    try:
        while True:
            df = broker.get_recent_crypto_bars(symbol, minutes_back=1, lookback_bars=1200)
            if len(df) < 30:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Not enough bars yet ({len(df)}). Waiting...")
                time.sleep(poll_seconds)
                continue

            current_price = df.iloc[-1].close

            # zones/sweeps are computed every single poll now (not just when flat)
            # so the live chart always reflects the latest picture, whether or
            # not we currently have a position open.
            zones = detect_liquidity_zones(df, CONFIG)
            sweeps = detect_sweeps(df, zones, CONFIG)

            # ---- manage an already-open position (manual stop/target check) ----
            if open_trade is not None:
                hit_stop = (
                    (open_trade["side"] == "buy" and current_price <= open_trade["stop_price"]) or
                    (open_trade["side"] == "sell" and current_price >= open_trade["stop_price"])
                )
                hit_target = (
                    (open_trade["side"] == "buy" and current_price >= open_trade["target_price"]) or
                    (open_trade["side"] == "sell" and current_price <= open_trade["target_price"])
                )

                if hit_stop or hit_target:
                    reason = "STOP" if hit_stop else "TARGET"
                    close_side = "sell" if open_trade["side"] == "buy" else "buy"
                    print(f"\n>>> Closing {symbol} position — {reason} hit at {current_price:.2f} <<<")
                    try:
                        broker.submit_crypto_market_order(symbol, close_side, open_trade["qty"])
                        print(f"    Position closed ({reason}).")

                        # record the result for the live stats panel AND persist it to disk
                        if open_trade["side"] == "buy":
                            pnl = (current_price - open_trade["entry_price"]) * open_trade["qty"]
                        else:
                            pnl = (open_trade["entry_price"] - current_price) * open_trade["qty"]
                        stats["trades_closed"] += 1
                        if pnl > 0:
                            stats["wins"] += 1
                        stats["total_pnl"] += pnl
                        stats["win_rate"] = (stats["wins"] / stats["trades_closed"]) * 100
                        stats["equity"] = broker.get_equity()

                        append_trade(
                            symbol=symbol, side=open_trade["side"],
                            entry_price=open_trade["entry_price"], exit_price=current_price,
                            qty=open_trade["qty"], pnl=pnl, exit_reason=reason.lower(),
                            equity_after=stats["equity"],
                        )
                    except Exception as e:
                        print(f"    CLOSE FAILED: {e}")
                    open_trade = None
                else:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                          f"Position open ({open_trade['side']}): price {current_price:.2f}, "
                          f"stop {open_trade['stop_price']:.2f}, target {open_trade['target_price']:.2f}")
                    save_live_chart(df, zones, sweeps, open_trade, symbol, stats)
                    time.sleep(poll_seconds)
                    continue

            # ---- look for a new signal (only if no position currently open) ----
            recent_sweeps = [s for s in sweeps if s.confirm_bar >= len(df) - 2]

            if not recent_sweeps:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                      f"No fresh sweep. {len(zones)} zones tracked, last close {current_price:.2f}")

            for sweep in recent_sweeps:
                sweep_key = (sweep.zone.level, sweep.confirm_bar)
                if sweep_key in already_traded_sweep_bars:
                    continue

                stop_buffer = CONFIG["stop_buffer_pct"]
                rr = CONFIG["risk_reward_ratio"]

                if sweep.direction == "bearish":
                    side = "sell"
                    stop_price = sweep.sweep_price * (1 + stop_buffer)
                    risk_per_unit = stop_price - current_price
                    target_price = current_price - rr * risk_per_unit
                else:
                    side = "buy"
                    stop_price = sweep.sweep_price * (1 - stop_buffer)
                    risk_per_unit = current_price - stop_price
                    target_price = current_price + rr * risk_per_unit

                if risk_per_unit <= 0:
                    already_traded_sweep_bars.add(sweep_key)
                    continue

                equity = broker.get_equity()
                risk_amount = equity * CONFIG["risk_per_trade_pct"]
                qty = risk_amount / risk_per_unit

                print(f"\n>>> SWEEP CONFIRMED: {sweep.direction} on {symbol} <<<")
                print(f"    Entry ~{current_price:.2f}  Stop {stop_price:.2f}  Target {target_price:.2f}  Qty {qty:.6f}")

                try:
                    order = broker.submit_crypto_market_order(symbol, side, qty)
                    print(f"    Order submitted: id={order.id} status={order.status}")
                    open_trade = {
                        "side": side, "entry_price": current_price,
                        "stop_price": stop_price, "target_price": target_price, "qty": qty,
                    }
                except Exception as e:
                    print(f"    ORDER FAILED: {e}")

                already_traded_sweep_bars.add(sweep_key)
                break  # only one open position at a time

            save_live_chart(df, zones, sweeps, open_trade, symbol, stats)
            time.sleep(poll_seconds)

    except KeyboardInterrupt:
        print("\nStopped by user.")
        sys.exit(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="24/7 crypto live/paper trading loop")
    parser.add_argument("--symbol", required=True, help="Crypto pair, e.g. BTC/USD, ETH/USD")
    parser.add_argument("--poll-seconds", type=int, default=60, help="How often to check for new bars/signals")
    parser.add_argument("--live", action="store_true",
                         help="DANGER: submit REAL orders with REAL money instead of paper trading.")
    args = parser.parse_args()

    if args.live:
        confirm = input(
            "You are about to run this with REAL MONEY (--live flag set). "
            "Type 'I UNDERSTAND THE RISK' exactly to continue: "
        )
        if confirm != "I UNDERSTAND THE RISK":
            print("Confirmation not matched. Exiting without trading.")
            sys.exit(0)

    run_live_crypto(args.symbol, args.poll_seconds, paper=not args.live)
