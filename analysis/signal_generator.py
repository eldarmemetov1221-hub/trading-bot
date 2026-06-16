"""
Signal Generator — combines SMC analysis across multiple timeframes
to produce high-confluence trade setups with entry, SL, TP
"""
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime, timezone

from .smc_analysis import SMCAnalyzer, SMCResult, Bias, SignalType, OrderBlock, FVG
from .market_data import MarketDataFetcher, HTF_MAP
from .risk_management import RiskManager


@dataclass
class TradeSignal:
    symbol: str
    signal_type: SignalType
    entry: float
    sl: float
    tp1: float
    tp2: float
    tp3: float
    rr_ratio: float
    confidence: int           # 0-100
    timeframe: str
    htf_bias: str
    setup_type: str           # e.g. "OB + FVG Confluence"
    description: str
    confluences: list = field(default_factory=list)
    market_phase: str = ""    # "accumulation"|"distribution"|"expansion"|"reversal"
    session: str = ""         # "London"|"NY"|"Asia"
    timestamp: str = ""
    invalidation: float = 0.0
    pip_value: float = 0.0001


STRATEGIES = {
    "OB_RETEST": "Order Block Retest",
    "FVG_FILL": "Fair Value Gap Fill",
    "OB_FVG": "OB + FVG Confluence",
    "CHOCH_ENTRY": "CHoCH Entry",
    "LIQUIDITY_SWEEP": "Liquidity Sweep + Reversal",
    "BOS_RETEST": "BOS Retest",
    "DISCOUNT_OB": "Discount Zone + OB",
    "PREMIUM_FVG": "Premium Zone + FVG",
}


class SignalGenerator:
    def __init__(self):
        self.analyzer = SMCAnalyzer(swing_length=5)
        self.fetcher = MarketDataFetcher()
        self.risk_mgr = RiskManager()

    async def close(self):
        await self.fetcher.close()

    async def generate_signal(self, symbol: str, timeframe: str) -> Optional[TradeSignal]:
        htf = HTF_MAP.get(timeframe, "4h")
        try:
            df_ltf = await self.fetcher.get_ohlcv(symbol, timeframe, 300)
            df_htf = await self.fetcher.get_ohlcv(symbol, htf, 200)
        except Exception as e:
            return None

        if len(df_ltf) < 50 or len(df_htf) < 30:
            return None

        ltf_result = self.analyzer.analyze(df_ltf)
        htf_result = self.analyzer.analyze(df_htf)

        signal = self._build_signal(symbol, timeframe, ltf_result, htf_result, df_ltf)
        return signal

    def _build_signal(
        self,
        symbol: str,
        timeframe: str,
        ltf: SMCResult,
        htf: SMCResult,
        df: pd.DataFrame,
    ) -> Optional[TradeSignal]:
        price = ltf.current_price
        bias = htf.bias
        confluences = []
        confidence = 30

        # Base: HTF bias
        if bias == Bias.BULLISH:
            signal_type = SignalType.LONG
            confluences.append("✅ HTF Bullish Structure")
            confidence += 10
        elif bias == Bias.BEARISH:
            signal_type = SignalType.SHORT
            confluences.append("✅ HTF Bearish Structure")
            confidence += 10
        else:
            # Neutral — use LTF bias
            if ltf.bias == Bias.BULLISH:
                signal_type = SignalType.LONG
            elif ltf.bias == Bias.BEARISH:
                signal_type = SignalType.SHORT
            else:
                return None

        # Check premium/discount
        eq = htf.equilibrium
        if signal_type == SignalType.LONG and price < eq:
            confluences.append("✅ Price in Discount Zone (below EQ)")
            confidence += 15
        elif signal_type == SignalType.SHORT and price > eq:
            confluences.append("✅ Price in Premium Zone (above EQ)")
            confidence += 15
        else:
            confidence -= 5

        # Order Block
        ob = ltf.nearest_ob
        entry_zone = None
        sl = None
        setup_type = "Structure Bias"

        if ob:
            ob_mid = (ob.top + ob.bottom) / 2
            if signal_type == SignalType.LONG and price > ob.top:
                # Price above OB, wait for retest
                entry_zone = (ob.bottom, ob.top)
                entry = ob_mid
                sl = ob.bottom * 0.9998
                confluences.append(f"✅ Bullish OB [{ob.bottom:.5f} - {ob.top:.5f}]")
                confidence += 20
                setup_type = "OB_RETEST"
            elif signal_type == SignalType.SHORT and price < ob.bottom:
                entry_zone = (ob.bottom, ob.top)
                entry = ob_mid
                sl = ob.top * 1.0002
                confluences.append(f"✅ Bearish OB [{ob.bottom:.5f} - {ob.top:.5f}]")
                confidence += 20
                setup_type = "OB_RETEST"
            else:
                entry = price
        else:
            entry = price

        # FVG
        fvg = ltf.nearest_fvg
        if fvg:
            fvg_mid = (fvg.top + fvg.bottom) / 2
            if signal_type == SignalType.LONG and fvg.direction == "bullish":
                if entry_zone:
                    # Double confluence
                    entry = max(fvg_mid, ob_mid) if ob else fvg_mid
                    confluences.append(f"✅ Bullish FVG [{fvg.bottom:.5f} - {fvg.top:.5f}]")
                    confidence += 15
                    setup_type = "OB_FVG"
                else:
                    entry = fvg_mid
                    sl = fvg.bottom * 0.9998
                    confluences.append(f"✅ Bullish FVG [{fvg.bottom:.5f} - {fvg.top:.5f}]")
                    confidence += 12
                    setup_type = "FVG_FILL"
            elif signal_type == SignalType.SHORT and fvg.direction == "bearish":
                if entry_zone:
                    entry = min(fvg_mid, ob_mid) if ob else fvg_mid
                    confluences.append(f"✅ Bearish FVG [{fvg.bottom:.5f} - {fvg.top:.5f}]")
                    confidence += 15
                    setup_type = "OB_FVG"
                else:
                    entry = fvg_mid
                    sl = fvg.top * 1.0002
                    confluences.append(f"✅ Bearish FVG [{fvg.bottom:.5f} - {fvg.top:.5f}]")
                    confidence += 12
                    setup_type = "FVG_FILL"

        # Liquidity
        liq = ltf.nearest_liquidity
        if liq:
            confluences.append(f"✅ Liquidity Target: {liq.price:.5f} ({liq.kind})")
            confidence += 10

        # CHoCH / BOS
        if ltf.choch_indices:
            confluences.append("✅ Recent CHoCH (Change of Character)")
            confidence += 8
        if ltf.bos_indices:
            confluences.append("✅ BOS Confirmed (Break of Structure)")
            confidence += 7

        # Structure strength
        confidence += int(ltf.structure_strength * 10)
        confidence = min(95, max(20, confidence))

        # Calculate SL if not set
        if sl is None:
            atr = self._calc_atr(df)
            if signal_type == SignalType.LONG:
                sl = entry - 2.0 * atr
            else:
                sl = entry + 2.0 * atr

        # Calculate TPs with R:R
        risk = abs(entry - sl)
        if signal_type == SignalType.LONG:
            tp1 = entry + risk * 1.5
            tp2 = entry + risk * 2.5
            tp3 = liq.price if liq and liq.kind == "BSL" else entry + risk * 4.0
        else:
            tp1 = entry - risk * 1.5
            tp2 = entry - risk * 2.5
            tp3 = liq.price if liq and liq.kind == "SSL" else entry - risk * 4.0

        rr = abs(tp2 - entry) / risk if risk > 0 else 0

        # Market phase
        phase = self._detect_phase(ltf, htf)

        # Session
        session = self._get_session()

        desc = self._build_description(signal_type, setup_type, bias, phase, confluences, confidence)

        return TradeSignal(
            symbol=symbol,
            signal_type=signal_type,
            entry=round(entry, 5),
            sl=round(sl, 5),
            tp1=round(tp1, 5),
            tp2=round(tp2, 5),
            tp3=round(tp3, 5),
            rr_ratio=round(rr, 2),
            confidence=confidence,
            timeframe=timeframe,
            htf_bias=bias.value,
            setup_type=STRATEGIES.get(setup_type, setup_type),
            description=desc,
            confluences=confluences,
            market_phase=phase,
            session=session,
            timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            invalidation=round(sl, 5),
        )

    def _calc_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        high = df["high"]
        low = df["low"]
        close = df["close"].shift(1)
        tr = pd.concat([high - low, (high - close).abs(), (low - close).abs()], axis=1).max(axis=1)
        return tr.rolling(period).mean().iloc[-1]

    def _detect_phase(self, ltf: SMCResult, htf: SMCResult) -> str:
        if htf.bias == Bias.BULLISH and ltf.bias == Bias.BULLISH:
            return "Expansion (Bullish)"
        if htf.bias == Bias.BEARISH and ltf.bias == Bias.BEARISH:
            return "Expansion (Bearish)"
        if htf.bias != ltf.bias:
            return "Reversal / CHoCH"
        if ltf.structure_strength < 0.4:
            return "Accumulation / Consolidation"
        return "Distribution"

    def _get_session(self) -> str:
        h = datetime.now(timezone.utc).hour
        if 7 <= h < 16:
            return "🇬🇧 London Session"
        if 13 <= h < 22:
            return "🇺🇸 New York Session"
        return "🌏 Asia Session"

    def _build_description(self, signal_type, setup, bias, phase, confluences, confidence) -> str:
        direction = "LONG 📈" if signal_type == SignalType.LONG else "SHORT 📉"
        lines = [
            f"Направление: {direction}",
            f"Фаза рынка: {phase}",
            f"Стратегия: {STRATEGIES.get(setup, setup)}",
            f"HTF Bias: {bias.value.upper()}",
        ]
        return "\n".join(lines)
