"""
config.py
---------
All tunable parameters for the Liquidity Sweep Reversal System live here.
Change these to tune the strategy without touching the core logic.
"""

CONFIG = {
    # ---- Zone detection ----
    "swing_lookback": 10,          # bars on each side to confirm a swing high/low (fractal size)
    "equal_level_tolerance": 0.0008,  # 0.08% price tolerance to treat two swings as "equal" (liquidity pool)
    "min_zone_touches": 5,        # minimum swing points clustered together to call it a liquidity zone

    # ---- Sweep detection ----
    "sweep_confirmation_bars": 3,  # max bars allowed between the wick beyond the zone and the close-back-inside
    "sweep_wick_min_pct": 0.0005,  # minimum wick-beyond-zone size (0.05%) to count as a real sweep, filters noise

    # ---- Trade rules ----
    "risk_reward_ratio": 2.0,      # take-profit distance = R * stop-loss distance
    "stop_buffer_pct": 0.0008,     # extra buffer beyond the sweep wick for the stop-loss (0.08%)
    "risk_per_trade_pct": 0.01,    # 1% of account risked per trade
    "starting_capital": 10000.0,

    # ---- Data ----
    "ohlc_file": "ohlc.csv",       # date, open, high, low, close, volume (volume optional)
}
