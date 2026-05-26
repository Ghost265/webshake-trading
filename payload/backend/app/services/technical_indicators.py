from __future__ import annotations
from typing import Iterable, List, Optional

def _clean(values: Iterable[float]) -> List[float]:
    out = []
    for value in values:
        try:
            out.append(float(value))
        except (TypeError, ValueError):
            continue
    return out

def sma(values: Iterable[float], period: int = 14) -> Optional[float]:
    data = _clean(values)
    if period <= 0 or len(data) < period:
        return None
    return sum(data[-period:]) / period

def ema(values: Iterable[float], period: int = 14) -> Optional[float]:
    data = _clean(values)
    if period <= 0 or len(data) < period:
        return None
    multiplier = 2 / (period + 1)
    current = sum(data[:period]) / period
    for price in data[period:]:
        current = (price - current) * multiplier + current
    return current

def rsi(values: Iterable[float], period: int = 14) -> Optional[float]:
    data = _clean(values)
    if len(data) <= period:
        return None
    gains = []
    losses = []
    for i in range(1, period + 1):
        diff = data[i] - data[i - 1]
        gains.append(max(diff, 0))
        losses.append(abs(min(diff, 0)))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    for i in range(period + 1, len(data)):
        diff = data[i] - data[i - 1]
        avg_gain = ((avg_gain * (period - 1)) + max(diff, 0)) / period
        avg_loss = ((avg_loss * (period - 1)) + abs(min(diff, 0))) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)

def momentum(values: Iterable[float], period: int = 10) -> Optional[float]:
    data = _clean(values)
    if len(data) <= period:
        return None
    return round(data[-1] - data[-period - 1], 2)

def trend_strength(values: Iterable[float], short_period: int = 9, long_period: int = 21) -> Optional[float]:
    data = _clean(values)
    short = ema(data, short_period)
    long = ema(data, long_period)
    if short is None or long is None or long == 0:
        return None
    return round(((short - long) / long) * 100, 4)
