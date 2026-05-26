from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base

class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)

class Trade(Base):
    __tablename__ = "trades"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    mode: Mapped[str] = mapped_column(String(20), default="paper")
    symbol: Mapped[str] = mapped_column(String(20), default="BTC-EUR")
    side: Mapped[str] = mapped_column(String(10))
    amount_eur: Mapped[float] = mapped_column(Float)
    btc_amount: Mapped[float] = mapped_column(Float)
    price_eur: Mapped[float] = mapped_column(Float)
    reason: Mapped[str] = mapped_column(Text, default="")

class AIDecision(Base):
    __tablename__ = "ai_decisions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    mode: Mapped[str] = mapped_column(String(20), default="paper")
    symbol: Mapped[str] = mapped_column(String(20), default="BTC-EUR")
    action: Mapped[str] = mapped_column(String(10), default="HOLD")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    price_eur: Mapped[float] = mapped_column(Float, default=0.0)
    trend: Mapped[str] = mapped_column(String(20), default="FLAT")
    volatility_pct: Mapped[float] = mapped_column(Float, default=0.0)
    signal_strength: Mapped[float] = mapped_column(Float, default=0.0)
    strategy: Mapped[str] = mapped_column(String(80), default="trend-v0.5")
    reason: Mapped[str] = mapped_column(Text, default="")
    raw_json: Mapped[str] = mapped_column(Text, default="{}")
    trade_created: Mapped[bool] = mapped_column(Boolean, default=False)
    outcome: Mapped[str] = mapped_column(String(20), default="open")

class SystemEvent(Base):
    __tablename__ = "system_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    level: Mapped[str] = mapped_column(String(20), default="info")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    requires_attention: Mapped[bool] = mapped_column(Boolean, default=False)
