import json
import time
from pathlib import Path
from datetime import datetime, timedelta
from fastapi import Depends, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import uvicorn

from app.core.config import settings
from app.core.database import Base, engine, get_db, SessionLocal
from app.core.models import AIDecision, Setting, SystemEvent, Trade
from app.services.market_data import market_data
from app.services.risk import risk_shield, RiskSettings
from app.services.strategy import strategy_engine
from app.services.trading import trading_engine

Base.metadata.create_all(bind=engine)

ROOT_DIR = Path(__file__).resolve().parents[2]
VERSION_FILE = ROOT_DIR / "config" / "version.json"
APP_START_MONOTONIC = time.monotonic()
PAPER_START_DELAY_SECONDS = 60
BACKEND_STABLE = True
LAST_BACKEND_HEALTH_ERROR = ""


def reset_start_protection_timer() -> None:
    global APP_START_MONOTONIC
    APP_START_MONOTONIC = time.monotonic()


reset_start_protection_timer()


def load_version_info() -> dict:
    fallback = {"version": "v0.1.3-beta", "notes": []}
    try:
        if VERSION_FILE.exists():
            data = json.loads(VERSION_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("version"):
                return data
    except Exception:
        pass
    return fallback


def current_version() -> str:
    return str(load_version_info().get("version", "v0.1.3-beta"))


def load_risk_settings() -> None:
    db = SessionLocal()
    try:
        row = db.query(Setting).filter(Setting.key == "risk_settings").first()
        if row:
            risk_shield.settings = RiskSettings(**json.loads(row.value))
    except Exception:
        pass
    finally:
        db.close()


def save_setting(db: Session, key: str, value: dict) -> None:
    row = db.query(Setting).filter(Setting.key == key).first()
    payload = json.dumps(value, ensure_ascii=False)
    if row:
        row.value = payload
    else:
        db.add(Setting(key=key, value=payload))



def get_storage_limits(db: Session) -> dict:
    defaults = {
        "ai_decisions": 20000,
        "logs": 5000,
        "trades": 50000,
    }
    try:
        row = db.query(Setting).filter(Setting.key == "storage_limits").first()
        if row and row.value:
            data = json.loads(row.value)
            if isinstance(data, dict):
                defaults.update({k: int(v) for k, v in data.items() if k in defaults and int(v) > 0})
    except Exception:
        pass
    return defaults


def trim_table_by_id(db: Session, model, limit: int) -> int:
    if not limit or limit <= 0:
        return 0
    total = db.query(model).count()
    excess = total - int(limit)
    if excess <= 0:
        return 0
    ids = [row.id for row in db.query(model.id).order_by(model.id.asc()).limit(excess).all()]
    if not ids:
        return 0
    deleted = db.query(model).filter(model.id.in_(ids)).delete(synchronize_session=False)
    return int(deleted or 0)


def apply_storage_limits(db: Session) -> dict:
    limits = get_storage_limits(db)
    result = {
        "ai_decisions": trim_table_by_id(db, AIDecision, limits.get("ai_decisions", 20000)),
        "logs": trim_table_by_id(db, SystemEvent, limits.get("logs", 5000)),
        "trades": trim_table_by_id(db, Trade, limits.get("trades", 50000)),
    }
    if any(result.values()):
        db.commit()
    return result



def backend_is_stable() -> bool:
    try:
        test = market_data.get_btc_eur_price()
        if not isinstance(test, dict):
            return False
        if not test.get("price_eur"):
            return False
        return True
    except Exception:
        return False


def enforce_backend_safety(db: Session | None = None) -> dict:
    global BACKEND_STABLE, LAST_BACKEND_HEALTH_ERROR
    stable = backend_is_stable()
    BACKEND_STABLE = stable
    if not stable:
        LAST_BACKEND_HEALTH_ERROR = "Backend/Marktdaten nicht stabil erreichbar"
        risk_shield.settings.emergency_stop = True
        if db is not None:
            try:
                save_setting(db, "risk_settings", risk_shield.settings.model_dump())
                db.add(SystemEvent(level="critical", message="NOT-AUS automatisch aktiviert: Backend nicht stabil", requires_attention=True))
                db.commit()
            except Exception:
                db.rollback()
    return {
        "stable": stable,
        "emergency_stop": risk_shield.settings.emergency_stop,
        "error": LAST_BACKEND_HEALTH_ERROR if not stable else "",
    }


def store_ai_decision(db: Session, analysis: dict) -> AIDecision:
    if not BACKEND_STABLE:
        raise RuntimeError('KI-Daten werden nicht gespeichert: Backend nicht stabil')
    indicators = analysis.get("indicators", {}) or {}
    tick = analysis.get("tick", {}) or {}
    decision = AIDecision(
        mode="paper" if settings.paper_trading else "live",
        symbol=tick.get("symbol", "BTC-EUR"),
        action=analysis.get("action", "HOLD"),
        confidence=float(analysis.get("confidence", 0) or 0),
        price_eur=float(tick.get("price_eur", 0) or 0),
        trend=indicators.get("trend", "FLAT"),
        volatility_pct=float(indicators.get("volatility_20_samples_pct", 0) or 0),
        signal_strength=round(float(analysis.get("confidence", 0) or 0) * 100, 2),
        strategy=analysis.get("strategy", "ai-paper-v1.5.2"),
        reason=analysis.get("reason", ""),
        raw_json=json.dumps(analysis, ensure_ascii=False),
    )
    db.add(decision)
    db.commit()
    db.refresh(decision)
    apply_storage_limits(db)
    return decision


def calculate_paper_balance(db: Session) -> dict:
    start_eur = 50.0
    try:
        row = db.query(Setting).filter(Setting.key == "paper_start_eur").first()
        if row and row.value:
            start_eur = float(row.value)
    except Exception:
        start_eur = 50.0

    trades = db.query(Trade).filter(Trade.mode == "paper").order_by(Trade.id.asc()).all()

    eur = float(start_eur)
    btc = 0.0
    invested_eur = 0.0
    realized_eur = 0.0

    for t in trades:
        side = str(t.side or "").upper()
        amount_eur = float(t.amount_eur or 0)
        btc_amount = float(t.btc_amount or 0)

        if side == "BUY":
            eur -= amount_eur
            btc += btc_amount
            invested_eur += amount_eur
        elif side == "SELL":
            eur += amount_eur
            btc -= btc_amount
            realized_eur += amount_eur

    if abs(eur) < 0.000001:
        eur = 0.0
    if abs(btc) < 0.00000001:
        btc = 0.0

    tick = market_data.get_btc_eur_price()
    current_price = float(tick.get("price_eur", 0) or 0)
    btc_value = btc * current_price
    total = eur + btc_value
    pnl = total - start_eur
    pnl_pct = (pnl / start_eur * 100) if start_eur else 0.0

    return {
        "mode": "paper",
        "start_eur": round(start_eur, 2),
        "available_eur": round(eur, 2),
        "btc_amount": round(btc, 8),
        "btc_value_eur": round(btc_value, 2),
        "open_trades_value_eur": round(btc_value, 2),
        "current_price_eur": round(current_price, 2),
        "total_value_eur": round(total, 2),
        "profit_loss_eur": round(pnl, 2),
        "profit_loss_pct": round(pnl_pct, 4),
        "invested_eur": round(invested_eur, 2),
        "realized_eur": round(realized_eur, 2),
        "has_open_position": btc > 0.00000001,
        "trade_count": len(trades),
    }


def get_paper_position(db: Session) -> dict:
    trades = db.query(Trade).filter(Trade.mode == "paper").all()
    eur = 50.0
    btc = 0.0
    buy_count = 0
    sell_count = 0
    for t in trades:
        side = (t.side or "").upper()
        if side == "BUY":
            eur -= float(t.amount_eur or 0)
            btc += float(t.btc_amount or 0)
            buy_count += 1
        elif side == "SELL":
            eur += float(t.amount_eur or 0)
            btc -= float(t.btc_amount or 0)
            sell_count += 1
    tick = market_data.get_btc_eur_price()
    price = float(tick.get("price_eur", 0) or 0)
    return {
        "start_eur": 50.0,
        "available_eur": round(eur, 2),
        "btc_amount": round(max(btc, 0), 8),
        "btc_value_eur": round(max(btc, 0) * price, 2),
        "has_open_position": btc > 0.00000001,
        "buy_count": buy_count,
        "sell_count": sell_count,
        "price_eur": price,
    }


def maybe_execute_ai_paper_trade(db: Session, analysis: dict, decision: AIDecision | None = None) -> dict:
    action = str(analysis.get("action", "HOLD")).upper()
    probabilities = analysis.get("probabilities", {}) or {}
    position = get_paper_position(db)
    uptime = int(time.monotonic() - APP_START_MONOTONIC)
    remaining = max(0, PAPER_START_DELAY_SECONDS - uptime)

    if not BACKEND_STABLE:
        return {"executed": False, "reason": "Backend nicht stabil: kein Paper-Trade erlaubt.", "backend_stable": False}

    if risk_shield.settings.emergency_stop:
        return {"executed": False, "reason": "Not-Aus aktiv. Marktanalyse laeuft weiter, Paper-Trading pausiert."}

    buy_pct = float(probabilities.get("BUY", 0) or 0)
    sell_pct = float(probabilities.get("SELL", 0) or 0)
    hold_pct = float(probabilities.get("HOLD", 0) or 0)

    if remaining > 0:
        return {
            "executed": False,
            "reason": f"Startschutz aktiv: Paper-Trading wird in {remaining} Sekunden freigegeben.",
            "start_protection": True,
            "remaining_seconds": remaining,
            "position": position,
            "probabilities": probabilities,
        }

    if not position["has_open_position"] and position["available_eur"] >= 1 and action == "BUY" and buy_pct >= 45:
        amount = min(2.50, position["available_eur"])
        result = trading_engine.paper_trade(
            db,
            side="BUY",
            amount_eur=amount,
            reason=f"Startschutz beendet · CPU-Safe Paper BUY: BUY {buy_pct:.1f}% SELL {sell_pct:.1f}% HOLD {hold_pct:.1f}% · {analysis.get('reason','')}",
            force_manual=True
        )
        if result.get("executed") and decision is not None:
            decision.trade_created = True
            db.commit()
        return result

    return {
        "executed": False,
        "reason": f"Kein Paper-Trade: offene Position={position['has_open_position']}, EUR={position['available_eur']}, BUY={buy_pct:.1f}%, SELL={sell_pct:.1f}%, HOLD={hold_pct:.1f}%.",
        "start_protection": False,
        "position": position,
        "rules_checked": True,
        "probabilities": probabilities,
    }


load_risk_settings()

app = FastAPI(title=settings.app_name, version=current_version())
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
def log_startup_event():
    db = SessionLocal()
    try:
        db.add(SystemEvent(level="info", message="Webshake Trading v0.1.3-beta gestartet."))
        db.commit()
    finally:
        db.close()

@app.post("/api/system/shutdown-log")
def system_shutdown_log(reason: str = "normal", db: Session = Depends(get_db)):
    db.add(SystemEvent(level="info", message=f"Webshake Trading beendet. Art: {reason}"))
    db.commit()
    return {"logged": True, "reason": reason}

@app.get("/api/status")
def status():
    return {
        "server_time": datetime.now().isoformat(timespec="seconds"),
        "app": settings.app_name,
        "version": current_version(),
        "version_info": load_version_info(),
        "paper_trading": settings.paper_trading,
        "paper_start_protection": {"delay_seconds": PAPER_START_DELAY_SECONDS, "remaining_seconds": max(0, PAPER_START_DELAY_SECONDS - int(time.monotonic() - APP_START_MONOTONIC))},
        "risk": risk_shield.settings.model_dump(),
    }

@app.get("/api/version")
def api_version():
    return load_version_info()

@app.get("/api/changelog")
def api_changelog():
    info = load_version_info()
    return {
        "version": info.get("version", current_version()),
        "client_version": info.get("client_version", "v0.1.3-beta"),
        "show_once_key": "webshake_changelog_v0_1_0_beta_seen",
        "notes": info.get("notes", [
            "Versionsanzeige final dynamisch ueber Backend/API korrigiert",
            "Changelog nach Update wieder sichtbar und versionsgebunden",
            "Paper-Trading sichtbar/aktiv: BUY- und SELL-Regeln, Status, Gruende",
            "KI-Paper-Trading fuehrt simulierte BUY/SELL Trades aus, wenn Regeln erfuellt sind",
            "Keine echten Coinbase-Orders"
        ]),
    }

@app.get("/api/health")
def health():
    return {"ok": True, "version": current_version(), "version_info": load_version_info()}

@app.get("/api/account/balance")
def account_balance(db: Session = Depends(get_db)):
    return calculate_paper_balance(db)

@app.get("/api/paper/status")
def paper_status(db: Session = Depends(get_db)):
    position = get_paper_position(db)
    latest_trades = db.query(Trade).filter(Trade.mode == "paper").order_by(Trade.id.desc()).limit(10).all()
    return {
        "enabled": True,
        "mode": "paper",
        "symbol": "BTC-EUR",
        "start_capital_eur": 50.0,
        "max_open_trades": 1,
        "no_real_orders": True,
        "position": position,
        "buy_rules": [
            "KI-Entscheidung = BUY",
            "Vertrauen >= 68 %",
            "Trend nicht DOWN",
            "Momentum positiv",
            "RSI nicht ueberkauft",
            "kein offener Paper-Trade",
            "Not-Aus nicht aktiv",
            "Paper-Guthaben vorhanden"
        ],
        "sell_rules": [
            "KI-Entscheidung = SELL",
            "Vertrauen >= 62 %",
            "offener Paper-Trade vorhanden",
            "Trend kippt nach unten",
            "Momentum wird negativ",
            "Gewinnziel oder Verlustlimit erreicht",
            "Risiko steigt zu stark"
        ],
        "latest_trades": [
            {
                "id": t.id,
                "created_at": t.created_at.isoformat(),
                "side": t.side,
                "amount_eur": t.amount_eur,
                "btc_amount": t.btc_amount,
                "price_eur": t.price_eur,
                "reason": t.reason,
            } for t in latest_trades
        ],
    }


@app.get("/api/paper/start-protection")
def paper_start_protection():
    remaining = max(0, PAPER_START_DELAY_SECONDS - int(time.monotonic() - APP_START_MONOTONIC))
    return {
        "active": remaining > 0,
        "remaining_seconds": remaining,
        "delay_seconds": PAPER_START_DELAY_SECONDS,
        "status": "aktiv" if remaining > 0 else "freigegeben",
    }


@app.post("/api/system/restart-protection")
def restart_protection_timer():
    reset_start_protection_timer()
    return paper_start_protection()


@app.post("/api/database/delete")
def database_delete(payload: dict, db: Session = Depends(get_db)):
    table = str(payload.get("table", "")).lower()
    row_id = payload.get("id")
    delete_all = bool(payload.get("all", False))

    allowed = {
        "trades": Trade,
        "trade": Trade,
        "ai_decisions": AIDecision,
        "ki": AIDecision,
        "logs": SystemEvent,
        "log": SystemEvent,
    }
    if table not in allowed:
        return {"ok": False, "error": "Tabelle nicht erlaubt. Erlaubt: trades, ai_decisions, logs"}

    model = allowed[table]

    try:
        if delete_all:
            count = db.query(model).delete(synchronize_session=False)
            db.add(SystemEvent(level="warning", message=f"Datenbank: {count} Eintraege aus {table} geloescht", requires_attention=False))
            db.commit()
            return {"ok": True, "deleted": int(count or 0), "table": table}

        if row_id is None or str(row_id).strip() == "":
            return {"ok": False, "error": "Keine ID angegeben."}

        obj = db.query(model).filter(model.id == int(row_id)).first()
        if not obj:
            return {"ok": False, "error": "Eintrag nicht gefunden."}

        db.delete(obj)
        db.add(SystemEvent(level="warning", message=f"Datenbank: Eintrag {row_id} aus {table} geloescht", requires_attention=False))
        db.commit()
        return {"ok": True, "deleted": 1, "table": table, "id": int(row_id)}
    except Exception as exc:
        db.rollback()
        return {"ok": False, "error": str(exc)}


@app.get("/api/storage/limits")
def storage_limits_get(db: Session = Depends(get_db)):
    return get_storage_limits(db)


@app.post("/api/storage/limits")
def storage_limits_set(payload: dict, db: Session = Depends(get_db)):
    limits = {
        "ai_decisions": int(payload.get("ai_decisions", 20000)),
        "logs": int(payload.get("logs", 5000)),
        "trades": int(payload.get("trades", 50000)),
    }
    save_setting(db, "storage_limits", limits)
    db.commit()
    trimmed = apply_storage_limits(db)
    return {"ok": True, "limits": limits, "trimmed": trimmed}


@app.post("/api/paper/reset")
def paper_reset(db: Session = Depends(get_db)):
    try:
        trades_deleted = db.query(Trade).delete(synchronize_session=False)
        decisions_deleted = db.query(AIDecision).delete(synchronize_session=False)
        db.query(Setting).filter(Setting.key.in_(["paper_eur", "paper_btc", "paper_start_eur"])).delete(synchronize_session=False)
        db.add(Setting(key="paper_start_eur", value="50"))
        db.add(Setting(key="paper_eur", value="50"))
        db.add(Setting(key="paper_btc", value="0"))
        db.add(SystemEvent(level="warning", message="Paper-Trading Reset ausgefuehrt: 50 EUR Startkapital", requires_attention=False))
        db.commit()
        return {"ok": True, "trades_deleted": int(trades_deleted or 0), "decisions_deleted": int(decisions_deleted or 0), "start_balance_eur": 50}
    except Exception as exc:
        db.rollback()
        return {"ok": False, "error": str(exc)}



@app.get("/api/paper/start-protection")
def paper_start_protection():
    remaining = max(0, PAPER_START_DELAY_SECONDS - int(time.monotonic() - APP_START_MONOTONIC))
    return {
        "active": remaining > 0 or not BACKEND_STABLE,
        "remaining_seconds": remaining,
        "delay_seconds": PAPER_START_DELAY_SECONDS,
        "backend_stable": BACKEND_STABLE,
        "status": "backend-fehler" if not BACKEND_STABLE else ("aktiv" if remaining > 0 else "freigegeben"),
    }


@app.get("/api/system/health")
def system_health(db: Session = Depends(get_db)):
    return enforce_backend_safety(db)


@app.post("/api/system/restart-protection")
def restart_protection_timer():
    reset_start_protection_timer()
    return paper_start_protection()


@app.get("/api/market/btc")
def btc_price():
    return market_data.get_btc_eur_price()

@app.get("/api/market/24h")
def btc_24h_stats():
    return market_data.get_24h_stats()

@app.get("/api/market/timeframes")
def market_timeframes(force: bool = False):
    return market_data.get_timeframes(force=force)

@app.get("/api/ai/analyze")
def analyze(persist: bool = True, db: Session = Depends(get_db)):
    analysis = strategy_engine.analyze()
    decision = None
    if persist:
        decision = store_ai_decision(db, analysis)
        analysis["decision_id"] = decision.id
        paper_result = maybe_execute_ai_paper_trade(db, analysis, decision)
        analysis["paper_trading"] = paper_result
    return analysis



# Kompatibilitaetsrouten fuer aeltere Frontend-/Browser-Aufrufe.
# In v0.9.x ist die Hauptanalyse unter /api/ai/analyze.
# /api/analyze bleibt ab v0.9.4 wieder erreichbar, damit keine "Not Found"-Meldung entsteht.
@app.get("/api/analyze")
def analyze_legacy(persist: bool = True, db: Session = Depends(get_db)):
    return analyze(persist=persist, db=db)

@app.get("/api/ai/latest")
def ai_latest(db: Session = Depends(get_db)):
    latest = db.query(AIDecision).order_by(AIDecision.id.desc()).first()
    if latest:
        return {
            "id": latest.id,
            "created_at": latest.created_at.isoformat(),
            "mode": latest.mode,
            "symbol": latest.symbol,
            "action": latest.action,
            "confidence": latest.confidence,
            "price_eur": latest.price_eur,
            "trend": latest.trend,
            "volatility_pct": latest.volatility_pct,
            "signal_strength": latest.signal_strength,
            "strategy": latest.strategy,
            "reason": latest.reason,
            "trade_created": latest.trade_created,
            "outcome": latest.outcome,
        }
    analysis = strategy_engine.analyze()
    decision = store_ai_decision(db, analysis)
    analysis["decision_id"] = decision.id
    return analysis

@app.get("/api/market/indicators")
def indicators():
    return market_data.indicators()

@app.post("/api/trading/paper/{side}")
def paper_trade(side: str, amount_eur: float = 1.0, db: Session = Depends(get_db)):
    analysis = strategy_engine.analyze()
    decision = store_ai_decision(db, analysis)
    result = trading_engine.paper_trade(db, side=side, amount_eur=amount_eur, reason=analysis["reason"], force_manual=True)
    if result.get("executed"):
        decision.trade_created = True
        db.commit()
    result["decision_id"] = decision.id
    return result

@app.post("/api/risk/settings")
def update_risk(settings_in: RiskSettings, db: Session = Depends(get_db)):
    risk_shield.settings = settings_in
    save_setting(db, "risk_settings", risk_shield.settings.model_dump())
    db.add(SystemEvent(level="info", message="Risk-Shield-Einstellungen gespeichert."))
    db.commit()
    return {"saved": True, "risk": risk_shield.settings.model_dump()}

@app.post("/api/risk/emergency-stop")
def emergency_stop(db: Session = Depends(get_db)):
    already_active = bool(risk_shield.settings.emergency_stop)
    risk_shield.settings.emergency_stop = True
    save_setting(db, "risk_settings", risk_shield.settings.model_dump())
    if not already_active:
        db.add(SystemEvent(level="critical", message="Not-Aus aktiviert. Trading gestoppt. Marktanalyse laeuft weiter.", requires_attention=True))
    db.commit()
    return {"emergency_stop": True, "already_active": already_active, "market_analysis_active": True}

@app.post("/api/risk/resume")
def resume(db: Session = Depends(get_db)):
    risk_shield.settings.emergency_stop = False
    save_setting(db, "risk_settings", risk_shield.settings.model_dump())
    db.add(SystemEvent(level="info", message="System manuell fortgesetzt."))
    db.commit()
    return {"emergency_stop": False}


def _activity_line(message: str, level: str = "info") -> dict:
    return {"time": datetime.now().strftime("%d.%m.%Y %H:%M:%S"), "level": level, "message": message}

@app.get("/api/ai/live-monitor")
def ai_live_monitor():
    analysis = strategy_engine.analyze()
    indicators = analysis.get("indicators", {}) or {}
    tick = analysis.get("tick", {}) or {}
    lines = [
        _activity_line("Marktbeobachtung aktiv"),
        _activity_line(f"Datenquelle abgefragt: {tick.get('source', 'unbekannt')}", "data"),
        _activity_line(f"BTC/EUR Kurs empfangen: {tick.get('price_eur', 0)} EUR", "data"),
        _activity_line("Trendanalyse ausgefuehrt"),
        _activity_line(f"Trend: {indicators.get('trend', 'UNKNOWN')}"),
        _activity_line(f"Volatilitaet berechnet: {indicators.get('volatility_20_samples_pct', 0)} %"),
        _activity_line(f"KI-Entscheidung: {analysis.get('action', 'HOLD')} · {round(float(analysis.get('confidence', 0) or 0)*100)} %", "decision"),
    ]
    if not BACKEND_STABLE:
        return {"executed": False, "reason": "Backend nicht stabil: kein Paper-Trade erlaubt.", "backend_stable": False}

    if risk_shield.settings.emergency_stop:
        lines.append(_activity_line("Not-Aus aktiv: Trade-Ausfuehrung gestoppt, Marktanalyse laeuft weiter", "warning"))
    else:
        lines.append(_activity_line("Trading-Ausfuehrung im Paper-Modus bereit", "info"))
    return {
        "server_time": datetime.now().isoformat(timespec="seconds"),
        "market_analysis_active": True,
        "trade_execution_allowed": not risk_shield.settings.emergency_stop,
        "items": lines,
    }

@app.get("/api/trades")
def trades(db: Session = Depends(get_db), limit: int = 50):
    rows = db.query(Trade).order_by(Trade.id.desc()).limit(min(limit, 500)).all()
    return [{"id": r.id, "created_at": r.created_at.isoformat(), "mode": r.mode, "symbol": r.symbol, "side": r.side, "amount_eur": r.amount_eur, "btc_amount": r.btc_amount, "price_eur": r.price_eur, "reason": r.reason} for r in rows]


@app.get("/api/trades/overview")
def trades_overview(db: Session = Depends(get_db), limit: int = 50):
    tick = market_data.get_btc_eur_price()
    current_price = float(tick.get("price_eur", 0) or 0)
    rows = db.query(Trade).order_by(Trade.id.desc()).limit(min(limit, 500)).all()
    result = []
    for r in rows:
        side = (r.side or "").upper()
        entry_price = float(r.price_eur or 0)
        amount_eur = float(r.amount_eur or 0)
        btc_amount = float(r.btc_amount or 0)
        if side == "BUY":
            current_value = btc_amount * current_price
            pnl_eur = current_value - amount_eur
        elif side == "SELL":
            # Paper-Sell wird hier als Gegenrichtung betrachtet: Gewinn, wenn BTC nach Sell fällt.
            pnl_eur = amount_eur - (btc_amount * current_price)
            current_value = amount_eur + pnl_eur
        else:
            current_value = amount_eur
            pnl_eur = 0.0
        pnl_pct = (pnl_eur / amount_eur * 100) if amount_eur else 0.0
        result.append({
            "id": r.id,
            "created_at": r.created_at.isoformat(),
            "mode": r.mode,
            "symbol": r.symbol,
            "side": r.side,
            "status": "open",
            "entry_price_eur": round(entry_price, 2),
            "current_price_eur": round(current_price, 2),
            "amount_eur": round(amount_eur, 2),
            "btc_amount": round(btc_amount, 8),
            "pnl_eur": round(pnl_eur, 2),
            "pnl_pct": round(pnl_pct, 2),
            "reason": r.reason,
        })
    return result

@app.get("/api/ai/decisions")
def ai_decisions(db: Session = Depends(get_db), limit: int = 100):
    rows = db.query(AIDecision).order_by(AIDecision.id.desc()).limit(min(limit, 1000)).all()
    return [{
        "id": r.id,
        "created_at": r.created_at.isoformat(),
        "mode": r.mode,
        "symbol": r.symbol,
        "action": r.action,
        "confidence": r.confidence,
        "price_eur": r.price_eur,
        "trend": r.trend,
        "volatility_pct": r.volatility_pct,
        "signal_strength": r.signal_strength,
        "strategy": r.strategy,
        "reason": r.reason,
        "trade_created": r.trade_created,
        "outcome": r.outcome,
    } for r in rows]

@app.get("/api/db/overview")
def db_overview(db: Session = Depends(get_db)):
    return {
        "trades": db.query(Trade).count(),
        "ai_decisions": db.query(AIDecision).count(),
        "logs": db.query(SystemEvent).count(),
        "settings": db.query(Setting).count(),
    }

@app.get("/api/settings")
def get_settings_rows(db: Session = Depends(get_db)):
    rows = db.query(Setting).order_by(Setting.key.asc()).all()
    parsed = []
    for r in rows:
        try:
            value = json.loads(r.value)
        except Exception:
            value = r.value
        parsed.append({"id": r.id, "key": r.key, "value": value})
    parsed.append({"id": "runtime_app", "key": "app_version", "value": current_version()})
    parsed.append({"id": "runtime_paper", "key": "paper_trading", "value": settings.paper_trading})
    return parsed

@app.post("/api/settings/{key}")
def set_setting_row(key: str, value: dict, db: Session = Depends(get_db)):
    save_setting(db, key, value)
    db.add(SystemEvent(level="info", message=f"Einstellung gespeichert: {key}"))
    db.commit()
    return {"saved": True, "key": key, "value": value}

@app.get("/api/logs")
def logs(
    db: Session = Depends(get_db),
    limit: int = 100,
    level: str | None = None,
    category: str | None = None,
    q: str | None = None,
):
    query = db.query(SystemEvent)
    if level:
        query = query.filter(SystemEvent.level.ilike(f"%{level}%"))
    if q:
        query = query.filter(SystemEvent.message.ilike(f"%{q}%"))
    if category:
        query = query.filter(SystemEvent.message.ilike(f"%{category}%"))
    rows = query.order_by(SystemEvent.id.desc()).limit(min(limit, 1000)).all()
    return [{"id": r.id, "created_at": r.created_at.isoformat(), "level": r.level, "message": r.message, "requires_attention": r.requires_attention} for r in rows]

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8765, reload=True)
