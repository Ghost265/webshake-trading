from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, Dict, Any

@dataclass
class PaperTrade:
    id: int
    symbol: str
    side: str
    entry_price: float
    amount_btc: float
    invested_eur: float
    opened_at: str
    status: str = "OPEN"
    exit_price: Optional[float] = None
    closed_at: Optional[str] = None
    pnl_eur: float = 0.0
    pnl_pct: float = 0.0
    reason: str = ""

class PaperTradingEngine:
    def __init__(self, starting_balance_eur: float = 50.0, max_open_trades: int = 1):
        self.starting_balance_eur = starting_balance_eur
        self.balance_eur = starting_balance_eur
        self.max_open_trades = max_open_trades
        self.trades: list[PaperTrade] = []
        self.next_id = 1

    def open_trades(self):
        return [t for t in self.trades if t.status == "OPEN"]

    def can_buy(self) -> bool:
        return len(self.open_trades()) < self.max_open_trades and self.balance_eur > 0

    def buy(self, price_eur: float, confidence: float, reason: str = "KI Paper-Buy") -> Dict[str, Any]:
        if not self.can_buy():
            return {"ok": False, "message": "Maximale offene Paper-Trades erreicht oder kein Guthaben."}
        invest = round(self.balance_eur, 2)
        amount = invest / price_eur if price_eur else 0
        trade = PaperTrade(
            id=self.next_id, symbol="BTC-EUR", side="BUY", entry_price=price_eur,
            amount_btc=amount, invested_eur=invest, opened_at=datetime.now().isoformat(timespec="seconds"),
            reason=f"{reason} · Confidence {confidence:.2f}"
        )
        self.next_id += 1
        self.balance_eur -= invest
        self.trades.append(trade)
        return {"ok": True, "trade": asdict(trade)}

    def sell_open(self, price_eur: float, reason: str = "KI Paper-Sell") -> Dict[str, Any]:
        open_trades = self.open_trades()
        if not open_trades:
            return {"ok": False, "message": "Kein offener Paper-Trade vorhanden."}
        trade = open_trades[0]
        value = trade.amount_btc * price_eur
        trade.exit_price = price_eur
        trade.closed_at = datetime.now().isoformat(timespec="seconds")
        trade.pnl_eur = round(value - trade.invested_eur, 4)
        trade.pnl_pct = round((trade.pnl_eur / trade.invested_eur) * 100, 4) if trade.invested_eur else 0
        trade.status = "CLOSED"
        trade.reason += f" | closed: {reason}"
        self.balance_eur += value
        return {"ok": True, "trade": asdict(trade)}

    def evaluate(self, action: str, price_eur: float, confidence: float, reason: str = "") -> Dict[str, Any]:
        action = (action or "HOLD").upper()
        if action == "BUY" and confidence >= 0.68:
            return self.buy(price_eur, confidence, reason or "KI Signal BUY")
        if action == "SELL" and confidence >= 0.62:
            return self.sell_open(price_eur, reason or "KI Signal SELL")
        return {"ok": True, "message": "HOLD / kein Paper-Trade ausgelöst", "action": action, "confidence": confidence}

    def status(self, current_price: float | None = None) -> Dict[str, Any]:
        open_trades = self.open_trades()
        floating = 0.0
        if current_price:
            for t in open_trades:
                floating += (t.amount_btc * current_price) - t.invested_eur
        return {
            "mode":"paper", "balance_eur": round(self.balance_eur, 4),
            "starting_balance_eur": self.starting_balance_eur,
            "open_trades": len(open_trades), "max_open_trades": self.max_open_trades,
            "floating_pnl_eur": round(floating, 4),
            "trades": [asdict(t) for t in self.trades[-150:]],
            "total_trades": len(self.trades)
        }
