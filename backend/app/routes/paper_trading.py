from fastapi import APIRouter
from pydantic import BaseModel
from app.services.paper_trading import PaperTradingEngine

router = APIRouter(prefix="/api/paper", tags=["paper-trading"])
engine = PaperTradingEngine(starting_balance_eur=50.0, max_open_trades=1)

class PaperDecision(BaseModel):
    action: str
    price_eur: float
    confidence: float = 0.0
    reason: str = ""

@router.get("/status")
def paper_status(current_price: float | None = None):
    return engine.status(current_price=current_price)

@router.post("/decision")
def paper_decision(decision: PaperDecision):
    return engine.evaluate(decision.action, decision.price_eur, decision.confidence, decision.reason)

@router.post("/reset")
def paper_reset():
    global engine
    engine = PaperTradingEngine(starting_balance_eur=50.0, max_open_trades=1)
    return {"ok": True, "message": "Paper-Trading zurückgesetzt", "status": engine.status()}
