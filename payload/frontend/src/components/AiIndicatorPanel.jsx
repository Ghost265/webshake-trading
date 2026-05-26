import React from 'react';

function Badge({ label, value }) {
  return (
    <div className="ws-card ws-small-card">
      <div className="ws-muted">{label}</div>
      <div className="ws-value">{value ?? '—'}</div>
    </div>
  );
}

export default function AiIndicatorPanel({ analysis }) {
  if (!analysis) return <div className="ws-card">KI Analyse 2.0 wartet auf Daten …</div>;
  return (
    <div className="ws-card">
      <h3>KI Analyse 2.0</h3>
      <div className="ws-grid">
        <Badge label="RSI" value={analysis.rsi} />
        <Badge label="RSI Status" value={analysis.rsi_status} />
        <Badge label="EMA 9" value={analysis.ema_9} />
        <Badge label="EMA 21" value={analysis.ema_21} />
        <Badge label="SMA 20" value={analysis.sma_20} />
        <Badge label="Momentum" value={analysis.momentum_10} />
        <Badge label="Trendstärke" value={analysis.trend_strength} />
        <Badge label="Signalqualität" value={analysis.signal_quality} />
      </div>
      <p className="ws-explanation">{analysis.explanation}</p>
    </div>
  );
}
