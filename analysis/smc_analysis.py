"""
Smart Money Concepts (SMC) Analysis Engine
Implements: Order Blocks, FVG, CHoCH, BOS, Liquidity Zones,
            Market Structure, Imbalances, Stop Hunt detection
"""
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class Bias(Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class SignalType(Enum):
    LONG = "LONG"
    SHORT = "SHORT"


@dataclass
class SwingPoint:
    index: int
    price: float
    kind: str  # 'HH', 'HL', 'LH', 'LL'
    timestamp: object = None


@dataclass
class OrderBlock:
    top: float
    bottom: float
    direction: str  # 'bullish' | 'bearish'
    index: int
    strength: float = 0.0
    tested: bool = False
    timestamp: object = None


@dataclass
class FVG:
    top: float
    bottom: float
    direction: str
    index: int
    filled: bool = False
    fill_pct: float = 0.0
    timestamp: object = None


@dataclass
class LiquidityLevel:
    price: float
    kind: str  # 'BSL' (buyside) | 'SSL' (sellside)
    strength: int = 1
    swept: bool = False
    index: int = 0


@dataclass
class SMCResult:
    bias: Bias
    swing_highs: list = field(default_factory=list)
    swing_lows: list = field(default_factory=list)
    order_blocks: list = field(default_factory=list)
    fvgs: list = field(default_factory=list)
    liquidity_levels: list = field(default_factory=list)
    choch_indices: list = field(default_factory=list)
    bos_indices: list = field(default_factory=list)
    premium_zone: tuple = (0, 0)
    discount_zone: tuple = (0, 0)
    equilibrium: float = 0.0
    current_price: float = 0.0
    nearest_ob: Optional[OrderBlock] = None
    nearest_fvg: Optional[FVG] = None
    nearest_liquidity: Optional[LiquidityLevel] = None
    structure_strength: float = 0.0


class SMCAnalyzer:
    def __init__(self, swing_length: int = 5):
        self.swing_length = swing_length

    def analyze(self, df: pd.DataFrame) -> SMCResult:
        df = df.copy().reset_index(drop=True)
        current_price = df["close"].iloc[-1]

        swing_highs, swing_lows = self._find_swings(df)
        bias = self._determine_bias(swing_highs, swing_lows)
        order_blocks = self._find_order_blocks(df, swing_highs, swing_lows, bias)
        fvgs = self._find_fvg(df)
        liquidity = self._find_liquidity(df, swing_highs, swing_lows)
        choch_idx, bos_idx = self._find_structure_breaks(df, swing_highs, swing_lows, bias)
        premium, discount, eq = self._calc_premium_discount(swing_highs, swing_lows, df)
        structure_strength = self._calc_structure_strength(swing_highs, swing_lows)

        # Find nearest untested OB in bias direction
        nearest_ob = self._nearest_ob(current_price, order_blocks, bias)
        nearest_fvg = self._nearest_fvg(current_price, fvgs, bias)
        nearest_liq = self._nearest_liquidity(current_price, liquidity, bias)

        return SMCResult(
            bias=bias,
            swing_highs=swing_highs,
            swing_lows=swing_lows,
            order_blocks=order_blocks,
            fvgs=fvgs,
            liquidity_levels=liquidity,
            choch_indices=choch_idx,
            bos_indices=bos_idx,
            premium_zone=premium,
            discount_zone=discount,
            equilibrium=eq,
            current_price=current_price,
            nearest_ob=nearest_ob,
            nearest_fvg=nearest_fvg,
            nearest_liquidity=nearest_liq,
            structure_strength=structure_strength,
        )

    def _find_swings(self, df: pd.DataFrame):
        n = self.swing_length
        highs, lows = [], []
        for i in range(n, len(df) - n):
            window_h = df["high"].iloc[i - n: i + n + 1]
            window_l = df["low"].iloc[i - n: i + n + 1]
            if df["high"].iloc[i] == window_h.max():
                highs.append(i)
            if df["low"].iloc[i] == window_l.min():
                lows.append(i)
        return highs, lows

    def _determine_bias(self, swing_highs: list, swing_lows: list) -> Bias:
        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return Bias.NEUTRAL
        # Check last 2 swing highs and lows for trend
        recent_h = swing_highs[-2:]
        recent_l = swing_lows[-2:]
        hh = recent_h[1] > recent_h[0]  # Higher High
        hl = recent_l[1] > recent_l[0]  # Higher Low
        lh = recent_h[1] < recent_h[0]  # Lower High
        ll = recent_l[1] < recent_l[0]  # Lower Low
        if hh and hl:
            return Bias.BULLISH
        if lh and ll:
            return Bias.BEARISH
        return Bias.NEUTRAL

    def _find_order_blocks(self, df, swing_highs, swing_lows, bias: Bias) -> list[OrderBlock]:
        obs = []
        # Bearish OB: last bearish candle before significant bullish move
        for i in range(2, len(df) - 2):
            candle = df.iloc[i]
            next_c = df.iloc[i + 1]
            # Bullish OB: last bearish candle before impulsive up move
            if candle["close"] < candle["open"]:  # bearish candle
                if next_c["close"] > candle["high"]:  # impulsive break above
                    strength = (next_c["close"] - next_c["open"]) / next_c["open"] * 100
                    ob = OrderBlock(
                        top=candle["high"], bottom=candle["low"],
                        direction="bullish", index=i,
                        strength=strength,
                        timestamp=df.index[i] if hasattr(df.index[i], "isoformat") else None,
                    )
                    obs.append(ob)
            # Bearish OB: last bullish candle before impulsive down move
            if candle["close"] > candle["open"]:  # bullish candle
                if next_c["close"] < candle["low"]:  # impulsive break below
                    strength = (next_c["open"] - next_c["close"]) / next_c["open"] * 100
                    ob = OrderBlock(
                        top=candle["high"], bottom=candle["low"],
                        direction="bearish", index=i,
                        strength=strength,
                        timestamp=df.index[i] if hasattr(df.index[i], "isoformat") else None,
                    )
                    obs.append(ob)

        # Mark tested OBs
        last_price = df["close"].iloc[-1]
        for ob in obs:
            later = df.iloc[ob.index + 1:]
            if ob.direction == "bullish":
                ob.tested = (later["low"] <= ob.top).any()
            else:
                ob.tested = (later["high"] >= ob.bottom).any()

        # Return recent untested OBs (last 20)
        return [ob for ob in obs if not ob.tested][-20:]

    def _find_fvg(self, df: pd.DataFrame) -> list[FVG]:
        fvgs = []
        for i in range(1, len(df) - 1):
            prev = df.iloc[i - 1]
            curr = df.iloc[i]
            nxt = df.iloc[i + 1]
            # Bullish FVG: gap between prev high and next low
            if nxt["low"] > prev["high"]:
                gap_size = nxt["low"] - prev["high"]
                if gap_size / prev["high"] > 0.0001:  # filter micro gaps
                    fvg = FVG(
                        top=nxt["low"], bottom=prev["high"],
                        direction="bullish", index=i,
                        timestamp=df.index[i] if hasattr(df.index[i], "isoformat") else None,
                    )
                    fvgs.append(fvg)
            # Bearish FVG: gap between prev low and next high
            if nxt["high"] < prev["low"]:
                gap_size = prev["low"] - nxt["high"]
                if gap_size / prev["low"] > 0.0001:
                    fvg = FVG(
                        top=prev["low"], bottom=nxt["high"],
                        direction="bearish", index=i,
                        timestamp=df.index[i] if hasattr(df.index[i], "isoformat") else None,
                    )
                    fvgs.append(fvg)

        # Check fill
        last_price = df["close"].iloc[-1]
        for fvg in fvgs:
            later = df.iloc[fvg.index + 2:]
            if fvg.direction == "bullish":
                touched = later["low"] <= fvg.top
                if touched.any():
                    fill_low = later.loc[touched, "low"].min()
                    fvg.fill_pct = min(100, (fvg.top - fill_low) / (fvg.top - fvg.bottom) * 100)
                    fvg.filled = fvg.fill_pct >= 90
            else:
                touched = later["high"] >= fvg.bottom
                if touched.any():
                    fill_high = later.loc[touched, "high"].max()
                    fvg.fill_pct = min(100, (fill_high - fvg.bottom) / (fvg.top - fvg.bottom) * 100)
                    fvg.filled = fvg.fill_pct >= 90

        return [f for f in fvgs if not f.filled][-15:]

    def _find_liquidity(self, df, swing_highs, swing_lows) -> list[LiquidityLevel]:
        levels = []
        close = df["close"].iloc[-1]
        # Equal highs/lows = liquidity pools
        highs = [df["high"].iloc[i] for i in swing_highs]
        lows = [df["low"].iloc[i] for i in swing_lows]

        for i, h in enumerate(highs):
            similar = [x for x in highs if abs(x - h) / h < 0.001 and x != h]
            strength = len(similar) + 1
            swept = df["high"].iloc[swing_highs[i] + 1:].max() > h if swing_highs[i] + 1 < len(df) else False
            levels.append(LiquidityLevel(
                price=h, kind="BSL", strength=strength,
                swept=swept, index=swing_highs[i],
            ))

        for i, l in enumerate(lows):
            similar = [x for x in lows if abs(x - l) / l < 0.001 and x != l]
            strength = len(similar) + 1
            swept = df["low"].iloc[swing_lows[i] + 1:].min() < l if swing_lows[i] + 1 < len(df) else False
            levels.append(LiquidityLevel(
                price=l, kind="SSL", strength=strength,
                swept=swept, index=swing_lows[i],
            ))

        return [l for l in levels if not l.swept]

    def _find_structure_breaks(self, df, swing_highs, swing_lows, bias: Bias):
        choch, bos = [], []
        if not swing_highs or not swing_lows:
            return choch, bos

        close = df["close"]
        # BOS: break of structure in trend direction
        # CHoCH: change of character (opposite direction break)
        for i in range(1, len(swing_highs)):
            prev_h = df["high"].iloc[swing_highs[i - 1]]
            curr_h = df["high"].iloc[swing_highs[i]]
            # Price breaks above previous high after bullish swing
            later_slice = close.iloc[swing_highs[i]:]
            if (later_slice > prev_h).any():
                idx = later_slice[later_slice > prev_h].index[0]
                if bias == Bias.BULLISH:
                    bos.append(int(idx))
                else:
                    choch.append(int(idx))

        for i in range(1, len(swing_lows)):
            prev_l = df["low"].iloc[swing_lows[i - 1]]
            later_slice = close.iloc[swing_lows[i]:]
            if (later_slice < prev_l).any():
                idx = later_slice[later_slice < prev_l].index[0]
                if bias == Bias.BEARISH:
                    bos.append(int(idx))
                else:
                    choch.append(int(idx))

        return choch[-5:], bos[-5:]

    def _calc_premium_discount(self, swing_highs, swing_lows, df):
        if not swing_highs or not swing_lows:
            p = df["close"].iloc[-1]
            return (p, p), (p, p), p
        recent_high = max(df["high"].iloc[h] for h in swing_highs[-3:])
        recent_low = min(df["low"].iloc[l] for l in swing_lows[-3:])
        mid = (recent_high + recent_low) / 2
        premium = (mid, recent_high)
        discount = (recent_low, mid)
        return premium, discount, mid

    def _calc_structure_strength(self, swing_highs, swing_lows) -> float:
        if len(swing_highs) < 3 or len(swing_lows) < 3:
            return 0.5
        hh_count = sum(1 for i in range(1, len(swing_highs)) if swing_highs[i] > swing_highs[i - 1])
        ll_count = sum(1 for i in range(1, len(swing_lows)) if swing_lows[i] < swing_lows[i - 1])
        return round(max(hh_count, ll_count) / max(len(swing_highs) - 1, 1), 2)

    def _nearest_ob(self, price, obs, bias: Bias) -> Optional[OrderBlock]:
        direction = "bullish" if bias == Bias.BULLISH else "bearish"
        candidates = [ob for ob in obs if ob.direction == direction]
        if not candidates:
            return None
        if bias == Bias.BULLISH:
            below = [ob for ob in candidates if ob.top < price]
            return max(below, key=lambda x: x.top) if below else None
        else:
            above = [ob for ob in candidates if ob.bottom > price]
            return min(above, key=lambda x: x.bottom) if above else None

    def _nearest_fvg(self, price, fvgs, bias: Bias) -> Optional[FVG]:
        direction = "bullish" if bias == Bias.BULLISH else "bearish"
        candidates = [f for f in fvgs if f.direction == direction]
        if not candidates:
            return None
        if bias == Bias.BULLISH:
            below = [f for f in candidates if f.top < price]
            return max(below, key=lambda x: x.top) if below else None
        else:
            above = [f for f in candidates if f.bottom > price]
            return min(above, key=lambda x: x.bottom) if above else None

    def _nearest_liquidity(self, price, levels, bias: Bias) -> Optional[LiquidityLevel]:
        if not levels:
            return None
        if bias == Bias.BULLISH:
            above = [l for l in levels if l.kind == "BSL" and l.price > price]
            return min(above, key=lambda x: x.price) if above else None
        else:
            below = [l for l in levels if l.kind == "SSL" and l.price < price]
            return max(below, key=lambda x: x.price) if below else None
