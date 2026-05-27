import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import time

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Trading Agents",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Design system ─────────────────────────────────────────────────────────────
# Colors
# --navy:   #0f172a   (darkest body text)
# --slate:  #334155   (secondary text)
# --muted:  #64748b   (labels, hints)
# --green:  #15803d   (bullish / LONG)
# --red:    #b91c1c   (bearish / SHORT)
# --amber:  #b45309   (neutral / HOLD)
# --bg:     #f1f5f9   (page background)
# --card:   #ffffff   (card background)

st.markdown("""
<style>
/* ════════════════════════════════════════════════════════════════════════════
   LIGHT THEME FOUNDATION
   config.toml sets base="light" which handles native widgets.
   These overrides lock down every remaining surface that can bleed dark.
   ════════════════════════════════════════════════════════════════════════════ */

/* ── Root canvas ── */
.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
[data-testid="stMainBlockContainer"],
[data-testid="stVerticalBlock"],
[data-testid="stHorizontalBlock"],
[data-testid="column"],
.main, .block-container {
  background-color: #f1f5f9 !important;
  color: #1e293b !important;
}

/* ── Header bar ── */
[data-testid="stHeader"] {
  background: #f1f5f9 !important;
  border-bottom: 1px solid #e2e8f0;
}

/* ── All body text ── */
p, span, div, label, li, td, th, h1, h2, h3, h4, h5, h6 {
  color: #1e293b;
}

/* Streamlit markdown containers */
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stMarkdownContainer"] span,
[data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3,
[data-testid="stMarkdownContainer"] strong {
  color: #1e293b !important;
}

/* ── Inputs / Selects / Text areas ── */
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stTextArea"] textarea,
[data-baseweb="input"] input,
[data-baseweb="textarea"] textarea {
  background: #ffffff !important;
  color: #1e293b !important;
  border: 1px solid #cbd5e1 !important;
  border-radius: 8px !important;
}
[data-testid="stTextInput"] input::placeholder,
[data-testid="stTextArea"] textarea::placeholder {
  color: #94a3b8 !important;
}

/* Selectbox */
[data-testid="stSelectbox"] [data-baseweb="select"] > div,
[data-baseweb="select"] div {
  background: #ffffff !important;
  color: #1e293b !important;
  border-color: #cbd5e1 !important;
}
[data-baseweb="popover"] ul,
[data-baseweb="popover"] li {
  background: #ffffff !important;
  color: #1e293b !important;
}

/* ── Labels above inputs ── */
[data-testid="stTextInput"] label,
[data-testid="stSelectbox"] label,
[data-testid="stNumberInput"] label,
[data-testid="stTextArea"] label,
[data-testid="stSlider"] label,
[data-testid="stRadio"] label,
[data-testid="stCheckbox"] label {
  color: #475569 !important;
  font-weight: 600 !important;
}

/* ── Buttons ── */
[data-testid="stButton"] button[kind="primary"] {
  background: #2563eb !important;
  color: #ffffff !important;
  border: none !important;
  border-radius: 8px !important;
  font-weight: 600 !important;
}
[data-testid="stButton"] button[kind="secondary"],
[data-testid="stButton"] button:not([kind]) {
  background: #ffffff !important;
  color: #1e293b !important;
  border: 1px solid #cbd5e1 !important;
  border-radius: 8px !important;
  font-weight: 600 !important;
}
[data-testid="stButton"] button:hover {
  opacity: 0.88 !important;
}

/* ── Tabs ── */
[data-testid="stTabs"] [data-baseweb="tab-list"] {
  background: transparent !important;
  border-bottom: 2px solid #e2e8f0 !important;
}
[data-testid="stTabs"] [data-baseweb="tab"] {
  background: transparent !important;
  color: #64748b !important;
  font-weight: 600 !important;
  border-bottom: 2px solid transparent !important;
}
[data-testid="stTabs"] [aria-selected="true"] {
  color: #1e293b !important;
  border-bottom-color: #2563eb !important;
}
[data-testid="stTabsContent"] {
  background: transparent !important;
  color: #1e293b !important;
}

/* ── Expander ── */
[data-testid="stExpander"] {
  background: #ffffff !important;
  border: 1px solid #e2e8f0 !important;
  border-radius: 10px !important;
}
[data-testid="stExpander"] summary,
[data-testid="stExpander"] summary p,
[data-testid="stExpander"] summary span {
  color: #1e293b !important;
  font-weight: 600 !important;
}
[data-testid="stExpander"] [data-testid="stExpanderDetails"] {
  background: #ffffff !important;
  color: #1e293b !important;
}

/* ── Metrics ── */
[data-testid="stMetric"] {
  background: #ffffff !important;
  border-radius: 10px !important;
  padding: 14px 18px !important;
  box-shadow: 0 1px 3px rgba(0,0,0,.06) !important;
}
[data-testid="stMetricLabel"] {
  color: #64748b !important;
  font-size: 11px !important;
  font-weight: 700 !important;
  text-transform: uppercase !important;
  letter-spacing: .05em !important;
}
[data-testid="stMetricValue"] {
  color: #1e293b !important;
  font-weight: 700 !important;
}
[data-testid="stMetricDelta"] {
  font-weight: 600 !important;
}

/* ── Dataframe / Table ── */
[data-testid="stDataFrame"] iframe,
[data-testid="stDataFrame"] {
  background: #ffffff !important;
  border-radius: 10px !important;
  overflow: hidden !important;
}
.dvn-scroller, .dvn-scroller * {
  background: #ffffff !important;
  color: #1e293b !important;
}

/* ── Slider ── */
[data-testid="stSlider"] [data-baseweb="slider"] [role="slider"] {
  background: #2563eb !important;
}

/* ── Alert / Info / Warning / Error boxes ── */
[data-testid="stAlert"] {
  border-radius: 8px !important;
  color: #1e293b !important;
}
[data-testid="stAlert"][data-baseweb="notification"] {
  background: #eff6ff !important;
}

/* ── Progress bar ── */
[data-testid="stProgressBar"] > div {
  background: #e2e8f0 !important;
  border-radius: 4px !important;
}
[data-testid="stProgressBar"] > div > div {
  background: #2563eb !important;
  border-radius: 4px !important;
}

/* ── Spinner ── */
[data-testid="stSpinner"] p { color: #475569 !important; }

/* ── Form ── */
[data-testid="stForm"] {
  background: #ffffff !important;
  border: 1px solid #e2e8f0 !important;
  border-radius: 12px !important;
  padding: 20px !important;
}

/* ── Radio buttons ── */
[data-testid="stRadio"] div[role="radiogroup"] label {
  color: #1e293b !important;
}

/* ════════════════════════════════════════════════════════════════════════════
   SIDEBAR  (intentionally dark navy)
   ════════════════════════════════════════════════════════════════════════════ */
[data-testid="stSidebar"],
[data-testid="stSidebar"] > div {
  background: #0f172a !important;
}
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] span {
  color: #e2e8f0 !important;
}
[data-testid="stSidebar"] [data-testid="stRadio"] label,
[data-testid="stSidebar"] [data-testid="stRadio"] span,
[data-testid="stSidebar"] [role="radiogroup"] label span {
  color: #e2e8f0 !important;
}
[data-testid="stSidebar"] hr { border-color: #334155 !important; }

/* ════════════════════════════════════════════════════════════════════════════
   CUSTOM COMPONENTS
   ════════════════════════════════════════════════════════════════════════════ */

/* ── White card ── */
.card {
  background: #ffffff !important;
  border-radius: 12px;
  padding: 20px 24px;
  box-shadow: 0 1px 4px rgba(0,0,0,.07);
  margin-bottom: 16px;
}
.card-title {
  font-size: 11px;
  font-weight: 700;
  color: #64748b !important;
  text-transform: uppercase;
  letter-spacing: .08em;
  margin-bottom: 6px;
}
.card-value {
  font-size: 26px;
  font-weight: 700;
  color: #1e293b !important;
  line-height: 1.2;
}

/* ── Signal badges ── */
.b-long    { display:inline-block; background:#dcfce7; color:#15803d !important;
             border-radius:6px; padding:2px 10px; font-size:12px; font-weight:700; }
.b-short   { display:inline-block; background:#fee2e2; color:#b91c1c !important;
             border-radius:6px; padding:2px 10px; font-size:12px; font-weight:700; }
.b-hold    { display:inline-block; background:#fef3c7; color:#92400e !important;
             border-radius:6px; padding:2px 10px; font-size:12px; font-weight:700; }
.b-bull    { display:inline-block; background:#dcfce7; color:#15803d !important;
             border-radius:6px; padding:2px 9px; font-size:11px; font-weight:700; }
.b-bear    { display:inline-block; background:#fee2e2; color:#b91c1c !important;
             border-radius:6px; padding:2px 9px; font-size:11px; font-weight:700; }
.b-neutral { display:inline-block; background:#f1f5f9; color:#475569 !important;
             border: 1px solid #cbd5e1;
             border-radius:6px; padding:2px 9px; font-size:11px; font-weight:700; }

/* ── Agent cards ── */
.agent-card {
  background: #ffffff !important;
  border-radius: 10px;
  padding: 14px 18px;
  box-shadow: 0 1px 3px rgba(0,0,0,.06);
  margin-bottom: 10px;
  border-left: 4px solid #e2e8f0;
}
.agent-bull    { border-left-color: #22c55e !important; }
.agent-bear    { border-left-color: #ef4444 !important; }
.agent-neutral { border-left-color: #94a3b8 !important; }
.agent-name    { font-size: 13px; font-weight: 700; color: #1e293b !important; }
.agent-reason  { font-size: 12px; color: #334155 !important; margin-top: 6px; line-height: 1.55; }
hr.div { border: none; border-top: 1px solid #e2e8f0; margin: 10px 0; }

/* ── Score bar ── */
.score-wrap  { margin: 6px 0 2px; }
.score-track { background: #e2e8f0; border-radius: 4px; height: 8px; position: relative; }
.score-fill  { border-radius: 4px; height: 8px; transition: width .3s; }
.score-label { font-size: 11px; color: #64748b !important; margin-top: 3px; }

/* ── Screener table ── */
.stbl { width: 100%; border-collapse: collapse; }
.stbl th {
  background: #f8fafc; color: #475569 !important;
  font-size: 11px; font-weight: 700;
  text-transform: uppercase; letter-spacing: .05em;
  padding: 10px 14px; text-align: left;
  border-bottom: 2px solid #e2e8f0;
}
.stbl td {
  padding: 10px 14px; font-size: 13px;
  color: #1e293b !important;
  border-bottom: 1px solid #f1f5f9;
}
.stbl tr:hover td { background: #f8fafc; }

/* ── Trade ticket ── */
.ticket {
  background: #ffffff !important;
  border-radius: 12px; padding: 24px;
  box-shadow: 0 2px 8px rgba(0,0,0,.07);
  border: 1px solid #e2e8f0;
}
.ticket-row   { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; margin-top: 14px; }
.ticket-label { font-size: 11px; color: #64748b !important; font-weight: 700;
                text-transform: uppercase; letter-spacing: .05em; }
.ticket-val   { font-size: 22px; font-weight: 700; color: #1e293b !important; margin-top: 2px; }

/* ── Sit-out banner ── */
.sit-out {
  background: #fffbeb; border: 2px solid #fcd34d;
  border-radius: 12px; padding: 28px 32px;
  text-align: center; margin: 24px 0;
}
.sit-out h2 { font-size: 22px; color: #92400e !important; margin: 0 0 8px; }
.sit-out p  { font-size: 14px; color: #78350f !important; margin: 0; }

/* ── Session summary grid ── */
.summary-grid {
  display: grid; grid-template-columns: repeat(4, 1fr);
  gap: 16px; margin-bottom: 20px;
}
.summary-cell {
  background: #ffffff !important;
  border-radius: 10px; padding: 16px 20px;
  box-shadow: 0 1px 3px rgba(0,0,0,.06);
}
.summary-label { font-size: 11px; color: #64748b !important; font-weight: 700;
                 text-transform: uppercase; letter-spacing: .05em; }
.summary-val   { font-size: 26px; font-weight: 700; color: #1e293b !important; margin-top: 4px; }
.summary-sub   { font-size: 11px; color: #64748b !important; margin-top: 2px; }
</style>
""", unsafe_allow_html=True)

# ── Bootstrap ─────────────────────────────────────────────────────────────────
import database as db
db.init_db()

from config import (
    SP50_TICKERS, ANTHROPIC_API_KEY, POLYGON_API_KEY,
    DEFAULT_MAX_POSITION_PCT, DEFAULT_DAILY_LOSS_LIMIT,
    DEFAULT_MAX_POSITIONS, DEFAULT_COOLDOWN_MINUTES,
    DEFAULT_STOP_LOSS_PCT, DEFAULT_TAKE_PROFIT_PCT,
)
from utils.data_fetcher import DataFetcher
from utils.portfolio import PortfolioManager
from agents import (
    MacroAgent, FundamentalAgent, TechnicalAgent, SentimentAgent,
    BullResearcher, BearResearcher, RiskManager, HeadTrader, HedgeAgent,
)

fetcher   = DataFetcher()
portfolio = PortfolioManager()


def _sdef(key, val):
    if key not in st.session_state:
        st.session_state[key] = val

_sdef("risk_config", {
    "max_position_pct":  DEFAULT_MAX_POSITION_PCT,
    "daily_loss_limit":  DEFAULT_DAILY_LOSS_LIMIT,
    "max_positions":     DEFAULT_MAX_POSITIONS,
    "cooldown_minutes":  DEFAULT_COOLDOWN_MINUTES,
    "stop_loss_pct":     DEFAULT_STOP_LOSS_PCT,
    "take_profit_pct":   DEFAULT_TAKE_PROFIT_PCT,
})
_sdef("screener_output",    None)   # dict returned by Screener.run()
_sdef("analysis_result",    None)   # full 9-agent result for selected ticker
_sdef("autonomous_running", False)
# Watchlist cache — populated lazily on first Watchlist page visit
# (not pre-loaded here so the DB read only happens when the page is opened)


# ── HTML helpers ──────────────────────────────────────────────────────────────

def badge_action(a: str) -> str:
    a = (a or "").upper()
    if a == "LONG":  return '<span class="b-long">LONG</span>'
    if a == "SHORT": return '<span class="b-short">SHORT</span>'
    return '<span class="b-hold">HOLD</span>'


def badge_signal(s: str) -> str:
    s = (s or "").upper()
    if "BULL" in s or s == "LONG":   return '<span class="b-bull">BULLISH</span>'
    if "BEAR" in s or s == "SHORT":  return '<span class="b-bear">BEARISH</span>'
    return '<span class="b-neutral">NEUTRAL</span>'


def score_bar(score: float, action: str) -> str:
    pct   = max(0, min(100, score))
    color = "#15803d" if action == "LONG" else "#b91c1c" if action == "SHORT" else "#b45309"
    return (
        f'<div class="score-wrap">'
        f'<div class="score-track">'
        f'<div class="score-fill" style="width:{pct}%;background:{color};"></div>'
        f'</div>'
        f'<span class="score-label">Score: {score:.1f}/100</span>'
        f'</div>'
    )


def conf_bar(confidence) -> str:
    pct   = int((confidence or 0) * 100)
    color = "#15803d" if pct >= 65 else "#b45309" if pct >= 45 else "#b91c1c"
    return (
        f'<div style="background:#f1f5f9;border-radius:4px;height:6px;margin-top:4px;">'
        f'<div style="width:{pct}%;background:{color};height:6px;border-radius:4px;"></div>'
        f'</div>'
        f'<span style="font-size:11px;color:#64748b;">{pct}% confidence</span>'
    )


# ── 9-agent full pipeline ─────────────────────────────────────────────────────

def run_full_analysis(ticker: str) -> dict:
    rc = st.session_state.risk_config
    with st.spinner(f"Fetching data for {ticker}…"):
        data = fetcher.get_full_data(ticker)

    port  = portfolio.get_portfolio_summary()
    port["existing_exposure_pct"] = portfolio.get_ticker_exposure(ticker, port)
    daily_pnl = db.get_daily_pnl()
    acc   = port.get("account_value", 100000)
    port["daily_pnl_pct"] = daily_pnl / acc * 100 if acc else 0

    elapsed = db.get_cooldown_minutes(ticker)
    cooldown_rem = None
    if elapsed is not None and elapsed < rc["cooldown_minutes"]:
        cooldown_rem = rc["cooldown_minutes"] - elapsed

    data.update({"portfolio": port, "risk_config": rc, "cooldown_remaining": cooldown_rem})

    steps = [
        ("Macro Agent — scanning market environment…",        MacroAgent,        "macro_analysis"),
        ("Fundamental Agent — evaluating financials…",        FundamentalAgent,  "fundamental_analysis"),
        ("Technical Agent — reading the charts…",             TechnicalAgent,    "technical_analysis"),
        ("Sentiment Agent — analysing live headlines…",       SentimentAgent,    "sentiment_analysis"),
        ("Bull Researcher — building long case…",             BullResearcher,    "bull_analysis"),
        ("Bear Researcher — building short case…",            BearResearcher,    "bear_analysis"),
        ("Risk Manager — sizing position (Opus)…",            RiskManager,       "risk_analysis"),
        ("Head Trader — final decision (Opus)…",              HeadTrader,        "trader_analysis"),
        ("Hedge Agent — checking portfolio balance (Opus)…",  HedgeAgent,        "hedge_analysis"),
    ]

    for label, AgentCls, key in steps:
        with st.spinner(label):
            r = AgentCls().analyze(data)
            data[key] = r
            db.log_decision(ticker, r.get("agent", key), r.get("signal") or r.get("action"),
                            r.get("confidence") or r.get("risk_score"),
                            r.get("reasoning") or r.get("bull_thesis") or r.get("bear_thesis"), r)

    return data


def execute_trade(ticker: str, trader_r: dict) -> dict:
    action = trader_r.get("action", "HOLD")
    stop   = trader_r.get("stop_loss")
    target = trader_r.get("take_profit")
    qty    = int(trader_r.get("quantity", 1))
    entry  = trader_r.get("entry_price", 0)

    if action == "HOLD" or not stop or not target or qty <= 0:
        return {"status": "skipped", "reason": "HOLD or missing parameters"}

    order = portfolio.submit_bracket_order(ticker, action, qty, stop, target)
    db.log_trade(ticker, action, qty, entry, stop, target,
                 status=order.get("status", "error"),
                 alpaca_order_id=order.get("order_id"),
                 notes=(trader_r.get("reasoning") or "")[:500])
    if order.get("status") not in ("error",):
        db.set_cooldown(ticker)
    return order


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📈 AI Trading Agents")
    st.markdown("---")
    page = st.radio(
        "nav", ["Manual Analysis", "Screener", "Semi-Auto", "Autonomous",
                "Watchlist", "Trade Journal", "Settings"],
        label_visibility="collapsed",
    )
    st.markdown("---")
    acc_info  = portfolio.get_account()
    connected = acc_info.get("connected", False)
    dot = "🟢" if connected else "🔴"
    st.markdown(f"{dot} Alpaca {'Connected' if connected else 'Disconnected'}")
    if connected:
        st.markdown(f"**Portfolio:** ${acc_info.get('account_value',0):,.0f}")
        st.markdown(f"**Buying Power:** ${acc_info.get('buying_power',0):,.0f}")
    if not ANTHROPIC_API_KEY:
        st.warning("⚠️ ANTHROPIC_API_KEY missing")
    if not POLYGON_API_KEY:
        st.info("💡 Add POLYGON_API_KEY for real-time TA data")
    st.markdown("---")
    dpnl = db.get_daily_pnl()
    color = "green" if dpnl >= 0 else "red"
    st.markdown(f"**Today's P&L:** :{color}[${dpnl:+,.2f}]")


def _render_analysis_result(result: dict):
    ticker   = result.get("ticker", "")
    price    = result.get("current_price", 0)
    trader_r = result.get("trader_analysis", {})
    risk_r   = result.get("risk_analysis", {})
    hedge_r  = result.get("hedge_analysis", {})
    action   = trader_r.get("action", "HOLD")

    # Header metrics
    c1, c2, c3, c4, c5 = st.columns(5)
    for col, title, val in [
        (c1, "Ticker",    f'<div class="card-value">{ticker}</div>'),
        (c2, "Price",     f'<div class="card-value">${price:,.2f}</div>'),
        (c3, "Decision",  f'<div style="margin-top:4px;">{badge_action(action)}</div>'),
        (c4, "Confidence",f'<div class="card-value">{int((trader_r.get("confidence",0))*100)}%</div>'),
        (c5, "Risk Gate", f'<div class="card-value" style="font-size:20px;">{"✅ Approved" if risk_r.get("approved") else "❌ Vetoed"}</div>'),
    ]:
        with col:
            st.markdown(
                f'<div class="card"><div class="card-title">{title}</div>{val}</div>',
                unsafe_allow_html=True,
            )

    # 4 Haiku agent signals
    st.markdown("### Agent Signals")
    cols = st.columns(4)
    for i, key in enumerate(["macro_analysis","fundamental_analysis",
                              "technical_analysis","sentiment_analysis"]):
        r   = result.get(key, {})
        sig = r.get("signal", "NEUTRAL")
        cls = "agent-bull" if "BULL" in sig else "agent-bear" if "BEAR" in sig else "agent-neutral"
        with cols[i]:
            st.markdown(
                f'<div class="agent-card {cls}">'
                f'<div class="agent-name">{r.get("agent","")}</div>'
                f'<div style="margin-top:4px;">{badge_signal(sig)}</div>'
                f'{conf_bar(r.get("confidence",0))}'
                f'<hr class="div">'
                f'<div class="agent-reason">{(r.get("reasoning","") or "")[:220]}</div>'
                f'</div>', unsafe_allow_html=True)

    # Bull vs Bear
    st.markdown("### Bull vs Bear Debate")
    bull_r = result.get("bull_analysis", {})
    bear_r = result.get("bear_analysis", {})
    cb, ca = st.columns(2)
    with cb:
        cats = "".join(f"<li style='color:#334155;'>{c}</li>"
                       for c in (bull_r.get("key_catalysts") or [])[:3])
        st.markdown(
            f'<div class="agent-card agent-bull">'
            f'<div class="agent-name">🐂 Bull Researcher</div>'
            f'{conf_bar(bull_r.get("confidence",0))}'
            f'<hr class="div">'
            f'<div class="agent-reason"><b>Thesis:</b> {bull_r.get("bull_thesis","")}</div>'
            f'<div class="agent-reason" style="margin-top:6px;"><b>Upside target:</b> '
            f'${bull_r.get("upside_target","?")}</div>'
            f'<div class="agent-reason"><b>Catalysts:</b><ul style="margin:4px 0 0 16px;">{cats}</ul></div>'
            f'</div>', unsafe_allow_html=True)
    with ca:
        risks = "".join(f"<li style='color:#334155;'>{r}</li>"
                        for r in (bear_r.get("key_risks") or [])[:3])
        st.markdown(
            f'<div class="agent-card agent-bear">'
            f'<div class="agent-name">🐻 Bear Researcher</div>'
            f'{conf_bar(bear_r.get("confidence",0))}'
            f'<hr class="div">'
            f'<div class="agent-reason"><b>Thesis:</b> {bear_r.get("bear_thesis","")}</div>'
            f'<div class="agent-reason" style="margin-top:6px;"><b>Downside target:</b> '
            f'${bear_r.get("downside_target","?")}</div>'
            f'<div class="agent-reason"><b>Risks:</b><ul style="margin:4px 0 0 16px;">{risks}</ul></div>'
            f'</div>', unsafe_allow_html=True)

    # Trade ticket
    st.markdown("### Trade Ticket")
    stop   = trader_r.get("stop_loss")
    target = trader_r.get("take_profit")
    qty    = trader_r.get("quantity", 0)
    t1, t2 = st.columns([2, 1])
    with t1:
        stop_disp   = f"${stop:.2f}"   if stop   else "N/A"
        target_disp = f"${target:.2f}" if target else "N/A"
        st.markdown(
            f'<div class="ticket">'
            f'<div style="font-size:17px;font-weight:700;color:#0f172a;">'
            f'{badge_action(action)} {ticker} &nbsp;—&nbsp; {trader_r.get("time_horizon","?")}</div>'
            f'<div class="ticket-row">'
            f'<div><div class="ticket-label">Entry</div>'
            f'<div class="ticket-val">${trader_r.get("entry_price",price):,.2f}</div></div>'
            f'<div><div class="ticket-label">Stop Loss</div>'
            f'<div class="ticket-val" style="color:#b91c1c;">{stop_disp}</div></div>'
            f'<div><div class="ticket-label">Take Profit</div>'
            f'<div class="ticket-val" style="color:#15803d;">{target_disp}</div></div>'
            f'</div>'
            f'<div style="margin-top:14px;font-size:13px;color:#334155;">'
            f'<b>Qty:</b> {qty} shares &nbsp;·&nbsp; '
            f'<b>R:R:</b> {risk_r.get("risk_reward_ratio","?")} &nbsp;·&nbsp;'
            f'<b>Max loss:</b> ${risk_r.get("max_loss_dollars","?")}'
            f'</div>'
            f'<div style="margin-top:12px;font-size:13px;color:#334155;line-height:1.55;">'
            f'{(trader_r.get("reasoning","") or "")[:450]}'
            f'</div></div>',
            unsafe_allow_html=True,
        )
    with t2:
        if action != "HOLD" and risk_r.get("approved"):
            if st.button(f"Execute {action} Trade", type="primary", use_container_width=True):
                with st.spinner("Submitting bracket order…"):
                    order = execute_trade(ticker, trader_r)
                if order.get("status") == "error":
                    st.error(f"Order failed: {order.get('error')}")
                else:
                    st.success(f"✅ Submitted! Order ID: {order.get('order_id','?')}")
        elif not risk_r.get("approved"):
            st.error(f"Vetoed: {risk_r.get('veto_reason') or 'risk controls'}")
        else:
            st.info("No trade recommended (HOLD)")
        if action != "HOLD":
            if st.button("+ Watchlist", use_container_width=True):
                db.add_to_watchlist(ticker)
                st.success(f"{ticker} added")

    # Hedge alert
    if hedge_r.get("hedge_needed"):
        urgency = hedge_r.get("urgency", "LOW")
        uc = {"HIGH": "#b91c1c", "MEDIUM": "#b45309", "LOW": "#15803d"}.get(urgency, "#64748b")
        recs_html = "".join(
            f'<div style="padding:7px 0;border-bottom:1px solid #f1f5f9;color:#334155;">'
            f'{badge_action(r.get("action","?"))} <b style="color:#0f172a;">{r.get("instrument","?")}</b>'
            f' ({r.get("allocation_pct","?")}% alloc) — {r.get("rationale","")}</div>'
            for r in hedge_r.get("recommendations", [])
        )
        st.markdown("### Hedge Agent Alert")
        st.markdown(
            f'<div class="card" style="border-left:4px solid {uc};">'
            f'<div class="card-title">Hedge Needed — Urgency: '
            f'<span style="color:{uc};">{urgency}</span></div>'
            f'<div style="font-size:13px;color:#334155;margin-bottom:10px;">'
            f'{hedge_r.get("reasoning","")}</div>'
            f'{recs_html}</div>', unsafe_allow_html=True)

    # Price chart
    st.markdown("### Price Chart")
    df = fetcher.get_price_history(ticker, "6mo")
    if not df.empty:
        tech = result.get("technicals", {})
        fig  = go.Figure()
        fig.add_trace(go.Candlestick(
            x=df.index, open=df["Open"], high=df["High"],
            low=df["Low"], close=df["Close"], name="Price",
            increasing_line_color="#15803d", decreasing_line_color="#b91c1c",
        ))
        for label, key, color in [("SMA 50","sma_50","#2563eb"),("SMA 200","sma_200","#d97706")]:
            if tech.get(key):
                fig.add_hline(y=tech[key], line_dash="dash", line_color=color,
                              annotation_text=label, annotation_position="right",
                              annotation_font_color=color)
        for key, label in [("bb_upper","BB Upper"),("bb_lower","BB Lower")]:
            if tech.get(key):
                fig.add_hline(y=tech[key], line_dash="dot", line_color="#94a3b8",
                              annotation_text=label, annotation_font_color="#64748b")
        if stop:
            fig.add_hline(y=stop, line_color="#b91c1c",
                          annotation_text=f"Stop ${stop:.2f}", annotation_font_color="#b91c1c")
        if target:
            fig.add_hline(y=target, line_color="#15803d",
                          annotation_text=f"Target ${target:.2f}", annotation_font_color="#15803d")
        fig.update_layout(
            height=450, paper_bgcolor="white", plot_bgcolor="white",
            xaxis_rangeslider_visible=False,
            margin=dict(l=10, r=80, t=20, b=10),
            xaxis=dict(gridcolor="#f1f5f9", color="#334155"),
            yaxis=dict(gridcolor="#f1f5f9", color="#334155"),
            font=dict(color="#334155"),
        )
        st.plotly_chart(fig, use_container_width=True)

    # News headlines fed to Sentiment Agent
    news = result.get("news", [])
    if news:
        st.markdown("### Headlines (fed to Sentiment Agent)")
        for n in news[:5]:
            dt_raw = n.get("datetime", "")
            if isinstance(dt_raw, int):
                try:
                    dt_str = datetime.utcfromtimestamp(dt_raw).strftime("%Y-%m-%d")
                except (OSError, OverflowError, ValueError):
                    dt_str = ""
            else:
                dt_str = str(dt_raw)[:10]
            st.markdown(
                f'<div style="padding:8px 0;border-bottom:1px solid #f1f5f9;">'
                f'<span style="font-size:11px;color:#64748b;font-weight:600;">'
                f'{n.get("source","?")} &nbsp;·&nbsp; {dt_str}</span><br>'
                f'<span style="font-size:13px;color:#0f172a;">{n.get("headline","")}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: MANUAL ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════
if page == "Manual Analysis":
    st.markdown("# Manual Analysis")
    st.markdown('<p style="color:#64748b;">Enter any ticker to run all 9 agents and get a full trade recommendation.</p>', unsafe_allow_html=True)

    col1, col2 = st.columns([3, 1])
    with col1:
        ticker_input = st.text_input("Ticker Symbol", placeholder="AAPL, MSFT, NVDA…",
                                      key="manual_ticker").upper().strip()
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        run_btn = st.button("Run Analysis", type="primary", use_container_width=True)

    if run_btn and ticker_input:
        st.session_state.analysis_result = run_full_analysis(ticker_input)

    result = st.session_state.get("analysis_result")
    if result:
        _render_analysis_result(result)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: SCREENER
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Screener":
    st.markdown("# S&P 50 Screener")
    st.markdown('<p style="color:#64748b;">One-shot scan of top S&P 500 stocks — Haiku agents only. Select a ticker to run full Opus analysis.</p>', unsafe_allow_html=True)

    # ── Session summary card ──────────────────────────────────────────────────
    port_now      = portfolio.get_portfolio_summary()
    held_tickers  = [p["symbol"] for p in port_now.get("positions", [])]
    daily_pnl_val = db.get_daily_pnl()
    output        = st.session_state.get("screener_output")
    scanned       = output["tickers_scanned"] if output else 0
    strong_n      = (output["long_count"] + output["short_count"]) if output else 0

    pnl_color = "#15803d" if daily_pnl_val >= 0 else "#b91c1c"
    held_str  = ", ".join(held_tickers) if held_tickers else "None"

    st.markdown(
        f'<div class="summary-grid">'
        f'<div class="summary-cell"><div class="summary-label">Tickers Scanned</div>'
        f'<div class="summary-val">{scanned}</div>'
        f'<div class="summary-sub">this session</div></div>'
        f'<div class="summary-cell"><div class="summary-label">Strong Signals</div>'
        f'<div class="summary-val">{strong_n}</div>'
        f'<div class="summary-sub">score &gt;65 or &lt;35</div></div>'
        f'<div class="summary-cell"><div class="summary-label">Positions Held</div>'
        f'<div class="summary-val">{len(held_tickers)}</div>'
        f'<div class="summary-sub" title="{held_str}">{held_str[:30]}{"…" if len(held_str)>30 else ""}</div></div>'
        f'<div class="summary-cell"><div class="summary-label">Today\'s P&L</div>'
        f'<div class="summary-val" style="color:{pnl_color};">${daily_pnl_val:+,.2f}</div>'
        f'<div class="summary-sub">from closed trades</div></div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Controls ──────────────────────────────────────────────────────────────
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        custom_input = st.text_input(
            "Custom tickers (comma-separated, leave blank for S&P 50)",
            placeholder="AAPL, TSLA, NVDA …",
        )
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        run_screen = st.button("🔍 Scan Now", type="primary", use_container_width=True)
    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        filter_opt = st.selectbox("Show", ["All signals", "LONG only", "SHORT only"])

    if run_screen:
        tickers = (
            [t.strip().upper() for t in custom_input.split(",") if t.strip()]
            if custom_input.strip()
            else SP50_TICKERS
        )
        st.session_state.screener_output  = None
        st.session_state.analysis_result  = None

        prog  = st.progress(0.0)
        label = st.empty()

        def _cb(i, total, tick):
            prog.progress(i / max(total, 1))
            label.markdown(f"Analysing **{tick}** ({i}/{total})…")

        from utils.screener import Screener
        sc = Screener(progress_callback=_cb)
        st.session_state.screener_output = sc.run(
            tickers=tickers,
            excluded_tickers=held_tickers,
        )
        prog.empty(); label.empty()
        st.rerun()

    # ── Results ───────────────────────────────────────────────────────────────
    output = st.session_state.get("screener_output")
    if output is None:
        st.info("Press **Scan Now** to run the screener.")
    else:
        results = output["results"]

        # Apply filter
        if filter_opt == "LONG only":
            results = [r for r in results if r.get("action") == "LONG"]
        elif filter_opt == "SHORT only":
            results = [r for r in results if r.get("action") == "SHORT"]

        # Exclude HOLD and ERROR from main display
        display = [r for r in results if r.get("action") in ("LONG", "SHORT")]

        if not output["has_opportunities"]:
            st.markdown(
                '<div class="sit-out">'
                '<h2>🧘 No Compelling Opportunities Today — Sit Out</h2>'
                '<p>No ticker scored above 65 (LONG) or below 35 (SHORT). '
                'The market lacks a clear edge right now. Preserving capital is the trade.</p>'
                '</div>',
                unsafe_allow_html=True,
            )
        else:
            # Excluded tickers note
            excl = output.get("tickers_excluded", [])
            if excl:
                st.info(f"ℹ️ Excluded (already held): {', '.join(excl)}")

            # Summary chips
            c1, c2, c3, c4 = st.columns(4)
            for col, lbl, val, clr in [
                (c1, "Scanned",  output["tickers_scanned"], "#0f172a"),
                (c2, "LONG",     output["long_count"],       "#15803d"),
                (c3, "SHORT",    output["short_count"],      "#b91c1c"),
                (c4, "Excluded", len(excl),                  "#64748b"),
            ]:
                with col:
                    st.markdown(
                        f'<div class="card" style="padding:14px 20px;">'
                        f'<div class="card-title">{lbl}</div>'
                        f'<div class="card-value" style="color:{clr};">{val}</div>'
                        f'</div>', unsafe_allow_html=True)

            # Table
            if display:
                rows = ""
                for r in display:
                    action = r.get("action", "HOLD")
                    score  = r.get("score", 50)
                    bw     = int(abs(score - 50) * 2)
                    bc     = "#15803d" if action == "LONG" else "#b91c1c"
                    rsi    = r.get("rsi")
                    rsi_c  = "#b91c1c" if rsi and rsi > 70 else "#15803d" if rsi and rsi < 30 else "#334155"
                    rows += (
                        f'<tr>'
                        f'<td><b style="color:#0f172a;">{r.get("ticker","")}</b></td>'
                        f'<td style="color:#0f172a;">${r.get("price",0):,.2f}</td>'
                        f'<td>{badge_action(action)}</td>'
                        f'<td>'
                        f'<div style="display:flex;align-items:center;gap:8px;">'
                        f'<div style="background:#e2e8f0;border-radius:4px;width:70px;height:8px;">'
                        f'<div style="width:{bw}%;background:{bc};height:8px;border-radius:4px;"></div></div>'
                        f'<span style="font-size:12px;color:#334155;font-weight:600;">{score:.0f}</span>'
                        f'</div></td>'
                        f'<td>{badge_signal(r.get("macro_signal","?"))}</td>'
                        f'<td>{badge_signal(r.get("fund_signal","?"))}</td>'
                        f'<td>{badge_signal(r.get("tech_signal","?"))}</td>'
                        f'<td>{badge_signal(r.get("sent_signal","?"))}</td>'
                        f'<td style="color:#334155;">{r.get("tech_trend","?")}</td>'
                        f'<td style="color:{rsi_c};font-weight:600;">'
                        f'{f"{rsi:.1f}" if rsi else "N/A"}</td>'
                        f'</tr>'
                    )

                st.markdown(
                    f'<div class="card" style="padding:0;overflow:hidden;">'
                    f'<table class="stbl"><thead><tr>'
                    f'<th>Ticker</th><th>Price</th><th>Signal</th><th>Score/100</th>'
                    f'<th>Macro</th><th>Fund</th><th>Tech</th><th>Sent</th>'
                    f'<th>Trend</th><th>RSI</th>'
                    f'</tr></thead><tbody>{rows}</tbody></table></div>',
                    unsafe_allow_html=True,
                )

                # ── Ticker selector → full 9-agent analysis ──────────────────
                st.markdown("### Run Full Analysis on a Screener Result")
                st.markdown('<p style="color:#64748b;font-size:13px;">Selects a ticker from the screener above and runs all 9 agents including Opus for a complete trade recommendation.</p>', unsafe_allow_html=True)

                strong_tickers = [r["ticker"] for r in display]
                sel = st.selectbox("Select ticker for full analysis", ["— select —"] + strong_tickers)
                if sel != "— select —":
                    if st.button(f"Run Full Analysis: {sel}", type="primary"):
                        st.session_state.analysis_result = run_full_analysis(sel)
                        st.rerun()

        # Show full analysis result if triggered from screener
        if st.session_state.get("analysis_result"):
            st.markdown("---")
            st.markdown(f"## Full Analysis: {st.session_state.analysis_result.get('ticker','')}")
            _render_analysis_result(st.session_state.analysis_result)

        # Sector rotation
        st.markdown("### Sector Rotation")
        with st.spinner("Fetching sector ETF performance…"):
            sec = fetcher.get_sector_performance()
        if sec:
            df_sec = pd.DataFrame([
                {"Sector": s, "ETF": v.get("etf",""),
                 "1D%": v.get("ret_1d"), "5D%": v.get("ret_5d"), "1M%": v.get("ret_1m")}
                for s, v in sec.items()
            ]).sort_values("1M%", ascending=False)
            fig = px.bar(
                df_sec.dropna(subset=["1M%"]),
                x="Sector", y="1M%", color="1M%",
                color_continuous_scale=["#b91c1c","#f1f5f9","#15803d"],
                color_continuous_midpoint=0,
                title="Sector 1-Month Performance (%)",
            )
            fig.update_layout(
                height=350, paper_bgcolor="white", plot_bgcolor="white",
                coloraxis_showscale=False,
                margin=dict(l=10, r=10, t=40, b=80),
                xaxis=dict(tickangle=-30, color="#334155"),
                yaxis=dict(color="#334155"),
                font=dict(color="#334155"),
            )
            st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: SEMI-AUTO
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Semi-Auto":
    st.markdown("# Semi-Auto Trading")
    st.markdown('<p style="color:#64748b;">Agents scan your watchlist once. You approve each trade.</p>', unsafe_allow_html=True)

    watchlist = db.get_watchlist()
    if not watchlist:
        st.info("Add tickers to your Watchlist first, then return here.")
    else:
        if st.button("Scan Watchlist Now", type="primary"):
            for ticker in watchlist:
                with st.expander(f"📊 {ticker}", expanded=True):
                    result   = run_full_analysis(ticker)
                    trader_r = result.get("trader_analysis", {})
                    risk_r   = result.get("risk_analysis", {})
                    action   = trader_r.get("action", "HOLD")
                    conf     = int(trader_r.get("confidence", 0) * 100)

                    st.markdown(
                        f'{badge_action(action)} &nbsp; '
                        f'<span style="color:#334155;">Confidence: <b>{conf}%</b> &nbsp;·&nbsp; '
                        f'Entry: <b>${trader_r.get("entry_price",0):,.2f}</b> &nbsp;·&nbsp; '
                        f'Stop: <b>${trader_r.get("stop_loss","?")}</b> &nbsp;·&nbsp; '
                        f'Target: <b>${trader_r.get("take_profit","?")}</b></span>',
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        f'<div style="font-size:13px;color:#334155;margin-top:8px;">'
                        f'{trader_r.get("reasoning","")}</div>',
                        unsafe_allow_html=True,
                    )
                    if action != "HOLD" and risk_r.get("approved"):
                        ca, cs = st.columns(2)
                        with ca:
                            if st.button(f"✅ Execute {action}", key=f"exec_{ticker}",
                                         type="primary", use_container_width=True):
                                order = execute_trade(ticker, trader_r)
                                st.success("Submitted!") if order.get("status") != "error" else st.error(order.get("error"))
                        with cs:
                            st.button("Skip", key=f"skip_{ticker}", use_container_width=True)
                    elif not risk_r.get("approved"):
                        st.warning(f"Risk Manager vetoed: {risk_r.get('veto_reason','')}")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: AUTONOMOUS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Autonomous":
    st.markdown("# Autonomous Mode")
    st.warning("⚠️ Autonomous mode executes real paper trades automatically. Verify risk controls before starting.")

    rc = st.session_state.risk_config
    c1, c2, c3 = st.columns(3)
    c1.metric("Max Position", f"{rc['max_position_pct']*100:.0f}%")
    c2.metric("Daily Loss Limit", f"{rc['daily_loss_limit']*100:.0f}%")
    c3.metric("Max Positions", rc["max_positions"])

    if not st.session_state.autonomous_running:
        if st.button("Start Autonomous Trading", type="primary"):
            st.session_state.autonomous_running = True
            st.rerun()
    else:
        if st.button("Stop", type="secondary"):
            st.session_state.autonomous_running = False
            st.rerun()

        scan_list     = db.get_watchlist() or SP50_TICKERS[:10]
        held_syms     = [p["symbol"] for p in portfolio.get_portfolio_summary().get("positions", [])]
        scan_list     = [t for t in scan_list if t not in held_syms]
        log_box       = st.empty()
        logs          = []

        for ticker in scan_list:
            daily_pnl = db.get_daily_pnl()
            acc_val   = portfolio.get_account().get("account_value", 100000)
            if acc_val and (-daily_pnl / acc_val) >= rc["daily_loss_limit"]:
                logs.append("🛑 Daily loss limit hit. Stopping."); break

            port_n = portfolio.get_portfolio_summary()
            if port_n.get("open_positions", 0) >= rc["max_positions"]:
                logs.append(f"⏸ Max positions ({rc['max_positions']}) reached. Skipping {ticker}."); continue

            logs.append(f"🔍 Analysing {ticker}…"); log_box.text("\n".join(logs[-20:]))
            try:
                result   = run_full_analysis(ticker)
                trader_r = result.get("trader_analysis", {})
                risk_r   = result.get("risk_analysis", {})
                action   = trader_r.get("action", "HOLD")
                if action != "HOLD" and risk_r.get("approved"):
                    order = execute_trade(ticker, trader_r)
                    logs.append(
                        f"✅ {ticker}: {action} submitted ({order.get('order_id','?')})"
                        if order.get("status") != "error"
                        else f"❌ {ticker}: {order.get('error')}"
                    )
                else:
                    logs.append(f"⏭ {ticker}: {action} — skipped")
            except Exception as e:
                logs.append(f"⚠️ {ticker}: {e}")
            log_box.text("\n".join(logs[-20:]))
            time.sleep(2)

        st.session_state.autonomous_running = False
        st.success("Autonomous scan complete.")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: WATCHLIST
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Watchlist":
    # ── Session state cache so add/delete never re-fetches all prices ─────────
    if "wl_list" not in st.session_state:
        st.session_state.wl_list   = db.get_watchlist()
    if "wl_prices" not in st.session_state:
        st.session_state.wl_prices = {}

    st.markdown("# Watchlist")

    ca, cb = st.columns([3, 1])
    with ca:
        new_t = st.text_input("Add ticker", placeholder="AAPL", key="wl_add").upper().strip()
    with cb:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Add", use_container_width=True) and new_t:
            if new_t not in st.session_state.wl_list:
                db.add_to_watchlist(new_t)
                st.session_state.wl_list.append(new_t)
            # No st.rerun() — Streamlit's natural rerun after the button click
            # handles the UI update; price cache avoids re-fetching existing tickers

    watchlist = st.session_state.wl_list
    if not watchlist:
        st.info("Your watchlist is empty. Add tickers above.")
    else:
        if st.button("🔄 Refresh Prices"):
            st.session_state.wl_prices = {}   # bust cache, next loop re-fetches all

        # Only fetch prices for tickers not already in the cache
        for t in watchlist:
            if t not in st.session_state.wl_prices:
                p    = fetcher.get_current_price(t)
                tech = fetcher.get_technicals(t)
                st.session_state.wl_prices[t] = {
                    "Price":    p,
                    "1D%":      tech.get("ret_1d"),
                    "5D%":      tech.get("ret_5d"),
                    "RSI":      tech.get("rsi"),
                    "vs SMA50":  tech.get("pct_vs_sma50"),
                    "vs SMA200": tech.get("pct_vs_sma200"),
                }

        rows = [{"Ticker": t, **st.session_state.wl_prices.get(t, {})} for t in watchlist]

        def _pc(v):
            v = v or 0
            c = "#15803d" if v >= 0 else "#b91c1c"
            return f'<td style="color:{c};font-weight:600;">{v:+.2f}%</td>'

        trows = ""
        for r in rows:
            rsi   = r.get("RSI") or 0
            rsi_c = "#b91c1c" if rsi > 70 else "#15803d" if rsi < 30 else "#334155"
            trows += (
                f'<tr><td><b style="color:#0f172a;">{r["Ticker"]}</b></td>'
                f'<td style="color:#0f172a;">${(r.get("Price") or 0):,.2f}</td>'
                + _pc(r.get("1D%")) + _pc(r.get("5D%"))
                + f'<td style="color:{rsi_c};font-weight:600;">{rsi:.1f}</td>'
                + _pc(r.get("vs SMA50")) + _pc(r.get("vs SMA200"))
                + f'<td></td></tr>'
            )

        st.markdown(
            f'<div class="card" style="padding:0;overflow:hidden;">'
            f'<table class="stbl"><thead><tr>'
            f'<th>Ticker</th><th>Price</th><th>1D%</th><th>5D%</th>'
            f'<th>RSI</th><th>vs SMA50</th><th>vs SMA200</th><th></th>'
            f'</tr></thead><tbody>{trows}</tbody></table></div>',
            unsafe_allow_html=True,
        )
        st.markdown("**Remove:**")
        cols = st.columns(min(len(watchlist), 6))
        for i, t in enumerate(watchlist[:]):   # slice copy so loop isn't affected by deletion
            with cols[i % len(cols)]:
                if st.button(f"✕ {t}", key=f"rm_{t}"):
                    db.remove_from_watchlist(t)
                    st.session_state.wl_list   = [x for x in st.session_state.wl_list if x != t]
                    st.session_state.wl_prices.pop(t, None)
                    # No st.rerun() — natural rerun is fast because prices are cached


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: TRADE JOURNAL
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Trade Journal":
    st.markdown("# Trade Journal")
    tab_t, tab_d = st.tabs(["Trades", "Decision Log"])

    with tab_t:
        trades = db.get_trades(100)
        if not trades:
            st.info("No trades logged yet.")
        else:
            df_t = pd.DataFrame(trades)
            cols = ["ticker","action","quantity","entry_price","stop_loss","take_profit","status","pnl","created_at"]
            cols = [c for c in cols if c in df_t.columns]
            df_s = df_t[cols].copy()
            df_s.columns = [c.replace("_"," ").title() for c in cols]

            def _style_pnl(val):
                if pd.isna(val): return ""
                return f"color:{'#15803d' if val>=0 else '#b91c1c'};font-weight:600"

            st.dataframe(
                df_s.style.applymap(_style_pnl, subset=["Pnl"] if "Pnl" in df_s.columns else []),
                use_container_width=True, height=400,
            )

            closed = [t for t in trades if t.get("pnl") is not None]
            if closed:
                dfc = pd.DataFrame(closed)[["created_at","pnl","ticker"]].copy()
                dfc["created_at"] = pd.to_datetime(dfc["created_at"])
                dfc = dfc.sort_values("created_at")
                dfc["cum_pnl"] = dfc["pnl"].cumsum()
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=dfc["created_at"], y=dfc["cum_pnl"],
                    mode="lines+markers", name="Cumulative P&L",
                    line=dict(color="#2563eb", width=2),
                    fill="tozeroy", fillcolor="rgba(37,99,235,.08)",
                ))
                fig.update_layout(
                    title="Cumulative P&L", height=300,
                    paper_bgcolor="white", plot_bgcolor="white",
                    xaxis=dict(gridcolor="#f1f5f9", color="#334155"),
                    yaxis=dict(gridcolor="#f1f5f9", color="#334155", tickprefix="$"),
                    font=dict(color="#334155"),
                    margin=dict(l=10,r=10,t=40,b=10),
                )
                st.plotly_chart(fig, use_container_width=True)

    with tab_d:
        tf = st.text_input("Filter by ticker", placeholder="Leave blank for all").upper().strip()
        decisions = db.get_decisions(ticker=tf or None, limit=300)
        if not decisions:
            st.info("No decisions logged yet.")
        else:
            dfd = pd.DataFrame(decisions)
            cd  = ["ticker","agent_name","signal","confidence","reasoning","created_at"]
            cd  = [c for c in cd if c in dfd.columns]
            dfs = dfd[cd].copy()
            dfs.columns = [c.replace("_"," ").title() for c in cd]
            st.dataframe(dfs, use_container_width=True, height=500)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: SETTINGS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Settings":
    st.markdown("# Settings")
    with st.form("risk_form"):
        st.markdown("### Risk Controls")
        rc = st.session_state.risk_config
        c1, c2 = st.columns(2)
        with c1:
            max_pos     = st.slider("Max Position Size (%)", 1, 20, int(rc["max_position_pct"]*100))
            daily_loss  = st.slider("Daily Loss Limit (%)",  1, 10, int(rc["daily_loss_limit"]*100))
            max_pos_n   = st.slider("Max Concurrent Positions", 1, 30, rc["max_positions"])
        with c2:
            cooldown    = st.slider("Cooldown per Ticker (min)", 5, 480, rc["cooldown_minutes"], step=5)
            stop_l      = st.slider("Default Stop Loss (%)",    1, 10, int(rc["stop_loss_pct"]*100))
            take_p      = st.slider("Default Take Profit (%)",  1, 20, int(rc["take_profit_pct"]*100))
        if st.form_submit_button("Save", type="primary"):
            st.session_state.risk_config = {
                "max_position_pct": max_pos/100, "daily_loss_limit": daily_loss/100,
                "max_positions": max_pos_n, "cooldown_minutes": cooldown,
                "stop_loss_pct": stop_l/100, "take_profit_pct": take_p/100,
            }
            st.success("Settings saved!")

    st.markdown("### API Status")
    from config import FINNHUB_API_KEY, NEWS_API_KEY
    checks = {
        "Anthropic":  bool(ANTHROPIC_API_KEY),
        "Finnhub":    bool(FINNHUB_API_KEY),
        "Polygon.io": bool(POLYGON_API_KEY),
        "Alpaca":     portfolio.connected,
        "NewsAPI":    bool(NEWS_API_KEY),
    }
    cols = st.columns(len(checks))
    for i, (name, ok) in enumerate(checks.items()):
        with cols[i]:
            st.markdown(
                f'<div class="card" style="text-align:center;padding:16px;">'
                f'<div class="card-title">{name}</div>'
                f'<div style="font-size:26px;">{"✅" if ok else "❌"}</div>'
                f'</div>', unsafe_allow_html=True)

    st.markdown(
        '<div class="card">'
        '<div class="card-title">AI Trading Agents v2.0</div>'
        '<p style="color:#334155;font-size:13px;line-height:1.6;">'
        '<b>Screener:</b> Haiku-only (6 agents) — cost-efficient one-shot scan.<br>'
        '<b>Full Analysis:</b> All 9 agents including Opus — triggered manually per ticker.<br>'
        '<b>Technical data:</b> Polygon.io (primary) → yfinance fallback.<br>'
        '<b>News:</b> Finnhub live headlines fed directly to Sentiment Agent.'
        '</p></div>',
        unsafe_allow_html=True,
    )
