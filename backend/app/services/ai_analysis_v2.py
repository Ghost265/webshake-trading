from statistics import mean

def sma(values, period):
    if len(values) < period:
        return None
    return mean(values[-period:])

def ema(values, period):
    if len(values) < period:
        return None
    k = 2 / (period + 1)
    e = values[0]
    for v in values[1:]:
        e = v * k + e * (1-k)
    return e

def rsi(values, period=14):
    if len(values) <= period:
        return 50
    gains=[]; losses=[]
    for a,b in zip(values[-period-1:-1], values[-period:]):
        d=b-a
        gains.append(max(d,0)); losses.append(abs(min(d,0)))
    avg_gain=mean(gains) if gains else 0
    avg_loss=mean(losses) if losses else 0
    if avg_loss == 0:
        return 100
    rs=avg_gain/avg_loss
    return 100-(100/(1+rs))

def analyze_market(prices, volumes=None):
    if not prices:
        return {"action":"HOLD","confidence":0.0,"trend":"UNKNOWN","reason":"Keine Daten"}
    short=sma(prices,5) or prices[-1]
    long=sma(prices,20) or prices[-1]
    mom=(prices[-1]-prices[-5])/prices[-5] if len(prices)>=5 and prices[-5] else 0
    r=rsi(prices)
    volume_score=0
    if volumes and len(volumes)>=10:
        volume_score=(mean(volumes[-3:])/(mean(volumes[-10:]) or 1))-1
    score=0
    score += 1 if short>long else -1 if short<long else 0
    score += 1 if mom>0.001 else -1 if mom<-0.001 else 0
    score += 1 if r<35 else -1 if r>70 else 0
    score += 1 if volume_score>0.1 and mom>0 else -1 if volume_score>0.1 and mom<0 else 0
    if score>=2:
        action='BUY'; trend='UP'
    elif score<=-2:
        action='SELL'; trend='DOWN'
    else:
        action='HOLD'; trend='FLAT'
    confidence=min(0.95, 0.50 + abs(score)*0.10)
    return {"action":action,"confidence":round(confidence,2),"trend":trend,"rsi":round(r,2),"momentum":round(mom,5),"volume_score":round(volume_score,4),"reason":"Kombinationssignal aus RSI, SMA/EMA, Momentum, Volumen und Marktphase"}
