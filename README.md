# Liquidity Sweep Reversal Trading System (Smart Money Concept)

A Python-based trading system that detects **liquidity sweeps** (fake breakouts)
and trades the **reversal**, inspired by Smart Money Concepts (SMC) in technical
analysis.

## What it does

1. **Finds liquidity zones** — clusters of equal (or near-equal) swing highs
   and swing lows, where stop-losses and breakout orders tend to bunch up.
2. **Detects sweeps** — price wicks beyond a zone (triggering those stops/orders)
   then closes back inside it within a few bars. That's the "fake breakout".
3. **Enters reversal trades** on the next bar after a sweep confirms, with a
   stop-loss just beyond the sweep wick and a take-profit at a fixed
   risk/reward multiple.
4. **Simulates every trade** bar-by-bar to see whether the stop or the target
   is hit first, and tracks equity over time.
5. **Reports performance**: win rate, total return, max drawdown, profit factor.
6. **Visualizes everything**: an annotated 2D candlestick chart (zones, sweeps,
   entries/exits) and a 3D chart (time × price × volatility) with trades overlaid.

## Project structure

```
liquidity_sweep_system/
├── main.py                  # entry point — runs the full pipeline
├── config.py                 # all tunable strategy parameters
├── sample_data_generator.py  # creates a demo ohlc.csv with engineered sweeps
├── requirements.txt
├── core/
│   ├── data.py                # CSV loading & validation
│   ├── zones.py               # swing point + liquidity zone detection
│   ├── sweeps.py               # sweep (fake breakout) detection
│   ├── simulator.py           # trade simulation engine
│   ├── metrics.py             # win rate / return / drawdown / profit factor
│   └── visualize.py           # 2D + 3D charting
└── output/                    # chart_2d.png / chart_3d.png get written here
```

## How to run it

### 1. Install dependencies
```bash
pip install pandas numpy matplotlib
```
(or `pip install -r requirements.txt`)

### 2. Get some OHLC data
Either use the built-in generator to create a demo dataset with realistic
engineered sweep patterns:
```bash
python sample_data_generator.py
```
This writes `ohlc.csv` with columns `date, open, high, low, close, volume`.

Or drop in your own CSV with at least `date, open, high, low, close` columns
(volume is optional) and name it `ohlc.csv`, or pass `--file yourdata.csv`.

### 3. Run the system
```bash
python main.py
```
This prints a step-by-step log (zones found, sweeps found, trades executed),
a performance report, and pops up the 2D and 3D charts. PNGs are also saved
to `output/`.

To skip the pop-up windows (e.g. running headless / over SSH):
```bash
python main.py --no-show
```

## Tuning the strategy

Everything is in `config.py` — no need to touch the core logic:

| Parameter | What it controls |
|---|---|
| `swing_lookback` | How many bars on each side confirm a swing high/low (fractal size) |
| `equal_level_tolerance` | How close two swings need to be (%) to count as "equal" |
| `min_zone_touches` | Minimum swings clustered together to form a liquidity zone |
| `sweep_confirmation_bars` | Max bars allowed for price to close back inside the zone after the wick |
| `sweep_wick_min_pct` | Minimum wick size beyond the zone to filter out noise |
| `risk_reward_ratio` | Take-profit distance as a multiple of stop-loss distance |
| `stop_buffer_pct` | Extra cushion beyond the sweep wick for the stop-loss |
| `risk_per_trade_pct` | % of equity risked per trade (used for position sizing) |
| `starting_capital` | Starting account equity for the simulation |

## How the logic works (short version)

- **Zones**: a bar is a "swing high" if its high is the highest in a window of
  `swing_lookback` bars on each side (same idea for swing lows). Swing highs
  that land within `equal_level_tolerance` of each other get clustered into a
  resistance zone; swing lows form support zones the same way.
- **Sweeps**: once a zone exists, we watch for a bar whose high pierces above
  a resistance zone (or low pierces below a support zone) by at least
  `sweep_wick_min_pct`. If price closes back on the "inside" of that zone
  within `sweep_confirmation_bars`, that's a confirmed sweep.
- **Trades**: enter at the open of the bar after confirmation, in the reversal
  direction. Stop-loss sits just beyond the sweep's extreme wick; take-profit
  is `risk_reward_ratio` × the stop distance away. Each zone can only be swept
  (and traded) once.

## Extending it

- Swap `sample_data_generator.py` for a real data feed (exchange API, broker
  export, etc.) — just make sure the CSV has the required columns.
- `core/simulator.py` currently assumes one trade at a time per zone with no
  overlapping positions tracked against each other — extend it if you want
  portfolio-level position sizing across concurrent trades.
- `core/zones.py`'s clustering is intentionally simple (sequential clustering
  on sorted prices). For noisier data you may want a proper density-based
  clustering approach.

## Background reading

- [Support and resistance](https://en.wikipedia.org/wiki/Support_and_resistance)
- [Stop hunting](https://en.wikipedia.org/wiki/Stop_hunting)
- [Technical analysis](https://en.wikipedia.org/wiki/Technical_analysis)
- [Risk management](https://en.wikipedia.org/wiki/Risk_management)
- [Backtesting](https://en.wikipedia.org/wiki/Backtesting)

## Disclaimer

This is an educational backtesting tool, not financial advice. Past
performance in a backtest does not guarantee future results. Always paper
trade and validate thoroughly before risking real capital.
