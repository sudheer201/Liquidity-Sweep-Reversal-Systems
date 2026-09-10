"""
core/zones.py
-------------
Step 1 of the pipeline: find "liquidity zones".

In Smart Money Concepts, liquidity pools sit just beyond clusters of equal
(or near-equal) swing highs and swing lows, because that's where retail
stop-losses and breakout orders bunch up. We:

  1. Find swing highs/lows (fractals) using a simple lookback window.
  2. Cluster swings whose prices are within a small tolerance of each other.
  3. Keep clusters with at least `min_zone_touches` swings -> these are our
     liquidity zones (resistance zones from equal highs, support zones from
     equal lows).
"""

from dataclasses import dataclass, field
from typing import List, Literal
import pandas as pd


@dataclass
class LiquidityZone:
    kind: Literal["resistance", "support"]   # resistance = equal highs, support = equal lows
    level: float                              # average price of the cluster
    touches: List[int] = field(default_factory=list)  # bar indices that make up this zone
    swept: bool = False                       # set True once a sweep has consumed this zone


def find_swing_points(df: pd.DataFrame, lookback: int) -> pd.DataFrame:
    """
    Mark each bar as a swing high and/or swing low.

    A bar `i` is a swing high if its `high` is the maximum among the
    `lookback` bars on either side. Same idea (minimum) for swing lows.
    """
    df = df.copy()
    n = len(df)
    is_high = [False] * n
    is_low = [False] * n

    for i in range(lookback, n - lookback):
        window_high = df["high"].iloc[i - lookback: i + lookback + 1]
        window_low = df["low"].iloc[i - lookback: i + lookback + 1]

        if df["high"].iloc[i] == window_high.max():
            is_high[i] = True
        if df["low"].iloc[i] == window_low.min():
            is_low[i] = True

    df["swing_high"] = is_high
    df["swing_low"] = is_low
    return df


def _cluster_levels(points: List[tuple], tolerance: float) -> List[List[tuple]]:
    """
    Cluster (bar_index, price) points whose prices are within `tolerance`
    (relative) of a running cluster average. Points must be price-sorted first.
    """
    if not points:
        return []

    points = sorted(points, key=lambda p: p[1])
    clusters = [[points[0]]]

    for point in points[1:]:
        cluster_avg = sum(p[1] for p in clusters[-1]) / len(clusters[-1])
        if abs(point[1] - cluster_avg) / cluster_avg <= tolerance:
            clusters[-1].append(point)
        else:
            clusters.append([point])

    return clusters


def detect_liquidity_zones(df: pd.DataFrame, config: dict) -> List[LiquidityZone]:
    """
    Full zone-detection pipeline: find swings, cluster equal highs into
    resistance zones and equal lows into support zones.
    """
    lookback = config["swing_lookback"]
    tolerance = config["equal_level_tolerance"]
    min_touches = config["min_zone_touches"]

    swings = find_swing_points(df, lookback)

    high_points = [(i, row.high) for i, row in swings[swings["swing_high"]].iterrows()]
    low_points = [(i, row.low) for i, row in swings[swings["swing_low"]].iterrows()]

    zones: List[LiquidityZone] = []

    for cluster in _cluster_levels(high_points, tolerance):
        if len(cluster) >= min_touches:
            avg_level = sum(p[1] for p in cluster) / len(cluster)
            zones.append(LiquidityZone(
                kind="resistance",
                level=avg_level,
                touches=[p[0] for p in cluster],
            ))

    for cluster in _cluster_levels(low_points, tolerance):
        if len(cluster) >= min_touches:
            avg_level = sum(p[1] for p in cluster) / len(cluster)
            zones.append(LiquidityZone(
                kind="support",
                level=avg_level,
                touches=[p[0] for p in cluster],
            ))

    # zones must be usable going forward -> anchor each zone's "start bar"
    # at the bar of its last touch, so sweeps can only happen after the zone
    # actually exists
    for z in zones:
        z.touches.sort()

    return zones
