from sqlalchemy.orm import Session
from app.core.models import Trade, SystemEvent
from app.services.market_data import market_data
from app.services.risk import risk_shield

class TradingEngine:
    def paper_trade(self, db: Session, side: str, amount_eur: float, reason: str, force_manual: bool = True) -> dict:
        if not force_manual:
            allowed, risk_reason = risk_shield.can_trade(amount_eur)
            if not allowed:
                db.add(SystemEvent(level="warning", message=risk_reason, requires_attention=True))
                db.commit()
                return {"executed": False, "reason": risk_reason}
        else:
            if risk_shield.settings.emergency_stop:
                msg = "Not-Aus ist aktiv. Manueller Paper-Trade wurde blockiert."
                db.add(SystemEvent(level="warning", message=msg, requires_attention=True))
                db.commit()
                return {"executed": False, "reason": msg}
            if amount_eur > risk_shield.settings.max_trade_size_eur:
                msg = "Trade-Betrag ueberschreitet maximales Risiko."
                db.add(SystemEvent(level="warning", message=msg, requires_attention=True))
                db.commit()
                return {"executed": False, "reason": msg}

        tick = market_data.get_btc_eur_price()
        btc_amount = amount_eur / tick["price_eur"]
        trade = Trade(side=side.upper(), amount_eur=amount_eur, btc_amount=btc_amount, price_eur=tick["price_eur"], reason=reason)
        db.add(trade)
        db.add(SystemEvent(level="info", message=f"Paper-Trade ausgefuehrt: {side.upper()} {amount_eur} EUR BTC"))
        db.commit()
        db.refresh(trade)
        return {"executed": True, "trade_id": trade.id, "price_eur": tick["price_eur"], "btc_amount": btc_amount}

trading_engine = TradingEngine()
