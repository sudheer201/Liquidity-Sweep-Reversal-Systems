"""
core/sweeps.py
---------------
Step 2 of the pipeline: detect liquidity sweeps.

A sweep is the classic "stop hunt" / fake breakout pattern:
  - Resistance sweep: price wicks ABOVE a resistance zone (triggering
    breakout buyers + stop-losses of shorts) but then CLOSES back BELOW
    the zone within `sweep_confirmation_bars` -> likely reversal down.
  - Support sweep: mirror image, price wicks BELOW support then closes
    back ABOVE it -> likely reversal up.

Each confirmed sweep becomes a candidate reversal trade signal.
"""

from dataclasses import dataclass
from typing import List, Literal
import pandas as pd

from .zones import LiquidityZone


@dataclass
class Sweep:
    zone: LiquidityZone
    direction: Literal["bearish", "bullish"]  # bearish = resistance swept -> expect price to fall
    sweep_bar: int          # bar index of the wick that pierced the zone
    confirm_bar: int        # bar index where the close moved back inside the zone
    sweep_price: float      # the extreme (wick) price of the sweep


def detect_sweeps(df: pd.DataFrame, zones: List[LiquidityZone], config: dict) -> List[Sweep]:
    """
    Scan forward through the candles and look for zones being swept.
    Only bars AFTER a zone's last confirming touch are eligible, since the
    zone doesn't exist as a liquidity pool before that.
    """
    confirm_window = config["sweep_confirmation_bars"]
    min_wick_pct = config["sweep_wick_min_pct"]

    sweeps: List[Sweep] = []

    for zone in zones:
        zone_start_bar = max(zone.touches) + 1  # zone becomes "live" right after its last touch
        i = zone_start_bar

        while i < len(df):
            bar = df.iloc[i]

            if zone.kind == "resistance" and not zone.swept:
                wick_beyond = (bar.high - zone.level) / zone.level
                if bar.high > zone.level and wick_beyond >= min_wick_pct:
                    # look ahead up to confirm_window bars for a close back below the zone
                    confirmed = False
                    for j in range(i, min(i + confirm_window, len(df))):
                        if df.iloc[j].close < zone.level:
                            sweeps.append(Sweep(
                                zone=zone,
                                direction="bearish",
                                sweep_bar=i,
                                confirm_bar=j,
                                sweep_price=bar.high,
                            ))
                            zone.swept = True
                            confirmed = True
                            break
                    if confirmed:
                        break  # zone consumed, move to next zone

            if zone.kind == "support" and not zone.swept:
                wick_beyond = (zone.level - bar.low) / zone.level
                if bar.low < zone.level and wick_beyond >= min_wick_pct:
                    confirmed = False
                    for j in range(i, min(i + confirm_window, len(df))):
                        if df.iloc[j].close > zone.level:
                            sweeps.append(Sweep(
                                zone=zone,
                                direction="bullish",
                                sweep_bar=i,
                                confirm_bar=j,
                                sweep_price=bar.low,
                            ))
                            zone.swept = True
                            confirmed = True
                            break
                    if confirmed:
                        break

            i += 1

    sweeps.sort(key=lambda s: s.confirm_bar)
    return sweeps
