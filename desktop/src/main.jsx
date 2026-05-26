import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { ShieldAlert, Bot, LineChart, Settings, Activity, Database, Power, RefreshCw, Save, Smartphone, Wallet, DoorOpen, TrendingUp, TrendingDown, Radio, Clock, X } from 'lucide-react';
import './style.css';

const API = 'http://127.0.0.1:8765/api';
const BACKEND_ERROR = 'Backend antwortet aktuell nicht stabil. Die App versucht automatisch, die Verbindung wiederherzustellen.';
const menu = ['Dashboard','Live Trading','KI Analyse','KI Live-Monitor','Strategien','Risiko','Datenbank','Logs','Einstellungen'];
function euro(v){ return Number(v || 0).toLocaleString('de-DE',{minimumFractionDigits:2,maximumFractionDigits:2}) + ' €'; }
function pct(v){ return `${Number(v || 0).toFixed(2)}%`; }
function ts(v){ try{return new Date(v).toLocaleString('de-DE')}catch{return v} }
function trendInfo(t){
  const trend=(t||'UNKNOWN').toUpperCase();
  if(trend==='UP') return {label:'UP', cls:'trend-up', icon:'↑'};
  if(trend==='DOWN') return {label:'DOWN', cls:'trend-down', icon:'↓'};
  if(trend==='FLAT') return {label:'FLAT', cls:'trend-flat', icon:'→'};
  return {label:'UNKNOWN', cls:'trend-unknown', icon:'◇'};
}
function TrendBadge({trend}){ const t=trendInfo(trend); return <span className={`trend-badge ${t.cls}`}>{t.icon} {t.label}</span>; }

function volatilityInfo(v){
  const n=Number(v || 0);
  if(n < 0.08) return {label:'LOW', cls:'vol-low', text:'ruhig'};
  if(n < 0.25) return {label:'MEDIUM', cls:'vol-medium', text:'normal'};
  return {label:'HIGH', cls:'vol-high', text:'starke Bewegung'};
}
function VolatilityBadge({value}){ const v=volatilityInfo(value); return <span className={`vol-badge ${v.cls}`}>{v.label} · {pct(value)} · {v.text}</span>; }
const changelog = [
  'v0.1.3-beta: Dashboard optimiert.',
  'Live-Refresh läuft über einen zentralen 1-Sekunden-Timer.',
  'Nur sichtbare Bereiche werden aktualisiert.',
  'Backend-Sicherheit blockiert Trading/Lernen bei instabilem Backend.',
  'KI-Entscheidung nutzt 24H High-/Low-Gewichtung.',
  'Backend-Logging verbessert.',
  'Keine echten Coinbase-Orders.'
];


function App(){
  const [active,setActive]=useState('Dashboard');
  const [status,setStatus]=useState(null);
  const [analysis,setAnalysis]=useState(null);
  const [trades,setTrades]=useState([]);
  const [tradeOverview,setTradeOverview]=useState([]);
  const [logs,setLogs]=useState([]);
  const [decisions,setDecisions]=useState([]);
  const [balance,setBalance]=useState(null);
  const [db,setDb]=useState(null);
  const [settingsRows,setSettingsRows]=useState([]);
  const [monitor,setMonitor]=useState(null);
  const [timeframes,setTimeframes]=useState(null);
  const [startProtection,setStartProtection]=useState(null);
  const [error,setError]=useState('');
  const [showChangelog,setShowChangelog]=useState(()=>localStorage.getItem('webshake_changelog_v0_1_0_beta_seen')!=='1');

  async function get(path, opts={}){
    const timeoutMs = opts.timeoutMs || 1800;
    const controller = new AbortController();
    const timer = setTimeout(()=>controller.abort(), timeoutMs);
    try{
      const response = await fetch(`${API}${path}`, { signal: controller.signal, cache: 'no-store' });
      if(!response.ok){
        const text = await response.text().catch(()=> '');
        throw new Error(`API ${path} antwortet mit HTTP ${response.status}: ${text}`);
      }
      return await response.json();
    } finally {
      clearTimeout(timer);
    }
  }
  async function safeGet(path, fallback){
    try { return await get(path); }
    catch(e){ console.warn('Webshake API Fehler:', path, e); return fallback; }
  }
  async function loadFast(persist=false){
    const st = await safeGet('/status', null);
    if(st){
      setStatus(st);
      setError('');
    } else {
      setError(BACKEND_ERROR);
      return;
    }
    const an = await safeGet(`/ai/analyze?persist=${persist ? 'true' : 'false'}`, null);
    if(an){
      setAnalysis(an);
    } else {
      const latest = await safeGet('/ai/latest', null);
      if(latest) setAnalysis(latest);
    }
  }
  async function loadSlow(){
    const [tr, tov, lo, de, ba, dbo, se, tf, sp] = await Promise.all([
      safeGet('/trades?limit=100', trades),
      safeGet('/trades/overview?limit=100', tradeOverview),
      safeGet('/logs?limit=100', logs),
      safeGet('/ai/decisions?limit=150', decisions),
      safeGet('/account/balance', balance),
      safeGet('/db/overview', db),
      safeGet('/settings', settingsRows),
      safeGet('/market/timeframes', timeframes),
      safeGet('/paper/start-protection', startProtection)
    ]);
    if(tr) setTrades(tr);
    if(tov) setTradeOverview(tov);
    if(lo) setLogs(lo);
    if(de) setDecisions(de);
    if(ba) setBalance(ba);
    if(dbo) setDb(dbo);
    if(se) setSettingsRows(se);
    if(tf) setTimeframes(tf);
    if(sp) setStartProtection(sp);
  }
  async function loadMonitor(){ const m = await safeGet('/ai/live-monitor', null); if(m) setMonitor(m); }
  async function load(){ await Promise.all([loadFast(true), loadSlow(), loadMonitor()]); }
  useEffect(()=>{
    let stopped=false;
    let tick=0;
    let busy=false;

    async function visibleRefresh(){
      if(stopped || busy) return;
      busy=true;
      tick += 1;
      try{
        if(active==='Dashboard'){
          await loadFast(tick % 10 === 0);
          await loadSlow();
        } else if(active==='KI Live-Monitor'){
          await loadMonitor();
        } else if(active==='Live Trading'){
          await loadFast(false);
          await loadSlow();
        } else if(active==='Datenbank' || active==='Logs'){
          if(tick % 5 === 0) await loadSlow();
        } else if(active==='Risiko' || active==='Einstellungen'){
          if(tick % 20 === 0 && !document.activeElement?.matches?.('input,select,textarea')) await loadSlow();
        }
      } finally {
        busy=false;
      }
    }

    load();
    const timer=setInterval(visibleRefresh,1000);
    return()=>{stopped=true;clearInterval(timer)}
  },[active]);
  async function emergency(){ if(status?.risk?.emergency_stop) return; await fetch(`${API}/risk/emergency-stop`,{method:'POST'}); load(); }
  async function resume(){ await fetch(`${API}/risk/resume`,{method:'POST'}); load(); }
  function closeApp(){ if(confirm('Webshake Trading wirklich beenden?\n\nAlle Hintergrundprozesse werden sauber geschlossen.')) window.webshakeWindow?.shutdown?.(); }
  function updateRestart(){ const choice=prompt('Was möchtest du machen?\n\n1 = Software neu starten\n2 = Update installieren\n0 = Abbrechen','1'); if(choice==='1'){ if(confirm('Software jetzt sauber neu starten?')) window.webshakeWindow?.restart?.(); } else if(choice==='2'){ if(confirm('Update installieren und danach automatisch starten?')) window.webshakeWindow?.updateRestart?.(); } }

  return <div className="app">
    {showChangelog && <Changelog onClose={()=>{localStorage.setItem('webshake_changelog_v0_1_0_beta_seen','1');setShowChangelog(false)}}/>}
    <div className="topbar"><div className="brand-centered"><div className="brand-title">Webshake Trading</div><div className="brand-version">v0.1.3-beta</div></div><div className="window-actions"><button onClick={()=>window.webshakeWindow?.minimize?.()}>—</button><button onClick={()=>window.webshakeWindow?.maximize?.()}>□</button><button onClick={()=>window.webshakeWindow?.close?.()}>×</button></div></div>
    <aside className="sidebar">
      <div className="current">{active}</div>
      {menu.map(m=><button key={m} onClick={()=>setActive(m)} className="navbtn">{m}</button>)}
      <button className="update-restart" onClick={updateRestart}><RefreshCw size={18}/> UPDATE-NEUSTART</button>
      <button className="exit" onClick={closeApp}><DoorOpen size={18}/> BEENDEN</button>
      <button className="stop" onClick={emergency} disabled={!!status?.risk?.emergency_stop}><Power size={18}/> {status?.risk?.emergency_stop?'SYSTEM GESTOPPT':'NOT-AUS'}</button>
      {status?.risk?.emergency_stop && <button className="resume" onClick={resume}>System fortsetzen</button>}
    </aside>
    <main className="panel">
      <Header active={active} reload={load}/>
      {error && <div className="card danger">{error}</div>}
      {active==='Dashboard' && <Dashboard status={status} analysis={analysis} trades={trades} tradeOverview={tradeOverview} logs={logs} balance={balance} decisions={decisions} timeframes={timeframes} startProtection={startProtection}/>} 
      {active==='KI Analyse' && <AI analysis={analysis} decisions={decisions} timeframes={timeframes} startProtection={startProtection}/>} 
      {active==='KI Live-Monitor' && <LiveMonitor monitor={monitor} status={status}/>} 
      {active==='Live Trading' && <Trading trades={trades} tradeOverview={tradeOverview} reload={load} status={status} balance={balance}/>} 
      {active==='Risiko' && <Risk status={status} reload={load}/>} 
      {active==='Datenbank' && <DatabasePage db={db} trades={trades} logs={logs} decisions={decisions} settingsRows={settingsRows} reload={load}/>} 
      {active==='Logs' && <Logs initialLogs={logs}/>} 
      {active==='Einstellungen' && <SettingsPage status={status} settingsRows={settingsRows}/>} 
      {active==='Strategien' && <Strategies/>} 
    </main>
  </div>
}
function Header({active}){return <div className="section-title"><Activity/> {active}</div>}
function Card({icon,title,children}){return <div className="card"><h3>{icon} {title}</h3><div>{children}</div></div>}
function Changelog({onClose}){return <div className="modal-backdrop"><div className="modal"><button className="modal-close" onClick={onClose}><X size={18}/></button><h2>Webshake Trading v0.1.3-beta</h2><p>Neue Version erfolgreich geladen.</p><ul>{changelog.map((c,i)=><li key={i}>{c}</li>)}</ul><button className="primary" onClick={onClose}>Verstanden</button></div></div>}


function StartProtectionBadge({startProtection,status}){
  const remaining = Number(startProtection?.remaining_seconds || 0);
  const active = !!startProtection?.active;
  const emergency = !!status?.risk?.emergency_stop;

  if(emergency){
    return <span className="startschutz start-red">Trading gesperrt</span>
  }

  if(active){
    return <span className="startschutz start-orange">Startschutz aktiv · {remaining}s</span>
  }

  return <span className="startschutz start-green">Paper-Trading freigegeben</span>
}


function Probabilities({data}){
  const probs = data?.probabilities || {};
  const action = String(data?.action || 'HOLD').toUpperCase();
  const conf = Math.max(0, Math.min(100, Number(data?.confidence || 0) * 100));
  let buy = Number(probs.BUY ?? probs.buy ?? 0);
  let sell = Number(probs.SELL ?? probs.sell ?? 0);
  let hold = Number(probs.HOLD ?? probs.hold ?? 0);
  if((buy + sell + hold) <= 0){
    if(action === 'BUY'){ buy = conf; hold = Math.max(0, 100 - conf); sell = 0; }
    else if(action === 'SELL'){ sell = conf; hold = Math.max(0, 100 - conf); buy = 0; }
    else { hold = conf || 100; buy = (100 - hold) / 2; sell = (100 - hold) / 2; }
  }
  const total = buy + sell + hold;
  if(total > 0 && Math.abs(total - 100) > 1){
    buy = buy / total * 100;
    sell = sell / total * 100;
    hold = Math.max(0, 100 - buy - sell);
  }
  const items = [
    ['BUY', buy, 'prob-card-buy'],
    ['SELL', sell, 'prob-card-sell'],
    ['HOLD', hold, 'prob-card-hold']
  ];
  return <div className="prob-panel">{items.map(([label,value,cls])=><div className={`prob-card ${cls}`} key={label}><span>{label}</span><b>{Number(value).toFixed(1)}%</b><i style={{width:`${Math.max(3, Math.min(100, Number(value)))}%`}} /></div>)}</div>
}

function MultiTimeframeBox({timeframes,analysis}){
  const frames = timeframes?.timeframes || analysis?.timeframes?.timeframes || analysis?.indicators?.multi_timeframe?.timeframes || {};
  const order = ['1M','5M','15M','1H','4H','24H'];
  const hasFrames = Object.keys(frames || {}).length > 0;
  return <div className="wide card">
    <h3>Multi-Timeframe-Analyse</h3>
    {!hasFrames && <p className="note">Warte auf Runtime-Multi-Timeframe-Daten vom Backend...</p>}
    <div className="timeframe-grid">
      {order.map(label=>{
        const f = frames[label] || {};
        return <div className="timeframe-card" key={label}>
          <div className="tf-head"><b>{label}</b><TrendBadge trend={f.trend || 'UNKNOWN'}/></div>
          <small>{f.ready ? 'auswertbar' : 'warte auf Daten'} · {Number(f.samples || 0)}/{Number(f.required_samples || 0) || '?'} Punkte</small>
          <p>Momentum: {Number(f.momentum_pct || 0).toFixed(2)}%</p>
          <p>Volatilität: {Number(f.volatility_pct || 0).toFixed(2)}%</p>
          <small>{f.reason || ''}</small>
        </div>
      })}
    </div>
  </div>
}

function Dashboard({status,analysis,trades,tradeOverview,logs,balance,decisions,timeframes,startProtection}){return <div className="grid">
  <Card icon={<Bot/>} title="KI Status"><p>{status?.risk?.emergency_stop?'SYSTEM GESTOPPT':'Bereit'}</p><small>Backend: {status?.backend_stable===false?'FEHLER':'ONLINE'}</small><small>{status?.risk?.emergency_stop?'Marktanalyse aktiv · Trading gesperrt':'Live-UI ca. 500 ms · KI-Speicherung ca. 10 s'} · Paper-Trading: aktiv</small></Card>
  <Card icon={<LineChart/>} title="BTC Markt"><p>{euro(analysis?.tick?.price_eur)}</p><small>{analysis?.tick?.source}{analysis?.tick?.fallback?' · Fallback':''}</small></Card>
  <Card icon={<TrendingUp/>} title="Hoch"><p className="positive">{euro(analysis?.tick?.high_eur || analysis?.indicators?.high_eur)}</p><small>höchster gespeicherter Live-Wert</small></Card>
  <Card icon={<TrendingDown/>} title="Tief"><p className="negative">{euro(analysis?.tick?.low_eur || analysis?.indicators?.low_eur)}</p><small>niedrigster gespeicherter Live-Wert</small></Card>
  <Card icon={<ShieldAlert/>} title="Risiko"><p>Max Trade: {euro(status?.risk?.max_trade_size_eur)}</p><small>Tageslimit: {euro(status?.risk?.daily_loss_limit_eur)}</small></Card>
  <Card icon={<Wallet/>} title="Guthaben"><p>Verfügbar: {euro(balance?.available_eur)}</p><small>Offene Trades: {euro(balance?.open_trades_value_eur || balance?.btc_value_eur)} · Gesamt: {euro(balance?.total_value_eur)} · BTC: {balance?.btc_amount || 0}</small></Card>
  <Card icon={<Database/>} title="Datenbank"><p>{trades?.length || 0} Trades</p><small>{logs?.length || 0} Logs · {decisions?.length || 0} KI-Entscheidungen</small></Card>
  <Card icon={<Wallet/>} title="Tages-/Paper-Stand"><p className={Number(balance?.profit_loss_eur)>=0?'positive':'negative'}>{euro(balance?.profit_loss_eur)}</p><small>{pct(balance?.profit_loss_pct)} seit Paper-Startkapital {euro(balance?.start_eur)}</small></Card>
  <div className="wide card"><h3>Aktuelle KI-Entscheidung</h3><p className="decision">{analysis?.action} · {(analysis?.confidence*100 || 0).toFixed(0)}%</p><Probabilities data={analysis}/><p>{analysis?.reason}</p><div className="chips"><StartProtectionBadge startProtection={startProtection} status={status}/><TrendBadge trend={analysis?.indicators?.trend}/><span>SMA kurz: {euro(analysis?.indicators?.sma_short)}</span><span>SMA lang: {euro(analysis?.indicators?.sma_long)}</span><VolatilityBadge value={analysis?.indicators?.volatility_20_samples_pct}/><span>gespeicherte KI-Daten: {decisions?.length || 0}</span></div></div>
  <MultiTimeframeBox timeframes={timeframes} analysis={analysis}/>
  <div className="wide card"><h3>Trade-Übersicht seit Tradebeginn</h3><DataTable rows={tradeOverview} cols={['created_at','side','status','entry_price_eur','current_price_eur','amount_eur','pnl_eur','pnl_pct','reason']} /></div>
</div>}
function AI({analysis,decisions}){const [debug,setDebug]=useState(false); const indicators=analysis?.indicators || {}; return <div className="grid"><div className="wide card ai-summary"><div className="ai-head"><div><h3>KI Analyse v0.9</h3><p className="decision">{analysis?.action || 'WARTET'} · {((analysis?.confidence || 0)*100).toFixed(0)}%</p><p>{analysis?.reason || 'Die KI sammelt Live-Daten.'}</p></div><button className="mini" onClick={()=>setDebug(!debug)}>{debug?'Entwicklerdaten ausblenden':'Entwicklerdaten anzeigen'}</button></div><div className="grid mini-grid"><Card icon={<LineChart/>} title="Trend"><p><TrendBadge trend={indicators.trend}/></p><small>Kurz: {euro(indicators.sma_short)} · Lang: {euro(indicators.sma_long)}</small></Card><Card icon={<Activity/>} title="Volatilität"><p><VolatilityBadge value={indicators.volatility_20_samples_pct}/></p><small>20 Live-Datenpunkte</small></Card><Card icon={<ShieldAlert/>} title="Signalstärke"><p>{((analysis?.confidence || 0)*100).toFixed(0)}%</p><small>BUY / SELL / HOLD Bewertung</small></Card><Card icon={<Database/>} title="Strategie"><p>{analysis?.strategy || '-'}</p><small>Entscheidung wird gespeichert</small></Card></div>{debug && <div className="debugbox"><h3>Entwickler-Modus · Rohdaten</h3><pre>{JSON.stringify(analysis,null,2)}</pre></div>}</div><div className="wide card"><h3>KI-Entscheidungs-Historie</h3><DataTable rows={decisions} cols={['created_at','action','confidence','price_eur','trend','volatility_pct','reason']} /></div></div>}
function Trading({trades,tradeOverview,reload,status,balance}){const [amount,setAmount]=useState(1); async function trade(side){if(status?.risk?.emergency_stop){alert('Not-Aus ist aktiv. Marktanalyse läuft weiter, aber Trading ist gesperrt.'); return;} await fetch(`${API}/trading/paper/${side}?amount_eur=${Number(amount)||1}`,{method:'POST'}); reload()} return <div className="card"><h3>Paper Trading</h3><p>Live-Daten werden schnell aktualisiert. Die Oberfläche läuft automatisch live; KI-Speicherung bleibt getrennt. Echte Orders sind weiterhin gesperrt.</p><p><b>Status:</b> {status?.risk?.emergency_stop ? 'Not-Aus aktiv' : 'bereit'} · Paper-Gesamtwert: {euro(balance?.total_value_eur)}</p><label>Paper-Trade Betrag in €<input value={amount} onChange={e=>setAmount(e.target.value)} /></label><button className="primary" onClick={()=>trade('BUY')}>Paper-Buy testen</button><button className="secondary" onClick={()=>trade('SELL')}>Paper-Sell testen</button><h3>Gewinn/Verlust seit Tradebeginn</h3><DataTable rows={tradeOverview} cols={['created_at','side','entry_price_eur','current_price_eur','amount_eur','pnl_eur','pnl_pct','reason']} /><h3>Trade-Historie</h3><DataTable rows={trades} cols={['created_at','side','amount_eur','btc_amount','price_eur','reason']} /></div>}
function LiveMonitor({monitor,status}){const items=monitor?.items || []; return <div className="grid"><div className="wide card"><h3><Radio/> KI Live-Monitor</h3><p>{status?.risk?.emergency_stop ? 'SYSTEM GESTOPPT — MARKTANALYSE AKTIV' : 'KI beobachtet den Markt'}</p><small><Clock size={14}/> Serverzeit: {monitor?.server_time ? ts(monitor.server_time) : 'warte auf Daten...'}</small><div className="timeline">{items.map((it,i)=><div className={`timeline-row ${it.level||'info'}`} key={i}><span>{it.time}</span><b>{it.message}</b></div>)}</div></div></div>}
function Risk({status,reload}){ const [form,setForm]=useState(status?.risk || {}); useEffect(()=>{setForm(status?.risk || {})},[status]); function update(k,v){setForm(prev=>({...prev,[k]:v}))} async function save(){ await fetch(`${API}/risk/settings`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...form,max_trade_size_eur:Number(form.max_trade_size_eur),daily_loss_limit_eur:Number(form.daily_loss_limit_eur),max_open_trades:Number(form.max_open_trades)})}); reload(); } return <div className="card"><h3>Risk Shield</h3><div className="formgrid"><label>Maximaler Trade in €<input value={form.max_trade_size_eur ?? 5} onChange={e=>update('max_trade_size_eur',e.target.value)} /></label><label>Tägliches Verlustlimit in €<input value={form.daily_loss_limit_eur ?? 2} onChange={e=>update('daily_loss_limit_eur',e.target.value)} /></label><label>Max offene Trades<input value={form.max_open_trades ?? 1} onChange={e=>update('max_open_trades',e.target.value)} /></label></div><label className="check"><input type="checkbox" checked={!!form.require_strategy_approval} onChange={e=>update('require_strategy_approval',e.target.checked)} /> Strategieänderungen müssen bestätigt werden</label><label className="check"><input type="checkbox" checked={!!form.auto_trading_enabled} onChange={e=>update('auto_trading_enabled',e.target.checked)} /> Auto-Trading erlauben</label><button className="primary" onClick={save}><Save size={16}/> Risiko speichern</button><p className="note">Die Einstellungen werden in der Datenbank gespeichert und vor Updates gesichert.</p></div>}
function DatabasePage({db,trades,logs,decisions,settingsRows,reload}){
  const [tab,setTab]=useState('KI-Entscheidungen');
  const [filter,setFilter]=useState({q:'',level:'',category:''});
  const tabs=['KI-Entscheidungen','Handel','Protokolle','Einstellungen'];
  let rows = tab==='Handel'?trades:tab==='Protokolle'?logs:tab==='Einstellungen'?settingsRows:decisions;
  if(tab==='Protokolle'){
    rows=(rows||[]).filter(r=>(!filter.q || String(r.message||'').toLowerCase().includes(filter.q.toLowerCase())) && (!filter.level || String(r.level||'').toLowerCase().includes(filter.level.toLowerCase())) && (!filter.category || String(r.message||'').toLowerCase().includes(filter.category.toLowerCase())));
  }
  const cols = tab==='Handel'?['id','created_at','side','amount_eur','btc_amount','price_eur','reason']:tab==='Protokolle'?['id','created_at','level','message','requires_attention']:tab==='Einstellungen'?['key','value']:['id','created_at','action','confidence','price_eur','trend','volatility_pct','strategy','trade_created','reason'];
  return <div className="card"><h3><Database/> Datenbank einsehen</h3><DeleteDatabasePanel reload={reload}/><StorageLimitsPanel/>
    <div className="chips"><span>Handel: {db?.trades ?? 0}</span><span>KI-Entscheidungen: {db?.ai_decisions ?? 0}</span><span>Protokolle: {db?.logs ?? 0}</span><span>Einstellungen: {db?.settings ?? 0}</span></div>
    <div className="tabs">{tabs.map(t=><button className={tab===t?'active':''} onClick={()=>setTab(t)} key={t}>{t}</button>)}</div>
    {tab==='Protokolle' && <div className="filterbar"><input placeholder="Suche im Protokoll" value={filter.q} onChange={e=>setFilter({...filter,q:e.target.value})}/><select value={filter.level} onChange={e=>setFilter({...filter,level:e.target.value})}><option value="">Alle Level</option><option value="info">Info</option><option value="warning">Warnung</option><option value="critical">Kritisch</option><option value="error">Fehler</option></select><select value={filter.category} onChange={e=>setFilter({...filter,category:e.target.value})}><option value="">Alle Kategorien</option><option value="KI">KI</option><option value="Trading">Trading</option><option value="Coinbase">Coinbase</option><option value="Webshake">System</option></select><button className="mini" onClick={()=>setFilter({q:'',level:'',category:''})}>Filter zurücksetzen</button></div>}
    <DataTable rows={rows} cols={cols}/><p className="note">Einträge können gezielt gelöscht werden. Backups werden vor Updates automatisch erstellt.</p></div>}

function DeleteDatabasePanel({reload}){
  const [table,setTable]=useState('trades');
  const [rowId,setRowId]=useState('');
  async function delOne(){
    if(!rowId){ alert('Bitte ID eingeben.'); return; }
    if(!confirm(`Eintrag ${rowId} aus ${table} wirklich löschen?`)) return;
    const r=await fetch(`${API}/database/delete`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({table,id:Number(rowId)})});
    const data=await r.json();
    alert(data.ok ? 'Eintrag gelöscht.' : `Fehler: ${data.error}`);
    reload?.();
  }
  async function delAll(){
    if(!confirm(`ALLE Einträge aus ${table} wirklich löschen?`)) return;
    if(!confirm('Letzte Sicherheitsabfrage: Wirklich löschen?')) return;
    const r=await fetch(`${API}/database/delete`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({table,all:true})});
    const data=await r.json();
    alert(data.ok ? `${data.deleted} Einträge gelöscht.` : `Fehler: ${data.error}`);
    reload?.();
  }
  return <div className="delete-panel"><h3>Datenbank-Einträge löschen</h3><select value={table} onChange={e=>setTable(e.target.value)}><option value="trades">Trades</option><option value="ai_decisions">KI-Entscheidungen</option><option value="logs">Logs</option></select><input placeholder="ID" value={rowId} onChange={e=>setRowId(e.target.value)}/><button className="secondary" onClick={delOne}>Eintrag löschen</button><button className="stop-inline" onClick={delAll}>Tabelle leeren</button><p className="note">Löschaktionen werden im Log gespeichert.</p></div>
}
function StorageLimitsPanel(){
  const [ai,setAi]=useState(20000);
  const [logs,setLogs]=useState(5000);
  const [trades,setTrades]=useState(50000);
  async function save(){
    const r=await fetch(`${API}/storage/limits`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ai_decisions:Number(ai),logs:Number(logs),trades:Number(trades)})});
    const data=await r.json();
    alert(data.ok ? 'Limits gespeichert.' : 'Fehler beim Speichern.');
  }
  return <div className="delete-panel"><h3>KI-Datenspeicher Limits</h3><label>KI-Analysen<input value={ai} onChange={e=>setAi(e.target.value)}/></label><label>Logs<input value={logs} onChange={e=>setLogs(e.target.value)}/></label><label>Trades<input value={trades} onChange={e=>setTrades(e.target.value)}/></label><button className="primary" onClick={save}>Limits speichern</button></div>
}

function Logs({initialLogs}){const [q,setQ]=useState(''); const [level,setLevel]=useState(''); const rows=(initialLogs||[]).filter(r=>(!q||String(r.message||'').toLowerCase().includes(q.toLowerCase()))&&(!level||String(r.level||'').toLowerCase().includes(level.toLowerCase()))); return <div className="card"><h3>System-Protokolle</h3><div className="filterbar"><input placeholder="Protokolle durchsuchen" value={q} onChange={e=>setQ(e.target.value)}/><select value={level} onChange={e=>setLevel(e.target.value)}><option value="">Alle Level</option><option value="info">Info</option><option value="warning">Warnung</option><option value="critical">Kritisch</option><option value="error">Fehler</option></select><button className="mini" onClick={()=>{setQ('');setLevel('')}}>Filter zurücksetzen</button></div><DataTable rows={rows} cols={['created_at','level','message','requires_attention']} /></div>}
function Strategies(){return <div className="card"><h3>Strategien</h3><p>Strategien werden weiterhin zuerst simuliert und müssen vor Aktivierung freigegeben werden.</p><div className="chips"><span>Trendfolge v0.9</span><span>Volatilitätsfilter aktiv</span><span>KI-Historie speichert Signale</span><span>Logging mit Systemzeit</span></div></div>}
function SettingsPage({status,settingsRows}){return <div className="grid"><Card icon={<Settings/>} title="System"><p>{status?.app}</p><small>{status?.version}</small></Card><Card icon={<Smartphone/>} title="Mobile Companion"><p>geplant</p><small>Not-Aus und Statusansicht kommen später.</small></Card><Card icon={<Activity/>} title="Entwicklung"><p>CMD-Fenster werden standardmäßig versteckt gestartet.</p><small>Konsolenanzeige als umschaltbare Entwickleroption folgt.</small></Card><div className="wide card"><h3>Gespeicherte Einstellungen</h3><DataTable rows={settingsRows||[]} cols={['key','value']}/></div><div className="wide card"><h3>v0.9 Änderungen</h3><p>Neu: Update-Neustart, Fensterposition speichern, deutsche Datenbank-Reiter, Log-Filter, versteckter Start ohne CMD-Fenster und Start-/Beenden-Logging.</p></div></div>}
function DataTable({rows=[],cols=[]}){return <div className="tablewrap"><table><thead><tr>{cols.map(c=><th key={c}>{c}</th>)}</tr></thead><tbody>{rows.map((r,i)=><tr key={r.id||i}>{cols.map(c=>{let val=r[c]; let cls=''; if(c==='pnl_eur'||c==='pnl_pct') cls=Number(val)>=0?'positive':'negative'; if(c==='trend') return <td key={c}><TrendBadge trend={val}/></td>; return <td className={cls} key={c}>{c.includes('created_at')?ts(val): typeof val==='number' && (c.includes('eur')||c==='amount_eur')?euro(val): c.includes('pct')?pct(val): typeof val==='object'?JSON.stringify(val):String(val ?? '')}</td>})}</tr>)}</tbody></table></div>}

createRoot(document.getElementById('root')).render(<App/>);
