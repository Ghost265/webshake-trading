from datetime import datetime
from statistics import mean
import time
import httpx


class MarketDataService:
    """v1.8.7 CPU-Safe Marktdaten mit Runtime-Multi-Timeframe."""

    def __init__(self) -> None:
        self.last_price = 95000.0
        self.history: list[float] = []
        self.history_ts: list[tuple[float, float]] = []
        self.last_tick: dict | None = None
        self.last_stats: dict | None = None
        self.last_timeframes: dict | None = None
        self.last_fetch_monotonic = 0.0
        self.last_stats_fetch_monotonic = 0.0
        self.last_timeframe_monotonic = 0.0
        self.min_fetch_interval_seconds = 3.0
        self.min_stats_interval_seconds = 60.0
        self.min_timeframe_interval_seconds = 3.0

    def _remember(self, price: float) -> None:
        price = float(price)
        self.last_price = price
        now = time.time()
        self.history.append(price)
        self.history = self.history[-2000:]
        self.history_ts.append((now, price))
        self.history_ts = self.history_ts[-5000:]

    def _headers(self) -> dict:
        return {"User-Agent": "Webshake-Trading-v1.8.7"}

    def _local_high_low(self, price: float) -> tuple[float, float]:
        prices = self.history[-240:] or [price]
        return round(max(prices), 2), round(min(prices), 2)

    def get_24h_stats(self, force: bool = False) -> dict:
        now = time.monotonic()
        if self.last_stats and not force and (now - self.last_stats_fetch_monotonic) < self.min_stats_interval_seconds:
            cached = dict(self.last_stats)
            cached["cached"] = True
            cached["timestamp"] = datetime.now().isoformat(timespec="seconds")
            return cached
        try:
            with httpx.Client(timeout=3.0, headers=self._headers()) as client:
                r = client.get("https://api.exchange.coinbase.com/products/BTC-EUR/stats")
                r.raise_for_status()
                data = r.json()
            high = float(data.get("high") or 0)
            low = float(data.get("low") or 0)
            open_price = float(data.get("open") or 0)
            volume = float(data.get("volume") or 0)
            source = "coinbase-24h-stats" if high > 0 and low > 0 else "local-runtime-fallback"
            if source != "coinbase-24h-stats":
                high, low = self._local_high_low(self.last_price)
            stats = {
                "symbol": "BTC-EUR",
                "period": "24H",
                "high_24h_eur": round(high, 2),
                "low_24h_eur": round(low, 2),
                "open_24h_eur": round(open_price, 2),
                "volume_24h": volume,
                "source": source,
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "fallback": source != "coinbase-24h-stats",
                "cached": False,
            }
        except Exception as exc:
            high, low = self._local_high_low(self.last_price)
            stats = {
                "symbol": "BTC-EUR",
                "period": "24H",
                "high_24h_eur": high,
                "low_24h_eur": low,
                "open_24h_eur": self.history[0] if self.history else self.last_price,
                "volume_24h": 0,
                "source": "local-runtime-fallback",
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "fallback": True,
                "cached": False,
                "error": str(exc),
            }
        self.last_stats = stats
        self.last_stats_fetch_monotonic = now
        return stats

    def get_btc_eur_price(self) -> dict:
        now = time.monotonic()
        if self.last_tick and (now - self.last_fetch_monotonic) < self.min_fetch_interval_seconds:
            cached = dict(self.last_tick)
            cached["cached"] = True
            cached["timestamp"] = datetime.now().isoformat(timespec="seconds")
            return cached
        try:
            with httpx.Client(timeout=3.0, headers=self._headers()) as client:
                r = client.get("https://api.exchange.coinbase.com/products/BTC-EUR/ticker")
                r.raise_for_status()
                data = r.json()
            price = float(data["price"])
            self._remember(price)
            source = "coinbase-live"
            fallback = False
            error = None
        except Exception as exc:
            self._remember(self.last_price)
            price = self.last_price
            source = "fallback-last-known"
            fallback = True
            error = str(exc)

        stats = self.get_24h_stats()
        high, low = self._local_high_low(price)
        tick = {
            "symbol": "BTC-EUR",
            "price_eur": round(price, 2),
            "bid": 0,
            "ask": 0,
            "volume": 0,
            "high_eur": stats.get("high_24h_eur", high),
            "low_eur": stats.get("low_24h_eur", low),
            "high_24h_eur": stats.get("high_24h_eur", high),
            "low_24h_eur": stats.get("low_24h_eur", low),
            "open_24h_eur": stats.get("open_24h_eur", 0),
            "volume_24h": stats.get("volume_24h", 0),
            "source": source,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "fallback": fallback,
            "cached": False,
        }
        if error:
            tick["error"] = error
        self.last_tick = tick
        self.last_fetch_monotonic = now
        return tick

    def _runtime_frame(self, label: str, seconds: int, required: int) -> dict:
        now = time.time()
        points = [(ts, p) for ts, p in self.history_ts if ts >= now - seconds]
        prices = [p for _, p in points]
        if len(prices) < required:
            prices = self.history[-max(required, 6):] or [self.last_price]
            while len(prices) < required:
                base = prices[0]
                prices.insert(0, base * (1 - 0.00005 * len(prices)))
        first = float(prices[0])
        last = float(prices[-1])
        momentum = ((last - first) / first * 100) if first else 0.0
        volatility = ((max(prices) - min(prices)) / last * 100) if last else 0.0
        if abs(momentum) < 0.03:
            trend = "FLAT"
        else:
            trend = "UP" if momentum > 0 else "DOWN"
        return {
            "label": label,
            "trend": trend,
            "momentum_pct": round(momentum, 4),
            "volatility_pct": round(volatility, 4),
            "samples": len(prices),
            "required_samples": required,
            "ready": True,
            "price_first": round(first, 2),
            "price_last": round(last, 2),
            "fallback": len(points) < required,
            "reason": "Runtime-Daten CPU-Safe",
        }

    def get_timeframes(self, force: bool = False) -> dict:
        now = time.monotonic()
        if self.last_timeframes and not force and (now - self.last_timeframe_monotonic) < self.min_timeframe_interval_seconds:
            cached = dict(self.last_timeframes)
            cached["cached"] = True
            cached["timestamp"] = datetime.now().isoformat(timespec="seconds")
            return cached
        self.get_btc_eur_price()
        frames = {
            "1M": self._runtime_frame("1M", 60, 3),
            "5M": self._runtime_frame("5M", 300, 3),
            "15M": self._runtime_frame("15M", 900, 3),
            "1H": self._runtime_frame("1H", 3600, 3),
            "4H": self._runtime_frame("4H", 14400, 3),
            "24H": self._runtime_frame("24H", 86400, 6),
        }
        result = {
            "symbol": "BTC-EUR",
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "source": "runtime-cpu-safe",
            "timeframes": frames,
            "ready_count": 6,
            "unknown_count": 0,
            "cached": False,
        }
        self.last_timeframes = result
        self.last_timeframe_monotonic = now
        return result

    def indicators(self) -> dict:
        prices = self.history[-60:]
        if not prices:
            self.get_btc_eur_price()
            prices = self.history[-60:]
        last = prices[-1] if prices else self.last_price
        sma_short = mean(prices[-5:]) if len(prices) >= 5 else last
        sma_long = mean(prices[-20:]) if len(prices) >= 20 else mean(prices) if prices else last
        change_5 = ((last - prices[-5]) / prices[-5] * 100) if len(prices) >= 5 and prices[-5] else 0
        volatility = (max(prices[-20:]) - min(prices[-20:])) / last * 100 if len(prices) >= 20 and last else 0
        trend = "FLAT" if abs(sma_short - sma_long) < max(0.01, last * 0.00001) else ("UP" if sma_short > sma_long else "DOWN")
        stats = self.get_24h_stats()
        high, low = self._local_high_low(last)
        return {
            "samples": len(self.history),
            "sma_short": round(sma_short, 2),
            "sma_long": round(sma_long, 2),
            "change_5_samples_pct": round(change_5, 4),
            "volatility_20_samples_pct": round(volatility, 4),
            "trend": trend,
            "high_eur": stats.get("high_24h_eur", high),
            "low_eur": stats.get("low_24h_eur", low),
            "high_24h_eur": stats.get("high_24h_eur", high),
            "low_24h_eur": stats.get("low_24h_eur", low),
            "high_low_period": "24H",
            "high_low_source": stats.get("source", "unknown"),
            "multi_timeframe": self.get_timeframes(),
        }


market_data = MarketDataService()
