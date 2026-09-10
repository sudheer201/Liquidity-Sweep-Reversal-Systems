"""
core/metrics.py
----------------
Step 4 of the pipeline: turn a list of Trade objects into a performance report.
"""

from typing import List, Dict
import numpy as np

from .simulator import Trade


def compute_metrics(trades: List[Trade], starting_capital: float) -> Dict:
    if not trades:
        return {
            "total_trades": 0,
            "win_rate": 0.0,
            "total_return_pct": 0.0,
            "final_equity": starting_capital,
            "max_drawdown_pct": 0.0,
            "profit_factor": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
        }

    pnls = np.array([t.pnl for t in trades])
    equity_curve = np.array([t.equity_after for t in trades])
    equity_curve_with_start = np.concatenate([[starting_capital], equity_curve])

    wins = pnls[pnls > 0]
    losses = pnls[pnls <= 0]

    win_rate = len(wins) / len(pnls) * 100

    gross_profit = wins.sum() if len(wins) else 0.0
    gross_loss = abs(losses.sum()) if len(losses) else 0.0
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float("inf")

    running_max = np.maximum.accumulate(equity_curve_with_start)
    drawdowns = (equity_curve_with_start - running_max) / running_max
    max_drawdown_pct = drawdowns.min() * 100

    final_equity = equity_curve[-1]
    total_return_pct = (final_equity - starting_capital) / starting_capital * 100

    return {
        "total_trades": len(trades),
        "win_rate": round(win_rate, 2),
        "total_return_pct": round(total_return_pct, 2),
        "final_equity": round(final_equity, 2),
        "max_drawdown_pct": round(max_drawdown_pct, 2),
        "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else "inf",
        "avg_win": round(wins.mean(), 2) if len(wins) else 0.0,
        "avg_loss": round(losses.mean(), 2) if len(losses) else 0.0,
    }


def print_report(metrics: Dict) -> None:
    print("\n" + "=" * 42)
    print(" LIQUIDITY SWEEP REVERSAL - PERFORMANCE")
    print("=" * 42)
    print(f" Total trades      : {metrics['total_trades']}")
    print(f" Win rate          : {metrics['win_rate']}%")
    print(f" Total return      : {metrics['total_return_pct']}%")
    print(f" Final equity      : {metrics['final_equity']}")
    print(f" Max drawdown      : {metrics['max_drawdown_pct']}%")
    print(f" Profit factor     : {metrics['profit_factor']}")
    print(f" Avg win / loss    : {metrics['avg_win']} / {metrics['avg_loss']}")
    print("=" * 42 + "\n")
