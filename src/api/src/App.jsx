import React, { useState, useRef, useEffect, useCallback } from "react";

const PROXY = "/api/proxy";
const ALPACA_BASE = "https://paper-api.alpaca.markets";

const SP50 = ["AAPL","MSFT","NVDA","AMZN","META","GOOGL","TSLA","JPM","V","UNH","XOM","LLY","JNJ","MA","AVGO","HD","MRK","ABBV","PG","COST","ORCL","CVX","CRM","BAC","NFLX","AMD","KO","PEP","TMO","WMT","CSCO","ACN","MCD","ABT","LIN","DHR","TXN","NKE","PM","NEE","INTC","QCOM","MS","UPS","RTX","GS","AMGN","LOW","BMY","SPY","QQQ","GLD","TLT","IWM","XLF","XLE","XLK","XLV","XLI"];
const CRYPTO20 = ["BTC-USD","ETH-USD","SOL-USD","BNB-USD","XRP-USD","ADA-USD","AVAX-USD","DOGE-USD","MATIC-USD","DOT-USD"];
const SECTORS = {"XLF":"Financials","XLE":"Energy","XLK":"Technology","XLV":"Healthcare","XLI":"Industrials","XLP":"Consumer Staples","XLY":"Consumer Disc","XLU":"Utilities","XLRE":"Real Estate","XLB":"Materials"};
const DEFAULT_RISK = { maxPerTrade: 2500, dailyLossLimit: 3000, maxPositions: 8, cooldownHours: 24, hedgeEnabled: true };

const AGENTS = [
  { id:"macro", label:"Macro Agent", icon:"🌍", color:"#7c3aed", model:"claude-haiku-4-5-20251001",
    role:`You are a Macro Analyst. Analyze the macroeconomic environment: Fed policy, inflation, dollar strength, sector rotation, risk-on vs risk-off. 3-4 sentences. End with: MACRO SIGNAL: [RISK-ON/RISK-OFF/NEUTRAL]` },
  { id:"fundamental", label:"Fundamental Analyst", icon:"📊", color:"#0ea5e9", model:"claude-haiku-4-5-20251001",
    role:`You are a Fundamental Analyst. For stocks: revenue, margins, P/E, EV/EBITDA, moat, balance sheet, earnings impact. For crypto: tokenomics, adoption, protocol revenue. For ETFs: holdings, expense ratio, sector exposure. 3-4 sentences. End with: FUNDAMENTAL SIGNAL: [BULLISH/BEARISH/NEUTRAL]` },
  { id:"technical", label:"Technical Analyst", icon:"📈", color:"#10b981", model:"claude-haiku-4-5-20251001",
    role:`You are a Technical Analyst. Analyze price momentum, trend, support/resistance vs 52W range, volume, volatility. 3-4 sentences. End with: TECHNICAL SIGNAL: [BULLISH/BEARISH/NEUTRAL]` },
  { id:"sentiment", label:"Sentiment Analyst", icon:"🧠", color:"#f59e0b", model:"claude-haiku-4-5-20251001",
    role:`You are a Sentiment Analyst with REAL recent news headlines. Analyze dominant narrative, catalysts, institutional vs retail sentiment. Reference specific headlines. 3-4 sentences. End with: SENTIMENT SIGNAL: [BULLISH/BEARISH/NEUTRAL]` },
  { id:"bull", label:"Bull Researcher", icon:"🐂", color:"#10b981", model:"claude-haiku-4-5-20251001",
    role:`You are the Bull Researcher. Make the strongest BULLISH case using all analyst signals, macro context, and news. Be specific. 3-4 sentences.` },
  { id:"bear", label:"Bear Researcher", icon:"🐻", color:"#ef4444", model:"claude-haiku-4-5-20251001",
    role:`You are the Bear Researcher. Make the strongest BEARISH case using all analyst signals, macro context, and news. Be specific. 3-4 sentences.` },
  { id:"risk", label:"Risk Manager", icon:"🛡️", color:"#f59e0b", model:"claude-opus-4-5",
    role:`You are the Risk Manager. Determine position sizing (1-5%), stop loss %, take profit %, max hold days. Consider volatility, earnings proximity, correlation. For crypto use wider stops (8-15%). For stocks use tighter stops (3-7%). High confidence = tighter stops, bigger targets.
End with: RISK VERDICT: [APPROVE/REJECT/REDUCE_SIZE] | STOP: [X]% | TARGET: [X]% | HOLD: [X] days` },
  { id:"trader", label:"Head Trader", icon:"⚡", color:"#f97316", model:"claude-opus-4-5",
    role:`You are the Head Trader. Make the final call. Consider shorting if overwhelmingly bearish. Set precise stop loss and take profit based on volatility and confidence.
End with exactly: FINAL DECISION: [BUY/SELL/SHORT/HOLD] | SIZE: [1-5]% | CONFIDENCE: [LOW/MEDIUM/HIGH] | STOP: [X]% | TARGET: [X]% | DAYS: [X]` },
  { id:"hedge", label:"Hedge Agent", icon:"🔒", color:"#ec4899", model:"claude-opus-4-5",
    role:`You are the Hedge Agent. After a trade, analyze portfolio exposure. Recommend a hedge using SPY, QQQ, GLD, or TLT if needed.
End with: HEDGE: [HEDGE_LONG/HEDGE_SHORT/NO_HEDGE] | INSTRUMENT: [ticker or NONE] | SIZE: [0-3]%` },
];

const SCANNER_PROMPT = `You are a quantitative stock scanner. Given tickers with price data, identify TOP 6 opportunities — mix of LONG and SHORT candidates.
For each: ticker, direction (LONG/SHORT), type (SWING/EARNINGS_PLAY/HEDGE), one-sentence reason, score 1-10.
Respond ONLY in JSON: {"picks":[{"ticker":"AAPL","direction":"LONG","type":"SWING","reason":"...","score":8},...]}`;

function parseDecision(text) {
  const action = text.match(/FINAL DECISION:\s*(BUY|SELL|SHORT|HOLD)/i)?.[1]?.toUpperCase();
  const conf = text.match(/CONFIDENCE:\s*(LOW|MEDIUM|HIGH)/i)?.[1];
  const size = text.match(/SIZE:\s*([\d.]+)%/i);
  const stop = text.match(/STOP:\s*([\d.]+)%/i);
  const target = text.match(/TARGET:\s*([\d.]+)%/i);
  const days = text.match(/DAYS:\s*(\d+)/i);
  return { action: action??null, confidence: conf??null, size: size?parseFloat(size[1]):null,
    stopPct: stop?parseFloat(stop[1]):5, targetPct: target?parseFloat(target[1]):10, days: days?parseInt(days[1]):10 };
}

function parseHedge(text) {
  return {
    recommendation: text.match(/HEDGE:\s*(HEDGE_LONG|HEDGE_SHORT|NO_HEDGE)/i)?.[1]??"NO_HEDGE",
    instrument: text.match(/INSTRUMENT:\s*([A-Z-]+)/i)?.[1]??"NONE",
    size: parseFloat(text.match(/SIZE:\s*([\d.]+)%/i)?.[1]??0),
  };
}

function isCrypto(sym) { return sym?.includes("-USD") || ["BTC","ETH","SOL","DOGE","ADA","XRP","AVAX","MATIC","LINK","DOT","BNB"].includes(sym); }
function formatTicker(sym) {
  const clean = sym.replace(/[-\/]USD$/i,"").toUpperCase();
  return ["BTC","ETH","SOL","DOGE","ADA","XRP","AVAX","MATIC","LINK","DOT","BNB","ATOM","UNI","LTC","BCH"].includes(clean) ? `${clean}-USD` : sym.toUpperCase();
}

function TypingText({ text, speed=3 }) {
  const [d,setD]=useState(""); const idx=useRef(0);
  useEffect(()=>{ idx.current=0; setD(""); if(!text) return;
    const iv=setInterval(()=>{ idx.current++; setD(text.slice(0,idx.current)); if(idx.current>=text.length) clearInterval(iv); },speed);
    return ()=>clearInterval(iv); },[text]);
  return <span>{d}</span>;
}

const ls=(k,d)=>{try{return JSON.parse(localStorage.getItem(k)||JSON.stringify(d));}catch{return d;}};
const ss=(k,v)=>{try{localStorage.setItem(k,JSON.stringify(v));}catch{}};
const PORT_KEY="ta_v4_port"; const WATCH_KEY="ta_v4_watch"; const RISK_KEY="ta_v4_risk"; const COOL_KEY="ta_v4_cool"; const JOURNAL_KEY="ta_v4_journal";

// ── Styles ────────────────────────────────────────────────────────────────────
const C = {
  bg: "#f0f4f8", bgCard: "#ffffff", bgDark: "#1e293b", bgSidebar: "#1e293b",
  border: "#e2e8f0", borderDark: "#334155",
  text: "#0f172a", textMuted: "#64748b", textLight: "#94a3b8",
  green: "#10b981", red: "#ef4444", blue: "#0ea5e9", orange: "#f97316",
  purple: "#7c3aed", yellow: "#f59e0b", pink: "#ec4899",
  greenBg: "#d1fae5", redBg: "#fee2e2", blueBg: "#e0f2fe",
  greenBorder: "#6ee7b7", redBorder: "#fca5a5", blueBorder: "#7dd3fc",
};

export default function TradingAgents() {
  const [mode,setMode]=useState("manual");
  const [ticker,setTicker]=useState("");
  const [newsKey,setNewsKey]=useState("");
  const [alpacaKey,setAlpacaKey]=useState("");
  const [alpacaSecret,setAlpacaSecret]=useState("");
  const [useAlpaca,setUseAlpaca]=useState(false);
  const [running,setRunning]=useState(false);
  const [scanning,setScanning]=useState(false);
  const [phase,setPhase]=useState(null);
  const [outputs,setOutputs]=useState({});
  const [decision,setDecision]=useState(null);
  const [hedgeResult,setHedgeResult]=useState(null);
  const [orderResult,setOrderResult]=useState(null);
  const [marketData,setMarketData]=useState(null);
  const [news,setNews]=useState([]);
  const [earnings,setEarnings]=useState(null);
  const [log,setLog]=useState([]);
  const [tab,setTab]=useState("agents");
  const [portfolio,setPortfolio]=useState(()=>ls(PORT_KEY,[]));
  const [watchlist,setWatchlist]=useState(()=>ls(WATCH_KEY,[]));
  const [scanResults,setScanResults]=useState([]);
  const [scanProgress,setScanProgress]=useState(0);
  const [riskSettings,setRiskSettings]=useState(()=>ls(RISK_KEY,DEFAULT_RISK));
  const [cooldowns,setCooldowns]=useState(()=>ls(COOL_KEY,{}));
  const [journal,setJournal]=useState(()=>ls(JOURNAL_KEY,[]));
  const [sectorData,setSectorData]=useState({});
  const [alpacaPositions,setAlpacaPositions]=useState([]);
  const [alpacaAccount,setAlpacaAccount]=useState(null);
  const [showSettings,setShowSettings]=useState(false);
  const [watchInput,setWatchInput]=useState("");
  const [approvedTicker,setApprovedTicker]=useState(null);
  const logRef=useRef(null);
  const monitorRef=useRef(null);

  useEffect(()=>{ ss(PORT_KEY,portfolio); },[portfolio]);
  useEffect(()=>{ ss(WATCH_KEY,watchlist); },[watchlist]);
  useEffect(()=>{ ss(RISK_KEY,riskSettings); },[riskSettings]);
  useEffect(()=>{ ss(COOL_KEY,cooldowns); },[cooldowns]);
  useEffect(()=>{ ss(JOURNAL_KEY,journal); },[journal]);
  useEffect(()=>{ if(logRef.current) logRef.current.scrollTop=logRef.current.scrollHeight; },[log]);

  useEffect(()=>{
    if(useAlpaca&&alpacaKey&&alpacaSecret){ fetchAlpacaAccount(); startMonitor(); }
    return ()=>{ if(monitorRef.current) clearInterval(monitorRef.current); };
  },[useAlpaca,alpacaKey,alpacaSecret]);

  function startMonitor(){
    if(monitorRef.current) clearInterval(monitorRef.current);
    monitorRef.current=setInterval(()=>{ fetchAlpacaAccount(); },15*60*1000);
  }

  const addLog=(msg,type="info")=>setLog(l=>[...l,{msg,type,ts:Date.now()}]);

  function checkCooldown(sym){ const last=cooldowns[sym]; if(!last) return true; return (Date.now()-last)>(riskSettings.cooldownHours*3600000); }
  function setCooldown(sym){ const u={...cooldowns,[sym]:Date.now()}; setCooldowns(u); ss(COOL_KEY,u); }
  function checkMaxPositions(){ return alpacaPositions.length<riskSettings.maxPositions; }

  async function callClaude(system,user,model="claude-haiku-4-5-20251001",json=false){
    const res=await fetch(PROXY,{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({url:"https://api.anthropic.com/v1/messages",method:"POST",
        headers:{"Content-Type":"application/json","anthropic-version":"2023-06-01"},
        body:JSON.stringify({model,max_tokens:1000,system,messages:[{role:"user",content:user}]})})});
    const data=await res.json();
    if(data.error) throw new Error(data.error.message||JSON.stringify(data.error));
    const text=data.content[0].text;
    if(json){try{return JSON.parse(text.replace(/```json|```/g,"").trim());}catch{return null;}}
    return text;
  }

  async function alpacaCall(path,method="GET",body=null){
    const res=await fetch(PROXY,{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({url:`${ALPACA_BASE}${path}`,method,
        headers:{"APCA-API-KEY-ID":alpacaKey,"APCA-API-SECRET-KEY":alpacaSecret,"Content-Type":"application/json"},
        ...(body?{body:JSON.stringify(body)}:{})})});
    return res.json();
  }

  async function fetchAlpacaAccount(){
    if(!useAlpaca||!alpacaKey||!alpacaSecret) return;
    try{ const [acct,pos]=await Promise.all([alpacaCall("/v2/account"),alpacaCall("/v2/positions")]);
      setAlpacaAccount(acct); setAlpacaPositions(Array.isArray(pos)?pos:[]); }
    catch(e){ addLog(`Alpaca sync failed`,"warn"); }
  }

  async function fetchMkt(sym){
    try{
      const url=`https://query1.finance.yahoo.com/v8/finance/chart/${sym}?interval=1d&range=5d`;
      const proxy=`https://api.allorigins.win/get?url=${encodeURIComponent(url)}`;
      const res=await fetch(proxy); const json=await res.json();
      const data=JSON.parse(json.contents);
      const meta=data.chart.result[0].meta;
      const closes=data.chart.result[0].indicators.quote[0].close.filter(Boolean);
      const prev=closes[closes.length-2]||closes[closes.length-1];
      const curr=meta.regularMarketPrice; const chg=((curr-prev)/prev)*100;
      return {symbol:sym,price:curr,prevClose:prev?.toFixed(2),change:chg.toFixed(2),
        volume:meta.regularMarketVolume?.toLocaleString()??"N/A",
        marketCap:meta.marketCap?`$${(meta.marketCap/1e9).toFixed(1)}B`:"N/A",
        high52:meta.fiftyTwoWeekHigh?.toFixed(2)??"N/A",low52:meta.fiftyTwoWeekLow?.toFixed(2)??"N/A"};
    }catch{
      const c=isCrypto(sym);
      return {symbol:sym,price:c?42000:175,prevClose:c?41000:172,change:(Math.random()*6-3).toFixed(2),
        volume:"N/A",marketCap:"N/A",high52:"N/A",low52:"N/A",simulated:true};
    }
  }

  async function fetchNews(sym){
    if(!newsKey.trim()) return [];
    try{
      const q=sym.replace("-USD","");
      const url=`https://newsapi.org/v2/everything?q=${encodeURIComponent(q)}&sortBy=publishedAt&pageSize=8&language=en&apiKey=${newsKey}`;
      const proxy=`https://api.allorigins.win/get?url=${encodeURIComponent(url)}`;
      const res=await fetch(proxy); const json=await res.json();
      const data=JSON.parse(json.contents);
      if(data.status!=="ok") return [];
      return data.articles.map(a=>({title:a.title,source:a.source?.name,publishedAt:a.publishedAt?new Date(a.publishedAt).toLocaleDateString():"",description:a.description,url:a.url}));
    }catch{ return []; }
  }

  async function fetchEarnings(sym){
    if(isCrypto(sym)) return null;
    try{
      const url=`https://query1.finance.yahoo.com/v11/finance/quoteSummary/${sym}?modules=calendarEvents`;
      const proxy=`https://api.allorigins.win/get?url=${encodeURIComponent(url)}`;
      const res=await fetch(proxy); const json=await res.json();
      const data=JSON.parse(json.contents);
      const arr=data?.quoteSummary?.result?.[0]?.calendarEvents?.earnings?.earningsDate;
      if(!arr||!arr.length) return null;
      const next=new Date(arr[0].raw*1000); const days=Math.ceil((next-new Date())/(864e5));
      return {date:next.toLocaleDateString("en-US",{month:"short",day:"numeric",year:"numeric"}),daysUntil:days,soon:days<=14&&days>=0};
    }catch{ return null; }
  }

  async function fetchSectorData(){
    const results={};
    await Promise.all(Object.keys(SECTORS).map(async t=>{
      try{ const m=await fetchMkt(t); results[t]={...m,sectorName:SECTORS[t]}; }catch{}
    }));
    setSectorData(results);
  }

  async function placeOrder(sym,action,sizePct,stopPct,targetPct,isHedge=false){
    if(!useAlpaca||!alpacaKey||!alpacaSecret) return null;
    const accountVal=parseFloat(alpacaAccount?.portfolio_value||100000);
    const amount=Math.min((sizePct/100)*accountVal,riskSettings.maxPerTrade);
    const isShort=action==="SHORT";
    const c=isCrypto(sym);
    const entryPrice=marketData?.price||0;
    const stopPrice=isShort?entryPrice*(1+stopPct/100):entryPrice*(1-stopPct/100);
    const takeProfitPrice=isShort?entryPrice*(1-targetPct/100):entryPrice*(1+targetPct/100);
    try{
      // Place bracket order with stop loss and take profit
      const body=c
        ?{symbol:sym.replace("-","/"),notional:amount.toFixed(2),side:isShort?"sell":"buy",type:"market",time_in_force:"gtc"}
        :{symbol:sym,notional:amount.toFixed(2),side:isShort?"sell":"buy",type:"market",time_in_force:"day",
          order_class:"bracket",
          stop_loss:{stop_price:stopPrice.toFixed(2)},
          take_profit:{limit_price:takeProfitPrice.toFixed(2)}};
      const order=await alpacaCall("/v2/orders","POST",body);
      if(order.id){
        addLog(`${isHedge?"HEDGE ":""}${action} ${sym} · Stop $${stopPrice.toFixed(2)} · Target $${takeProfitPrice.toFixed(2)}`,"success");
        setCooldown(sym);
        if("Notification" in window&&Notification.permission==="granted"){
          new Notification(`TradingAgents: ${action} ${sym}`,{body:`Entry: $${entryPrice.toFixed(2)} | Stop: $${stopPrice.toFixed(2)} | Target: $${takeProfitPrice.toFixed(2)}`});
        }
        return order;
      }
      addLog(`Alpaca: ${order.message}`,"error"); return null;
    }catch(e){ addLog(`Order failed: ${e.message}`,"error"); return null; }
  }

  useEffect(()=>{
    if("Notification" in window&&Notification.permission==="default") Notification.requestPermission();
  },[]);

  function addToPortfolio(sym,mkt,dec,hedgeRec,journalText){
    const entry={id:Date.now(),symbol:sym,action:dec.action,confidence:dec.confidence,size:dec.size,
      price:mkt.price,change:mkt.change,isCrypto:isCrypto(sym),
      stopPct:dec.stopPct,targetPct:dec.targetPct,days:dec.days,
      stopPrice:dec.action==="SHORT"?mkt.price*(1+dec.stopPct/100):mkt.price*(1-dec.stopPct/100),
      targetPrice:dec.action==="SHORT"?mkt.price*(1-dec.targetPct/100):mkt.price*(1+dec.targetPct/100),
      date:new Date().toLocaleDateString(),time:new Date().toLocaleTimeString(),
      outcome:null,mode,hedge:hedgeRec?.recommendation!=="NO_HEDGE"?hedgeRec:null,closed:false};
    setPortfolio(p=>[entry,...p].slice(0,100));
    if(journalText){
      setJournal(j=>[{id:Date.now(),symbol:sym,date:new Date().toLocaleDateString(),
        decision:dec.action,stopPrice:entry.stopPrice,targetPrice:entry.targetPrice,
        days:dec.days,reasoning:journalText},...j].slice(0,50));
    }
  }

  async function runAnalysis(sym,autoTrade=false){
    setRunning(true); setOutputs({}); setDecision(null); setHedgeResult(null);
    setOrderResult(null); setPhase(null); setTab("agents");
    if(!checkCooldown(sym)){addLog(`${sym} in cooldown`,"error");setRunning(false);return;}
    if(!checkMaxPositions()){addLog(`Max positions reached`,"error");setRunning(false);return;}
    try{
      addLog(`Fetching data for ${sym}...`,"info");
      const [mkt,articles,earn]=await Promise.all([fetchMkt(sym),fetchNews(sym),fetchEarnings(sym)]);
      setMarketData(mkt); setNews(articles); setEarnings(earn);
      const c=isCrypto(sym);
      const openPos=alpacaPositions.map(p=>`${p.symbol}: ${p.side} $${parseFloat(p.market_value).toFixed(0)}`).join(", ")||"None";
      const mktCtx=`ASSET: ${c?"CRYPTO":"STOCK"} · ${mkt.symbol}
Price: $${parseFloat(mkt.price).toLocaleString()} (${parseFloat(mkt.change)>=0?"+":""}${mkt.change}% today)
Prev Close: $${mkt.prevClose} | Volume: ${mkt.volume} | MCap: ${mkt.marketCap}
52W Range: $${mkt.low52} – $${mkt.high52}
${earn?`Earnings: ${earn.date} (${earn.daysUntil}d)${earn.soon?" ⚠️ EARNINGS SOON":""}`:""}\nOpen positions: ${openPos}`;
      const newsCtx=articles.length>0?`\n\nHEADLINES:\n`+articles.map((a,i)=>`${i+1}. [${a.source}] ${a.title}`).join("\n"):"\n\nNEWS: None";
      const full=mktCtx+newsCtx; const ag={};

      addLog("Running analyst agents...","info");
      await Promise.all(AGENTS.slice(0,4).map(async agent=>{
        setPhase(agent.id);
        const out=await callClaude(agent.role,`Analyze:\n\n${full}`,agent.model);
        ag[agent.id]=out; setOutputs(o=>({...o,[agent.id]:out}));
        addLog(`${agent.label} ✓`,"success");
      }));

      const sum=`MACRO:\n${ag.macro}\n\nFUNDAMENTAL:\n${ag.fundamental}\n\nTECHNICAL:\n${ag.technical}\n\nSENTIMENT:\n${ag.sentiment}`;
      for(const agent of AGENTS.slice(4,6)){
        setPhase(agent.id);
        const out=await callClaude(agent.role,`${sym}\n\n${full}\n\n${sum}`,agent.model);
        ag[agent.id]=out; setOutputs(o=>({...o,[agent.id]:out}));
        addLog(`${agent.label} ✓`,"success");
      }

      setPhase("risk");
      const rOut=await callClaude(AGENTS[6].role,`${sym}\n\n${full}\n\nBULL:\n${ag.bull}\n\nBEAR:\n${ag.bear}`,AGENTS[6].model);
      ag.risk=rOut; setOutputs(o=>({...o,risk:rOut})); addLog("Risk Manager ✓","success");

      setPhase("trader");
      const tOut=await callClaude(AGENTS[7].role,`${sym}\n\n${full}\n\n${sum}\n\nBULL:\n${ag.bull}\n\nBEAR:\n${ag.bear}\n\nRISK:\n${rOut}`,AGENTS[7].model);
      ag.trader=tOut; setOutputs(o=>({...o,trader:tOut}));
      const dec=parseDecision(tOut); setDecision(dec);
      addLog(`DECISION: ${dec.action} | Stop: ${dec.stopPct}% | Target: ${dec.targetPct}%`,dec.action==="BUY"?"success":dec.action==="SHORT"||dec.action==="SELL"?"error":"warn");

      setPhase("hedge");
      const hOut=await callClaude(AGENTS[8].role,`Trade: ${dec.action} ${sym} ${dec.size}%\nPositions: ${openPos}\nMacro: ${ag.macro}`,AGENTS[8].model);
      ag.hedge=hOut; setOutputs(o=>({...o,hedge:hOut}));
      const hedge=parseHedge(hOut); setHedgeResult(hedge); setPhase("done");

      const journalText=`${dec.action} ${sym} @ $${mkt.price} | Stop: ${dec.stopPct}% | Target: ${dec.targetPct}% | Hold: ${dec.days}d | ${dec.confidence} confidence. Bull thesis: ${ag.bull?.slice(0,120)}...`;
      addToPortfolio(sym,mkt,dec,hedge,journalText);

      if(autoTrade&&dec.action&&dec.action!=="HOLD"&&useAlpaca){
        const order=await placeOrder(sym,dec.action,dec.size||2,dec.stopPct||5,dec.targetPct||10,false);
        setOrderResult(order);
        if(hedge.recommendation!=="NO_HEDGE"&&hedge.instrument!=="NONE"&&riskSettings.hedgeEnabled){
          await placeOrder(hedge.instrument,hedge.recommendation==="HEDGE_SHORT"?"SHORT":"BUY",hedge.size,3,6,true);
        }
        await fetchAlpacaAccount();
      }
    }catch(e){ addLog(`Error: ${e.message}`,"error"); setPhase(null); }
    setRunning(false);
  }

  async function runScanner(universe){
    setScanning(true); setScanResults([]); setScanProgress(0);
    addLog(`Scanning ${Math.min(universe.length,25)} tickers...`,"info");
    const sample=universe.slice(0,25); const mktData=[];
    for(let i=0;i<sample.length;i++){
      try{ const m=await fetchMkt(sample[i]); mktData.push(m); }catch{}
      setScanProgress(Math.round((i+1)/sample.length*100));
      await new Promise(r=>setTimeout(r,100));
    }
    const summary=mktData.map(m=>`${m.symbol}: $${m.price} (${m.change>=0?"+":""}${m.change}% today), MCap ${m.marketCap}, 52W ${m.low52}-${m.high52}`).join("\n");
    try{
      const result=await callClaude(SCANNER_PROMPT,`Find top opportunities:\n\n${summary}`,"claude-opus-4-5",true);
      if(result?.picks){ setScanResults(result.picks); addLog(`Found ${result.picks.length} picks`,"success"); }
    }catch(e){ addLog(`Scanner error: ${e.message}`,"error"); }
    setScanning(false);
  }

  function addToWatchlist(sym){ if(!watchlist.includes(sym)) setWatchlist(w=>[...w,sym]); }
  function removeFromWatchlist(sym){ setWatchlist(w=>w.filter(x=>x!==sym)); }

  const acColor=decision?.action==="BUY"?C.green:decision?.action==="SHORT"||decision?.action==="SELL"?C.red:C.yellow;
  const accountVal=parseFloat(alpacaAccount?.portfolio_value||100000);
  const dayPnl=parseFloat(alpacaAccount?.equity||0)-parseFloat(alpacaAccount?.last_equity||0);

  const TABS=[
    {id:"agents",label:"🤖 Agents"},
    {id:"scanner",label:`🔍 Scanner${scanResults.length>0?` (${scanResults.length})`:""}`},
    {id:"sector",label:"📊 Sectors"},
    {id:"positions",label:`📋 Positions`},
    {id:"journal",label:`📝 Journal`},
    {id:"news",label:`📰 News${news.length>0?` (${news.length})`:""}`},
    {id:"watchlist",label:`⭐ Watchlist (${watchlist.length})`},
  ];

  return (
    <div style={{fontFamily:"'Inter','Segoe UI',sans-serif",background:C.bg,minHeight:"100vh",color:C.text}}>
      {/* Header */}
      <div style={{background:C.bgDark,padding:"12px 20px",display:"flex",alignItems:"center",gap:"12px",boxShadow:"0 2px 8px rgba(0,0,0,0.3)"}}>
        <div style={{color:"white",fontSize:"16px",fontWeight:800,letterSpacing:"-0.02em"}}>
          ◈ <span style={{color:"#34d399"}}>Trading</span><span style={{color:"#60a5fa"}}>Agents</span>
        </div>
        <div style={{fontSize:"10px",color:"#94a3b8"}}>9-Agent AI · Stocks · Crypto · ETFs · Auto Hedge</div>

        <div style={{display:"flex",gap:"4px",marginLeft:"8px"}}>
          {[["manual","🎯","Manual"],["screener","🔍","Screener"],["semiauto","⚙️","Semi-Auto"],["auto","🤖","Auto"]].map(([m,icon,label])=>(
            <button key={m} onClick={()=>setMode(m)} style={{fontSize:"10px",padding:"4px 10px",borderRadius:"6px",cursor:"pointer",border:"none",fontWeight:600,
              background:mode===m?"#3b82f6":"#334155",color:mode===m?"white":"#94a3b8",transition:"all 0.15s"}}>
              {icon} {label}
            </button>
          ))}
        </div>

        {alpacaAccount&&(
          <div style={{marginLeft:"auto",display:"flex",gap:"16px",alignItems:"center"}}>
            <div style={{textAlign:"right"}}>
              <div style={{fontSize:"9px",color:"#64748b"}}>PORTFOLIO</div>
              <div style={{fontSize:"13px",fontWeight:700,color:"white"}}>${accountVal.toLocaleString()}</div>
            </div>
            <div style={{textAlign:"right"}}>
              <div style={{fontSize:"9px",color:"#64748b"}}>DAY P&L</div>
              <div style={{fontSize:"13px",fontWeight:700,color:dayPnl>=0?"#34d399":"#f87171"}}>{dayPnl>=0?"+":""}{dayPnl.toFixed(0)}</div>
            </div>
            <div style={{textAlign:"right"}}>
              <div style={{fontSize:"9px",color:"#64748b"}}>POSITIONS</div>
              <div style={{fontSize:"13px",fontWeight:700,color:"white"}}>{alpacaPositions.length}/{riskSettings.maxPositions}</div>
            </div>
          </div>
        )}

        {marketData&&(
          <div style={{display:"flex",gap:"10px",alignItems:"center",borderLeft:"1px solid #334155",paddingLeft:"12px"}}>
            <span style={{color:"#60a5fa",fontWeight:700,fontSize:"13px"}}>{marketData.symbol}</span>
            <span style={{color:"white",fontWeight:700}}>${parseFloat(marketData.price).toLocaleString()}</span>
            <span style={{color:parseFloat(marketData.change)>=0?"#34d399":"#f87171",fontWeight:600}}>
              {parseFloat(marketData.change)>=0?"▲":"▼"} {Math.abs(marketData.change)}%
            </span>
            {earnings?.soon&&<span style={{fontSize:"10px",color:"#fbbf24",background:"#451a03",padding:"2px 6px",borderRadius:"4px"}}>⚡ EARNS {earnings.daysUntil}d</span>}
          </div>
        )}

        <button onClick={()=>setShowSettings(!showSettings)} style={{background:showSettings?"#3b82f6":"#334155",border:"none",color:"white",padding:"5px 10px",borderRadius:"6px",cursor:"pointer",fontSize:"11px",fontWeight:600}}>⚙ Risk</button>
      </div>

      {/* Risk Settings */}
      {showSettings&&(
        <div style={{background:"#f8fafc",borderBottom:`1px solid ${C.border}`,padding:"12px 20px",display:"flex",gap:"20px",alignItems:"center",flexWrap:"wrap"}}>
          <div style={{fontSize:"11px",fontWeight:700,color:C.textMuted}}>RISK CONTROLS</div>
          {[["Max Per Trade ($)",riskSettings.maxPerTrade,"maxPerTrade"],["Daily Loss Limit ($)",riskSettings.dailyLossLimit,"dailyLossLimit"],["Max Positions",riskSettings.maxPositions,"maxPositions"],["Cooldown (hrs)",riskSettings.cooldownHours,"cooldownHours"]].map(([label,val,key])=>(
            <div key={key}>
              <div style={{fontSize:"9px",color:C.textMuted,marginBottom:"2px",fontWeight:600}}>{label}</div>
              <input type="number" value={val} onChange={e=>setRiskSettings(r=>({...r,[key]:parseFloat(e.target.value)}))}
                style={{width:"90px",padding:"5px 8px",border:`1px solid ${C.border}`,borderRadius:"6px",fontSize:"12px",fontWeight:700,color:C.text,background:"white",outline:"none"}}/>
            </div>
          ))}
          <div>
            <div style={{fontSize:"9px",color:C.textMuted,marginBottom:"2px",fontWeight:600}}>AUTO HEDGE</div>
            <button onClick={()=>setRiskSettings(r=>({...r,hedgeEnabled:!r.hedgeEnabled}))}
              style={{padding:"5px 12px",borderRadius:"6px",border:"none",cursor:"pointer",fontWeight:700,fontSize:"11px",
                background:riskSettings.hedgeEnabled?C.greenBg:C.redBg,color:riskSettings.hedgeEnabled?C.green:C.red}}>
              {riskSettings.hedgeEnabled?"🔒 ON":"🔓 OFF"}
            </button>
          </div>
        </div>
      )}

      <div style={{display:"grid",gridTemplateColumns:"260px 1fr",minHeight:"calc(100vh - 57px)"}}>
        {/* LEFT SIDEBAR */}
        <div style={{background:C.bgSidebar,padding:"16px",overflowY:"auto",borderRight:"1px solid #0f172a"}}>

          {mode==="manual"&&(
            <div style={{marginBottom:"14px"}}>
              <div style={{fontSize:"10px",fontWeight:700,color:"#64748b",marginBottom:"5px",letterSpacing:"0.05em"}}>TICKER</div>
              <input value={ticker} onChange={e=>setTicker(e.target.value.toUpperCase())}
                onKeyDown={e=>e.key==="Enter"&&!running&&runAnalysis(formatTicker(ticker))}
                placeholder="AAPL, BTC, SPY..." maxLength={10}
                style={{width:"100%",boxSizing:"border-box",padding:"10px 12px",background:"#0f172a",border:"1px solid #334155",
                  borderRadius:"8px",color:"#60a5fa",fontSize:"20px",fontWeight:800,outline:"none",letterSpacing:"0.05em"}}/>
              {ticker&&<div style={{fontSize:"10px",color:isCrypto(formatTicker(ticker))?"#fb923c":"#64748b",marginTop:"3px"}}>
                {isCrypto(formatTicker(ticker))?`🪙 Crypto → ${formatTicker(ticker)}`:"📈 Stock / ETF"}
              </div>}
            </div>
          )}

          {(mode==="screener"||mode==="semiauto"||mode==="auto")&&(
            <div style={{marginBottom:"14px"}}>
              <button onClick={()=>runScanner([...SP50,...CRYPTO20])} disabled={scanning||running}
                style={{width:"100%",padding:"10px",borderRadius:"8px",border:"none",cursor:scanning?"not-allowed":"pointer",fontWeight:700,fontSize:"12px",
                  background:scanning?"#1e293b":"#3b82f6",color:scanning?"#64748b":"white",marginBottom:"6px"}}>
                {scanning?`Scanning... ${scanProgress}%`:"🔍 Scan All Markets"}
              </button>
              <button onClick={fetchSectorData}
                style={{width:"100%",padding:"7px",borderRadius:"8px",border:"1px solid #334155",cursor:"pointer",
                  fontWeight:600,fontSize:"11px",background:"transparent",color:"#94a3b8"}}>
                📊 Refresh Sectors
              </button>
            </div>
          )}

          <div style={{marginBottom:"10px"}}>
            <div style={{fontSize:"10px",fontWeight:700,color:"#64748b",marginBottom:"4px"}}>NEWS API KEY</div>
            <input type="password" value={newsKey} onChange={e=>setNewsKey(e.target.value)} placeholder="newsapi.org key..."
              style={{width:"100%",boxSizing:"border-box",padding:"7px 10px",background:newsKey?"#0f2a1a":"#0f172a",
                border:`1px solid ${newsKey?"#10b981":"#334155"}`,borderRadius:"8px",color:"#e2e8f0",fontSize:"11px",outline:"none"}}/>
            {newsKey&&<div style={{fontSize:"9px",color:C.green,marginTop:"2px"}}>✓ Live news enabled</div>}
          </div>

          <div style={{marginBottom:"12px"}}>
            <button onClick={()=>setUseAlpaca(!useAlpaca)} style={{display:"flex",alignItems:"center",gap:"8px",background:"transparent",border:"none",cursor:"pointer",padding:"0",marginBottom:"6px"}}>
              <div style={{width:"36px",height:"20px",borderRadius:"10px",background:useAlpaca?"#10b981":"#334155",position:"relative",transition:"all 0.2s"}}>
                <div style={{position:"absolute",top:"2px",left:useAlpaca?"18px":"2px",width:"16px",height:"16px",borderRadius:"50%",background:"white",transition:"left 0.2s"}}/>
              </div>
              <span style={{fontSize:"11px",fontWeight:700,color:useAlpaca?"#34d399":"#64748b"}}>Alpaca Paper Trading</span>
            </button>
            {useAlpaca&&(
              <div style={{display:"flex",flexDirection:"column",gap:"4px"}}>
                {[["API Key",alpacaKey,setAlpacaKey,"PK..."],["Secret Key",alpacaSecret,setAlpacaSecret,"secret..."]].map(([l,v,s,p])=>(
                  <input key={l} type="password" value={v} onChange={e=>s(e.target.value)} placeholder={`${l}: ${p}`}
                    style={{padding:"6px 10px",background:"#0f172a",border:"1px solid #334155",borderRadius:"8px",
                      color:"#e2e8f0",fontSize:"10px",outline:"none",width:"100%",boxSizing:"border-box"}}/>
                ))}
                <button onClick={fetchAlpacaAccount} style={{padding:"5px",background:"#1e293b",border:"1px solid #334155",borderRadius:"6px",color:"#64748b",fontSize:"10px",cursor:"pointer"}}>↻ Sync Account</button>
              </div>
            )}
          </div>

          {mode==="manual"&&(
            <button onClick={()=>runAnalysis(formatTicker(ticker))} disabled={running||!ticker.trim()}
              style={{width:"100%",padding:"11px",borderRadius:"8px",border:"none",cursor:running?"not-allowed":"pointer",
                fontWeight:700,fontSize:"13px",background:running?"#1e293b":"#3b82f6",color:running?"#64748b":"white",
                marginBottom:"14px",transition:"all 0.2s"}}>
              {running?"◈ Analyzing...":"▶ Run Agents"}
            </button>
          )}

          {/* Pipeline */}
          <div style={{marginBottom:"6px"}}>
            <div style={{fontSize:"10px",fontWeight:700,color:"#64748b",marginBottom:"8px",letterSpacing:"0.05em"}}>9-AGENT PIPELINE</div>
            {AGENTS.map(agent=>{
              const done=!!outputs[agent.id],active=phase===agent.id;
              return(
                <div key={agent.id} style={{display:"flex",alignItems:"center",gap:"8px",padding:"6px 8px",borderRadius:"6px",marginBottom:"2px",
                  background:active?"#1e3a5f":done?"#0f2a1a":"transparent",transition:"all 0.3s"}}>
                  <div style={{width:"6px",height:"6px",borderRadius:"50%",flexShrink:0,
                    background:done?agent.color:active?agent.color:"#334155",
                    boxShadow:active?`0 0 8px ${agent.color}`:"none",transition:"all 0.3s"}}/>
                  <span style={{fontSize:"11px",color:done?"white":active?"white":"#64748b",fontWeight:done||active?600:400}}>
                    {agent.icon} {agent.label}
                  </span>
                  {done&&<span style={{marginLeft:"auto",color:C.green,fontSize:"11px"}}>✓</span>}
                  {active&&<span style={{marginLeft:"auto",display:"flex",gap:"2px"}}>
                    {[0,1,2].map(i=><span key={i} style={{width:"3px",height:"3px",borderRadius:"50%",background:agent.color,display:"inline-block",animation:`pulse 0.9s ${i*0.2}s infinite`}}/>)}
                  </span>}
                </div>
              );
            })}
          </div>

          {/* Decision Card */}
          {decision?.action&&(
            <div style={{marginTop:"12px",padding:"14px",borderRadius:"10px",border:`2px solid ${acColor}`,background:"#0f172a",textAlign:"center"}}>
              <div style={{fontSize:"10px",color:"#64748b",fontWeight:700,marginBottom:"4px"}}>FINAL DECISION</div>
              <div style={{fontSize:"28px",fontWeight:800,color:acColor,marginBottom:"2px"}}>{decision.action}</div>
              <div style={{fontSize:"11px",color:"#94a3b8",marginBottom:"8px"}}>{decision.size}% position · {decision.confidence} confidence</div>
              <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:"6px",marginBottom:"8px"}}>
                <div style={{background:"#fee2e2",borderRadius:"6px",padding:"6px"}}>
                  <div style={{fontSize:"9px",color:"#ef4444",fontWeight:700}}>STOP LOSS</div>
                  <div style={{fontSize:"12px",fontWeight:800,color:"#dc2626"}}>-{decision.stopPct}%</div>
                  <div style={{fontSize:"9px",color:"#991b1b"}}>${decision.action==="SHORT"?((marketData?.price||0)*(1+decision.stopPct/100)).toFixed(2):((marketData?.price||0)*(1-decision.stopPct/100)).toFixed(2)}</div>
                </div>
                <div style={{background:"#d1fae5",borderRadius:"6px",padding:"6px"}}>
                  <div style={{fontSize:"9px",color:"#10b981",fontWeight:700}}>TAKE PROFIT</div>
                  <div style={{fontSize:"12px",fontWeight:800,color:"#059669"}}>+{decision.targetPct}%</div>
                  <div style={{fontSize:"9px",color:"#065f46"}}>${decision.action==="SHORT"?((marketData?.price||0)*(1-decision.targetPct/100)).toFixed(2):((marketData?.price||0)*(1+decision.targetPct/100)).toFixed(2)}</div>
                </div>
              </div>
              <div style={{fontSize:"10px",color:"#64748b",marginBottom:"6px"}}>Hold: {decision.days} days · Cap: ${Math.min((decision.size/100)*accountVal,riskSettings.maxPerTrade).toFixed(0)}</div>
              {hedgeResult?.recommendation!=="NO_HEDGE"&&(
                <div style={{background:"#2d1b4e",borderRadius:"6px",padding:"6px",marginBottom:"6px",fontSize:"10px",color:"#c084fc"}}>
                  🔒 Hedge: {hedgeResult.recommendation} {hedgeResult.instrument} {hedgeResult.size}%
                </div>
              )}
              {mode==="semiauto"&&!orderResult&&decision.action!=="HOLD"&&useAlpaca&&(
                <button onClick={async()=>{
                  const sym=formatTicker(ticker||approvedTicker||"");
                  const o=await placeOrder(sym,decision.action,decision.size||2,decision.stopPct||5,decision.targetPct||10,false);
                  setOrderResult(o);
                  if(hedgeResult?.recommendation!=="NO_HEDGE"&&hedgeResult?.instrument!=="NONE"&&riskSettings.hedgeEnabled){
                    await placeOrder(hedgeResult.instrument,hedgeResult.recommendation==="HEDGE_SHORT"?"SHORT":"BUY",hedgeResult.size,3,6,true);
                  }
                  await fetchAlpacaAccount();
                }}
                  style={{width:"100%",padding:"8px",borderRadius:"8px",border:"none",cursor:"pointer",fontWeight:700,fontSize:"12px",background:C.green,color:"white"}}>
                  ✓ Approve & Place Order
                </button>
              )}
              {orderResult&&<div style={{marginTop:"6px",fontSize:"10px",color:C.green,fontWeight:600}}>✓ Bracket order placed on Alpaca</div>}
            </div>
          )}
        </div>

        {/* RIGHT PANEL */}
        <div style={{display:"flex",flexDirection:"column",background:C.bg}}>
          {/* Tabs */}
          <div style={{display:"flex",borderBottom:`1px solid ${C.border}`,background:"white",padding:"0 16px",overflowX:"auto"}}>
            {TABS.map(t=>(
              <button key={t.id} onClick={()=>setTab(t.id)} style={{background:"none",border:"none",
                borderBottom:`2px solid ${tab===t.id?C.blue:"transparent"}`,
                color:tab===t.id?C.blue:C.textMuted,fontSize:"11px",fontWeight:600,
                padding:"10px 14px 8px",cursor:"pointer",whiteSpace:"nowrap",transition:"all 0.2s"}}>
                {t.label}
              </button>
            ))}
          </div>

          {/* AGENTS TAB */}
          {tab==="agents"&&(
            <div style={{flex:1,padding:"14px",display:"grid",gridTemplateColumns:"1fr 1fr",gap:"10px",alignContent:"start",overflowY:"auto"}}>
              {AGENTS.map(agent=>{
                const out=outputs[agent.id],active=phase===agent.id;
                if(!out&&!active) return null;
                return(
                  <div key={agent.id} style={{background:"white",borderRadius:"10px",padding:"14px",
                    border:`1px solid ${active?agent.color:C.border}`,
                    boxShadow:active?`0 0 12px ${agent.color}22`:"0 1px 3px rgba(0,0,0,0.06)",
                    transition:"all 0.3s",
                    ...(agent.id==="trader"||agent.id==="hedge"?{gridColumn:"1 / -1"}:{})}}>
                    <div style={{display:"flex",alignItems:"center",gap:"6px",marginBottom:"8px"}}>
                      <span style={{fontSize:"14px"}}>{agent.icon}</span>
                      <span style={{fontSize:"11px",fontWeight:700,color:agent.color,letterSpacing:"0.03em"}}>{agent.label.toUpperCase()}</span>
                      <span style={{marginLeft:"auto",fontSize:"9px",color:C.textLight,background:C.bg,padding:"1px 6px",borderRadius:"4px"}}>{agent.model.includes("opus")?"Opus":"Haiku"}</span>
                      {active&&<span style={{display:"flex",gap:"2px"}}>
                        {[0,1,2].map(i=><span key={i} style={{width:"4px",height:"4px",borderRadius:"50%",background:agent.color,display:"inline-block",animation:`pulse 0.9s ${i*0.2}s infinite`}}/>)}
                      </span>}
                    </div>
                    <div style={{fontSize:"12px",lineHeight:"1.7",color:C.textMuted,whiteSpace:"pre-wrap"}}>
                      {out?<TypingText text={out} speed={3}/>:<span style={{color:C.textLight}}>Analyzing...</span>}
                    </div>
                  </div>
                );
              })}
              {!running&&phase===null&&Object.keys(outputs).length===0&&(
                <div style={{gridColumn:"1 / -1",display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"center",padding:"60px",textAlign:"center"}}>
                  <div style={{fontSize:"48px",marginBottom:"12px"}}>◈</div>
                  <div style={{fontSize:"14px",fontWeight:700,color:C.textMuted,marginBottom:"6px"}}>9 Agents Ready</div>
                  <div style={{fontSize:"12px",color:C.textLight,lineHeight:1.7,maxWidth:"300px"}}>
                    Macro · Fundamental · Technical · Sentiment · Bull · Bear · Risk · Trader · Hedge<br/>
                    Enter a ticker or run the scanner to begin.
                  </div>
                </div>
              )}
            </div>
          )}

          {/* SCANNER TAB */}
          {tab==="scanner"&&(
            <div style={{flex:1,padding:"14px",overflowY:"auto"}}>
              {scanning&&(
                <div style={{marginBottom:"14px"}}>
                  <div style={{display:"flex",justifyContent:"space-between",fontSize:"11px",color:C.textMuted,fontWeight:600,marginBottom:"6px"}}>
                    <span>Scanning markets...</span><span>{scanProgress}%</span>
                  </div>
                  <div style={{height:"6px",background:C.border,borderRadius:"3px",overflow:"hidden"}}>
                    <div style={{height:"100%",width:`${scanProgress}%`,background:C.blue,borderRadius:"3px",transition:"width 0.3s"}}/>
                  </div>
                </div>
              )}
              {scanResults.length===0&&!scanning?(
                <div style={{display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"center",padding:"60px",textAlign:"center"}}>
                  <div style={{fontSize:"36px",marginBottom:"10px"}}>🔍</div>
                  <div style={{fontSize:"13px",fontWeight:700,color:C.textMuted,marginBottom:"6px"}}>No Scan Results</div>
                  <div style={{fontSize:"12px",color:C.textLight}}>Run the scanner to find long and short opportunities</div>
                </div>
              ):(
                <div style={{display:"flex",flexDirection:"column",gap:"8px"}}>
                  <div style={{fontSize:"11px",fontWeight:700,color:C.textMuted,marginBottom:"4px"}}>AI SCANNER PICKS</div>
                  {scanResults.map((pick,i)=>{
                    const isLong=pick.direction==="LONG";
                    const inCooldown=!checkCooldown(pick.ticker);
                    return(
                      <div key={i} style={{background:"white",borderRadius:"10px",padding:"14px",border:`1px solid ${C.border}`,boxShadow:"0 1px 3px rgba(0,0,0,0.06)"}}>
                        <div style={{display:"flex",alignItems:"center",gap:"10px",marginBottom:"6px"}}>
                          <span style={{fontWeight:800,fontSize:"15px",color:C.text}}>{pick.ticker}</span>
                          <span style={{fontSize:"10px",fontWeight:700,color:isLong?C.green:C.red,background:isLong?C.greenBg:C.redBg,padding:"2px 8px",borderRadius:"4px"}}>
                            {isLong?"▲ LONG":"▼ SHORT"}
                          </span>
                          <span style={{fontSize:"10px",color:C.textMuted,background:C.bg,padding:"2px 6px",borderRadius:"4px"}}>{pick.type}</span>
                          <span style={{fontSize:"10px",color:C.textMuted,fontWeight:600}}>{pick.score}/10</span>
                          {inCooldown&&<span style={{fontSize:"9px",color:C.yellow,background:"#fef3c7",padding:"1px 6px",borderRadius:"4px"}}>COOLDOWN</span>}
                          <div style={{marginLeft:"auto",display:"flex",gap:"6px"}}>
                            <button onClick={()=>addToWatchlist(pick.ticker)}
                              style={{padding:"4px 8px",background:C.bg,border:`1px solid ${C.border}`,borderRadius:"6px",color:C.textMuted,fontSize:"10px",cursor:"pointer",fontWeight:600}}>
                              ⭐ Watch
                            </button>
                            <button onClick={()=>{setApprovedTicker(pick.ticker);runAnalysis(pick.ticker,mode==="auto");setTab("agents");}}
                              disabled={running||inCooldown}
                              style={{padding:"4px 10px",background:mode==="auto"?C.red:C.blue,border:"none",borderRadius:"6px",
                                color:"white",fontSize:"10px",cursor:running||inCooldown?"not-allowed":"pointer",fontWeight:700,opacity:inCooldown?0.5:1}}>
                              {mode==="auto"?"Auto Trade":mode==="semiauto"?"Analyze + Trade":"Analyze"}
                            </button>
                          </div>
                        </div>
                        <div style={{fontSize:"12px",color:C.textMuted,lineHeight:1.5}}>{pick.reason}</div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* SECTORS TAB */}
          {tab==="sector"&&(
            <div style={{flex:1,padding:"14px",overflowY:"auto"}}>
              <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:"12px"}}>
                <div style={{fontSize:"12px",fontWeight:700,color:C.textMuted}}>SECTOR ROTATION TRACKER</div>
                <button onClick={fetchSectorData} style={{padding:"5px 12px",background:C.blue,border:"none",borderRadius:"6px",color:"white",fontSize:"11px",cursor:"pointer",fontWeight:600}}>↻ Refresh</button>
              </div>
              {Object.keys(sectorData).length===0?(
                <div style={{display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"center",padding:"60px",textAlign:"center"}}>
                  <div style={{fontSize:"36px",marginBottom:"10px"}}>📊</div>
                  <div style={{fontSize:"12px",color:C.textLight}}>Click Refresh to load sector performance</div>
                </div>
              ):(
                <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:"8px"}}>
                  {Object.entries(sectorData).sort(([,a],[,b])=>parseFloat(b.change)-parseFloat(a.change)).map(([ticker,data])=>{
                    const chg=parseFloat(data.change);
                    return(
                      <div key={ticker} style={{background:"white",borderRadius:"10px",padding:"12px",border:`1px solid ${C.border}`,boxShadow:"0 1px 3px rgba(0,0,0,0.04)"}}>
                        <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:"4px"}}>
                          <div>
                            <div style={{fontWeight:800,fontSize:"13px",color:C.text}}>{ticker}</div>
                            <div style={{fontSize:"10px",color:C.textMuted}}>{data.sectorName}</div>
                          </div>
                          <div style={{fontSize:"16px",fontWeight:800,color:chg>=0?C.green:C.red}}>{chg>=0?"+":""}{chg}%</div>
                        </div>
                        <div style={{height:"6px",background:C.bg,borderRadius:"3px",overflow:"hidden"}}>
                          <div style={{height:"100%",width:`${Math.min(Math.abs(chg)*20,100)}%`,background:chg>=0?C.green:C.red,borderRadius:"3px",transition:"width 0.5s"}}/>
                        </div>
                        <div style={{fontSize:"10px",color:C.textLight,marginTop:"4px"}}>${parseFloat(data.price).toFixed(2)}</div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* POSITIONS TAB */}
          {tab==="positions"&&(
            <div style={{flex:1,padding:"14px",overflowY:"auto"}}>
              {/* Live Alpaca Positions */}
              <div style={{fontSize:"11px",fontWeight:700,color:C.textMuted,marginBottom:"8px"}}>LIVE POSITIONS · ALPACA</div>
              {alpacaPositions.length===0?(
                <div style={{background:"white",borderRadius:"10px",padding:"20px",border:`1px solid ${C.border}`,textAlign:"center",marginBottom:"16px"}}>
                  <div style={{fontSize:"12px",color:C.textLight}}>No open positions. Connect Alpaca to see live data.</div>
                </div>
              ):(
                <div style={{display:"flex",flexDirection:"column",gap:"8px",marginBottom:"16px"}}>
                  {alpacaPositions.map((pos,i)=>{
                    const pnl=parseFloat(pos.unrealized_pl);
                    const pnlPct=parseFloat(pos.unrealized_plpc)*100;
                    const entry=portfolio.find(e=>e.symbol===pos.symbol&&!e.closed);
                    const curr=parseFloat(pos.current_price||0);
                    const stop=entry?.stopPrice||0;
                    const target=entry?.targetPrice||0;
                    const progress=stop&&target?Math.max(0,Math.min(100,((curr-stop)/(target-stop))*100)):50;
                    return(
                      <div key={i} style={{background:"white",borderRadius:"10px",padding:"14px",border:`1px solid ${C.border}`,boxShadow:"0 1px 3px rgba(0,0,0,0.06)"}}>
                        <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:"8px"}}>
                          <div style={{display:"flex",gap:"8px",alignItems:"center"}}>
                            <span style={{fontWeight:800,fontSize:"15px"}}>{pos.symbol}</span>
                            <span style={{fontSize:"10px",fontWeight:700,color:pos.side==="long"?C.green:C.red,background:pos.side==="long"?C.greenBg:C.redBg,padding:"2px 6px",borderRadius:"4px"}}>
                              {pos.side.toUpperCase()}
                            </span>
                          </div>
                          <div style={{textAlign:"right"}}>
                            <div style={{fontSize:"14px",fontWeight:800,color:pnl>=0?C.green:C.red}}>{pnl>=0?"+":""}{pnl.toFixed(2)}</div>
                            <div style={{fontSize:"10px",color:pnlPct>=0?C.green:C.red}}>{pnlPct>=0?"+":""}{pnlPct.toFixed(2)}%</div>
                          </div>
                        </div>
                        {entry&&(
                          <div style={{marginBottom:"8px"}}>
                            <div style={{display:"flex",justifyContent:"space-between",fontSize:"10px",color:C.textMuted,marginBottom:"4px"}}>
                              <span style={{color:C.red}}>Stop ${stop.toFixed(2)}</span>
                              <span style={{color:C.textMuted}}>Current ${curr.toFixed(2)}</span>
                              <span style={{color:C.green}}>Target ${target.toFixed(2)}</span>
                            </div>
                            <div style={{height:"8px",background:C.bg,borderRadius:"4px",overflow:"hidden",position:"relative"}}>
                              <div style={{position:"absolute",left:0,top:0,height:"100%",width:"33%",background:"#fee2e2"}}/>
                              <div style={{position:"absolute",left:"33%",top:0,height:"100%",width:"34%",background:"#fef3c7"}}/>
                              <div style={{position:"absolute",left:"67%",top:0,height:"100%",width:"33%",background:"#d1fae5"}}/>
                              <div style={{position:"absolute",top:"50%",left:`${progress}%`,transform:"translate(-50%,-50%)",width:"12px",height:"12px",borderRadius:"50%",background:C.blue,border:"2px solid white",boxShadow:"0 1px 3px rgba(0,0,0,0.3)"}}/>
                            </div>
                          </div>
                        )}
                        <div style={{fontSize:"10px",color:C.textMuted}}>{pos.qty} shares · avg ${parseFloat(pos.avg_entry_price).toFixed(2)} · mkt val ${parseFloat(pos.market_value).toFixed(0)}</div>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Decision History */}
              <div style={{fontSize:"11px",fontWeight:700,color:C.textMuted,marginBottom:"8px"}}>DECISION HISTORY</div>
              {portfolio.slice(0,20).map(entry=>{
                const ac=entry.action==="BUY"||entry.action==="LONG"?C.green:entry.action==="SHORT"||entry.action==="SELL"?C.red:C.yellow;
                return(
                  <div key={entry.id} style={{background:"white",borderRadius:"8px",padding:"10px 12px",border:`1px solid ${C.border}`,marginBottom:"6px"}}>
                    <div style={{display:"flex",alignItems:"center",gap:"8px"}}>
                      <span style={{fontWeight:800,fontSize:"13px"}}>{entry.symbol}</span>
                      <span style={{fontSize:"11px",fontWeight:700,color:ac,background:ac==="#10b981"?C.greenBg:ac==="#ef4444"?C.redBg:"#fef3c7",padding:"1px 6px",borderRadius:"4px"}}>{entry.action}</span>
                      <span style={{fontSize:"10px",color:C.textMuted}}>Stop {entry.stopPct}% · Target {entry.targetPct}%</span>
                      {entry.hedge&&<span style={{fontSize:"9px",color:C.pink,background:"#fdf2f8",padding:"1px 5px",borderRadius:"4px"}}>🔒 hedged</span>}
                      <span style={{marginLeft:"auto",fontSize:"9px",color:C.textLight}}>{entry.date}</span>
                      <div style={{display:"flex",gap:"3px"}}>
                        {[["W","win",C.green],["L","loss",C.red],["–","hold",C.yellow]].map(([l,v,c])=>(
                          <button key={v} onClick={()=>setPortfolio(p=>p.map(e=>e.id===entry.id?{...e,outcome:v}:e))}
                            style={{background:entry.outcome===v?c:"transparent",border:`1px solid ${entry.outcome===v?c:C.border}`,
                              color:entry.outcome===v?"white":C.textMuted,padding:"2px 6px",borderRadius:"4px",cursor:"pointer",fontSize:"10px",fontWeight:700}}>
                            {l}
                          </button>
                        ))}
                      </div>
                    </div>
                    <div style={{fontSize:"10px",color:C.textMuted,marginTop:"2px"}}>@ ${parseFloat(entry.price).toLocaleString()} · {entry.confidence} confidence · {entry.days}d hold</div>
                  </div>
                );
              })}
            </div>
          )}

          {/* JOURNAL TAB */}
          {tab==="journal"&&(
            <div style={{flex:1,padding:"14px",overflowY:"auto"}}>
              <div style={{fontSize:"11px",fontWeight:700,color:C.textMuted,marginBottom:"8px"}}>TRADE JOURNAL · AUTO-GENERATED</div>
              {journal.length===0?(
                <div style={{display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"center",padding:"60px",textAlign:"center"}}>
                  <div style={{fontSize:"36px",marginBottom:"10px"}}>📝</div>
                  <div style={{fontSize:"12px",color:C.textLight}}>Journal entries auto-generate after each analysis</div>
                </div>
              ):(
                journal.map((entry,i)=>(
                  <div key={i} style={{background:"white",borderRadius:"10px",padding:"14px",border:`1px solid ${C.border}`,marginBottom:"8px",boxShadow:"0 1px 3px rgba(0,0,0,0.04)"}}>
                    <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:"8px"}}>
                      <div style={{display:"flex",gap:"8px",alignItems:"center"}}>
                        <span style={{fontWeight:800,fontSize:"14px"}}>{entry.symbol}</span>
                        <span style={{fontSize:"10px",fontWeight:700,color:entry.decision==="BUY"?C.green:entry.decision==="SHORT"||entry.decision==="SELL"?C.red:C.yellow,
                          background:entry.decision==="BUY"?C.greenBg:entry.decision==="SHORT"||entry.decision==="SELL"?C.redBg:"#fef3c7",padding:"1px 6px",borderRadius:"4px"}}>
                          {entry.decision}
                        </span>
                      </div>
                      <span style={{fontSize:"10px",color:C.textLight}}>{entry.date}</span>
                    </div>
                    {entry.stopPrice&&(
                      <div style={{display:"flex",gap:"10px",marginBottom:"8px"}}>
                        <div style={{background:C.redBg,padding:"4px 8px",borderRadius:"6px",fontSize:"10px"}}>
                          <span style={{color:C.red,fontWeight:700}}>Stop </span><span style={{color:"#dc2626"}}>${entry.stopPrice?.toFixed(2)}</span>
                        </div>
                        <div style={{background:C.greenBg,padding:"4px 8px",borderRadius:"6px",fontSize:"10px"}}>
                          <span style={{color:C.green,fontWeight:700}}>Target </span><span style={{color:"#059669"}}>${entry.targetPrice?.toFixed(2)}</span>
                        </div>
                        <div style={{background:C.blueBg,padding:"4px 8px",borderRadius:"6px",fontSize:"10px"}}>
                          <span style={{color:C.blue,fontWeight:700}}>Hold </span><span style={{color:"#0369a1"}}>{entry.days}d</span>
                        </div>
                      </div>
                    )}
                    <div style={{fontSize:"12px",color:C.textMuted,lineHeight:1.65}}>{entry.reasoning}</div>
                  </div>
                ))
              )}
            </div>
          )}

          {/* NEWS TAB */}
          {tab==="news"&&(
            <div style={{flex:1,padding:"14px",overflowY:"auto"}}>
              {news.length===0?(
                <div style={{display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"center",padding:"60px",textAlign:"center"}}>
                  <div style={{fontSize:"36px",marginBottom:"10px"}}>📰</div>
                  <div style={{fontSize:"13px",fontWeight:700,color:C.textMuted,marginBottom:"4px"}}>No News Loaded</div>
                  <div style={{fontSize:"12px",color:C.textLight}}>Add a NewsAPI key and run an analysis to see live headlines</div>
                </div>
              ):(
                <div style={{display:"flex",flexDirection:"column",gap:"8px"}}>
                  <div style={{fontSize:"11px",fontWeight:700,color:C.textMuted,marginBottom:"4px"}}>{news.length} ARTICLES · {marketData?.symbol}</div>
                  {news.map((a,i)=>(
                    <a key={i} href={a.url} target="_blank" rel="noopener noreferrer"
                      style={{display:"block",textDecoration:"none",background:"white",borderRadius:"10px",padding:"12px",border:`1px solid ${C.border}`,boxShadow:"0 1px 3px rgba(0,0,0,0.04)"}}>
                      <div style={{display:"flex",justifyContent:"space-between",marginBottom:"4px"}}>
                        <span style={{fontSize:"9px",fontWeight:700,color:C.blue,letterSpacing:"0.05em"}}>{a.source?.toUpperCase()}</span>
                        <span style={{fontSize:"9px",color:C.textLight}}>{a.publishedAt}</span>
                      </div>
                      <div style={{fontSize:"12px",color:C.text,lineHeight:1.5,fontWeight:500}}>{a.title}</div>
                      {a.description&&<div style={{fontSize:"11px",color:C.textMuted,lineHeight:1.4,marginTop:"4px"}}>{a.description.slice(0,100)}...</div>}
                    </a>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* WATCHLIST TAB */}
          {tab==="watchlist"&&(
            <div style={{flex:1,padding:"14px",overflowY:"auto"}}>
              <div style={{fontSize:"11px",fontWeight:700,color:C.textMuted,marginBottom:"10px"}}>WATCHLIST</div>
              <div style={{display:"flex",gap:"8px",marginBottom:"12px"}}>
                <input value={watchInput} onChange={e=>setWatchInput(e.target.value.toUpperCase())}
                  onKeyDown={e=>{if(e.key==="Enter"&&watchInput){addToWatchlist(formatTicker(watchInput));setWatchInput("");}}}
                  placeholder="Add ticker..." maxLength={10}
                  style={{flex:1,padding:"8px 12px",border:`1px solid ${C.border}`,borderRadius:"8px",fontSize:"13px",fontWeight:700,color:C.blue,outline:"none",background:"white"}}/>
                <button onClick={()=>{if(watchInput){addToWatchlist(formatTicker(watchInput));setWatchInput("");}}}
                  style={{padding:"8px 14px",background:C.blue,border:"none",borderRadius:"8px",color:"white",fontSize:"12px",cursor:"pointer",fontWeight:700}}>
                  + Add
                </button>
              </div>
              {watchlist.length===0?(
                <div style={{textAlign:"center",padding:"40px",color:C.textLight,fontSize:"12px"}}>Add tickers to track them here</div>
              ):(
                <div style={{display:"flex",flexDirection:"column",gap:"6px"}}>
                  {watchlist.map(sym=>(
                    <div key={sym} style={{background:"white",borderRadius:"10px",padding:"12px",border:`1px solid ${C.border}`,display:"flex",alignItems:"center",gap:"10px",boxShadow:"0 1px 3px rgba(0,0,0,0.04)"}}>
                      <span style={{fontWeight:800,fontSize:"14px"}}>{sym}</span>
                      {isCrypto(sym)&&<span style={{fontSize:"9px",color:C.orange,background:"#fff7ed",padding:"1px 6px",borderRadius:"4px",fontWeight:700}}>CRYPTO</span>}
                      <div style={{marginLeft:"auto",display:"flex",gap:"6px"}}>
                        <button onClick={()=>{setTicker(sym);setMode("manual");runAnalysis(sym);setTab("agents");}}
                          style={{padding:"5px 10px",background:C.blue,border:"none",borderRadius:"6px",color:"white",fontSize:"10px",cursor:"pointer",fontWeight:700}}>
                          Analyze
                        </button>
                        <button onClick={()=>removeFromWatchlist(sym)}
                          style={{padding:"5px 8px",background:C.bg,border:`1px solid ${C.border}`,borderRadius:"6px",color:C.textMuted,fontSize:"10px",cursor:"pointer"}}>
                          ✕
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Log */}
          <div style={{borderTop:`1px solid ${C.border}`,padding:"8px 14px",background:"white",height:"90px",flexShrink:0}}>
            <div style={{fontSize:"9px",fontWeight:700,color:C.textLight,marginBottom:"4px"}}>SYSTEM LOG</div>
            <div ref={logRef} style={{overflowY:"auto",height:"60px",display:"flex",flexDirection:"column",gap:"2px"}}>
              {log.map((e,i)=>(
                <div key={i} style={{fontSize:"10px",color:e.type==="success"?C.green:e.type==="error"?C.red:e.type==="warn"?C.yellow:C.textLight}}>
                  <span style={{color:C.textLight}}>[{new Date(e.ts).toLocaleTimeString()}]</span> {e.msg}
                </div>
              ))}
              {log.length===0&&<div style={{fontSize:"10px",color:C.textLight}}>Awaiting input...</div>}
            </div>
          </div>
        </div>
      </div>

      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
        @keyframes pulse{0%,100%{opacity:.3;transform:scale(.8)}50%{opacity:1;transform:scale(1.2)}}
        input::placeholder{color:#94a3b8}
        *{box-sizing:border-box}
        a:hover{opacity:0.85}
        ::-webkit-scrollbar{width:4px;height:4px}
        ::-webkit-scrollbar-track{background:transparent}
        ::-webkit-scrollbar-thumb{background:#e2e8f0;border-radius:2px}
      `}</style>
    </div>
  );
}
