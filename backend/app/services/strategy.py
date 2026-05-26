from app.services.market_data import market_data


class StrategyEngine:
    """v0.1.3-beta CPU-Safe Strategie mit Startschutz."""

    def analyze(self) -> dict:
        tick = market_data.get_btc_eur_price()
        indicators = market_data.indicators()
        timeframes = market_data.get_timeframes()

        frames = timeframes.get("timeframes", {})
        buy = 0.0
        sell = 0.0
        hold = 0.0
        weights = {"1M": 18, "5M": 22, "15M": 20, "1H": 16, "4H": 14, "24H": 10}
        details = []

        for label, weight in weights.items():
            frame = frames.get(label, {})
            trend = str(frame.get("trend", "FLAT")).upper()
            momentum = float(frame.get("momentum_pct", 0) or 0)
            if trend == "UP":
                buy += weight
            elif trend == "DOWN":
                sell += weight
            else:
                hold += weight * 0.60
                if momentum >= 0:
                    buy += weight * 0.40
                else:
                    sell += weight * 0.40
            details.append(f"{label}: {trend} ({momentum:.2f} %)")

        live_change = float(indicators.get("change_5_samples_pct", 0) or 0)
        if live_change >= 0:
            buy += 10
        else:
            sell += 10


        # 24H High-/Low-Logik:
        # Kurs nahe Tagestief = eher BUY/Rebound-Potenzial.
        # Kurs nahe Tageshoch = eher SELL/Gewinnmitnahme-Risiko.
        tick_price = float(tick.get("price_eur", 0) or 0)
        high = float(tick.get("high_24h_eur", tick.get("high_eur", 0)) or 0)
        low = float(tick.get("low_24h_eur", tick.get("low_eur", 0)) or 0)
        high_low_position = 0.5
        if high > low and tick_price > 0:
            high_low_position = max(0.0, min(1.0, (tick_price - low) / (high - low)))
            if high_low_position <= 0.35:
                buy += 18
                sell -= min(sell, 8)
                details.append(f"24H Position: nahe Tief ({high_low_position*100:.1f} %) -> BUY-Bonus")
            elif high_low_position >= 0.70:
                sell += 14
                buy -= min(buy, 6)
                details.append(f"24H Position: nahe Hoch ({high_low_position*100:.1f} %) -> SELL-Bonus")


        total = buy + sell + hold
        if total <= 0:
            buy_pct, sell_pct, hold_pct = 34.0, 33.0, 33.0
        else:
            buy_pct = round(buy / total * 100, 1)
            sell_pct = round(sell / total * 100, 1)
            hold_pct = round(max(0, 100 - buy_pct - sell_pct), 1)

        if buy_pct >= sell_pct:
            action = "BUY"
            confidence = max(0.50, min(0.86, buy_pct / 100))
            reason = "CPU-Safe Paper-Modus: BUY-Signal bevorzugt."
        else:
            action = "SELL"
            confidence = max(0.50, min(0.86, sell_pct / 100))
            reason = "CPU-Safe Paper-Modus: SELL-Signal bevorzugt."

        return {
            "tick": tick,
            "indicators": indicators,
            "timeframes": timeframes,
            "probabilities": {"BUY": buy_pct, "SELL": sell_pct, "HOLD": hold_pct},
            "action": action,
            "confidence": round(confidence, 2),
            "reason": reason,
            "decision_details": details,
            "strategy": "cpu-safe-start-protection-v0.1.3-beta",
        }


strategy_engine = StrategyEngine()
