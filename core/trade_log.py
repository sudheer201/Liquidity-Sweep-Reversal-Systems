"""
core/trade_log.py
-------------------
Persists every closed trade to a CSV file (one per symbol) so trade history
survives script restarts — nothing is lost if you stop and restart a live
trading loop. Also reconstructs running stats (trades closed, win rate,
total P&L) from that file on startup, instead of starting back at zero.
"""

import os
import csv
from datetime import datetime

FIELDNAMES = ["timestamp", "symbol", "side", "entry_price", "exit_price",
              "qty", "pnl", "exit_reason", "equity_after"]


def log_path_for(symbol: str, output_dir: str = "output") -> str:
    safe_name = symbol.replace("/", "")
    return os.path.join(output_dir, f"trade_log_{safe_name}.csv")


def append_trade(symbol: str, side: str, entry_price: float, exit_price: float,
                  qty: float, pnl: float, exit_reason: str, equity_after: float,
                  output_dir: str = "output"):
    """Appends one completed trade as a new row. Creates the file with a header if it doesn't exist yet."""
    os.makedirs(output_dir, exist_ok=True)
    path = log_path_for(symbol, output_dir)
    file_exists = os.path.isfile(path)

    with open(path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "symbol": symbol,
            "side": side,
            "entry_price": round(entry_price, 6),
            "exit_price": round(exit_price, 6),
            "qty": round(qty, 6),
            "pnl": round(pnl, 4),
            "exit_reason": exit_reason,
            "equity_after": round(equity_after, 2),
        })


def load_stats(symbol: str, starting_equity: float, output_dir: str = "output") -> dict:
    """
    Reads the full trade history for a symbol (if any exists) and rebuilds
    the running stats dict — called once at script startup so a restart
    doesn't wipe out everything that happened before.
    """
    path = log_path_for(symbol, output_dir)
    trades_closed = 0
    wins = 0
    total_pnl = 0.0
    equity = starting_equity

    if os.path.isfile(path):
        with open(path, "r", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                trades_closed += 1
                pnl = float(row["pnl"])
                total_pnl += pnl
                if pnl > 0:
                    wins += 1
                equity = float(row["equity_after"])

    win_rate = (wins / trades_closed * 100) if trades_closed > 0 else 0.0
    return {
        "trades_closed": trades_closed,
        "wins": wins,
        "win_rate": win_rate,
        "total_pnl": total_pnl,
        "equity": equity,
    }
