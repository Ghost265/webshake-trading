from pydantic import BaseModel

class RiskSettings(BaseModel):
    daily_loss_limit_eur: float = 2.0
    max_open_trades: int = 1
    max_trade_size_eur: float = 5.0
    require_strategy_approval: bool = True
    auto_trading_enabled: bool = False
    emergency_stop: bool = False

class RiskShield:
    def __init__(self) -> None:
        self.settings = RiskSettings()

    def can_trade(self, amount_eur: float) -> tuple[bool, str]:
        if self.settings.emergency_stop:
            return False, "Not-Aus ist aktiv. Trading pausiert."
        if not self.settings.auto_trading_enabled:
            return False, "Auto-Trading ist deaktiviert. Paper-Trades sind nur manuell moeglich."
        if amount_eur > self.settings.max_trade_size_eur:
            return False, "Trade-Betrag ueberschreitet maximales Risiko."
        return True, "Trade erlaubt."

risk_shield = RiskShield()
