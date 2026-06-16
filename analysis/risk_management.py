"""Risk Management — calculates position size, validates R:R, risk per trade"""


class RiskManager:
    DEFAULT_RISK_PCT = 1.0   # 1% per trade
    MIN_RR = 1.5             # Minimum R:R accepted
    MAX_RISK_PCT = 2.0

    def validate_signal(self, entry: float, sl: float, tp: float) -> bool:
        risk = abs(entry - sl)
        reward = abs(tp - entry)
        if risk == 0:
            return False
        return (reward / risk) >= self.MIN_RR

    def calc_position_size(
        self,
        account_balance: float,
        entry: float,
        sl: float,
        risk_pct: float = DEFAULT_RISK_PCT,
        pip_value: float = 10.0,  # per standard lot
    ) -> dict:
        risk_amount = account_balance * (risk_pct / 100)
        sl_pips = abs(entry - sl) / 0.0001
        lots = risk_amount / (sl_pips * pip_value) if sl_pips > 0 else 0
        return {
            "lots": round(lots, 2),
            "risk_amount": round(risk_amount, 2),
            "sl_pips": round(sl_pips, 1),
            "risk_pct": risk_pct,
        }

    def get_risk_label(self, confidence: int) -> str:
        if confidence >= 75:
            return "🟢 Высокое качество"
        if confidence >= 55:
            return "🟡 Среднее качество"
        return "🔴 Низкое качество"
