import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import time
import json

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Trading Agents",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  /* Base */
  .stApp { background: #f0f2f6; }
  section[data-testid="stSidebar"] { background: #1a1f2e; }
  section[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
  section[data-testid="stSidebar"] .stRadio label { color: #e2e8f0 !important; }

  /* White cards */
  .card {
    background: white;
    border-radius: 12px;
    padding: 20px 24px;
    box-shadow: 0 1px 3px rgba(0,0,0,.08), 0 1px 2px rgba(0,0,0,.05);
    margin-bottom: 16px;
  }
  .card-title {
    font-size: 13px;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: .05em;
    margin-bottom: 8px;
  }
  .card-value {
    font-size: 28px;
    font-weight: 700;
    color: #1e293b;
  }

  /* Badges */
  .badge-long   { background:#dcfce7; color:#166534; border-radius:6px; padding:3px 10px; font-size:12px; font-weight:700; }
  .badge-short  { background:#fee2e2; color:#991b1b; border-radius:6px; padding:3px 10px; font-size:12px; font-weight:700; }
  .badge-hold   { background:#fef9c3; color:#854d0e; border-radius:6px; padding:3px 10px; font-size:12px; font-weight:700; }
  .badge-bull   { background:#dcfce7; color:#166534; border-radius:6px; padding:3px 10px; font-size:12px; font-weight:600; }
  .badge-bear   { background:#fee2e2; color:#991b1b; border-radius:6px; padding:3px 10px; font-size:12px; font-weight:600; }
  .badge-neutral{ background:#f1f5f9; color:#475569; border-radius:6px; padding:3px 10px; font-size:12px; font-weight:600; }

  /* Agent cards */
  .agent-card {
    background: white;
    border-radius: 10px;
    padding: 14px 18px;
    box-shadow: 0 1px 3px rgba(0,0,0,.06);
    margin-bottom: 10px;
    border-left: 4px solid #e2e8f0;
  }
  .agent-bull { border-left-color: #22c55e !important; }
  .agent-bear { border-left-color: #ef4444 !important; }
  .agent-neutral { border-left-color: #94a3b8 !important; }
  .agent-name { font-size:13px; font-weight:700; color:#1e293b; }
  .agent-signal { font-size:12px; color:#64748b; margin-top:2px; }
  .agent-reasoning { font-size:12px; color:#475569; margin-top:6px; line-height:1.5; }

  /* Divider */
  hr.card-divider { border: none; border-top: 1px solid #f1f5f9; margin: 12px 0; }

  /* Metric row */
  .metric-row { display:flex; gap:16px; flex-wrap:wrap; margin-bottom:16px; }
  .metric-item { flex:1; min-width:120px; background:white; border-radius:10px;
                 padding:14px 16px; box-shadow:0 1px 3px rgba(0,0,0,.06); }
  .metric-label { font-size:11px; color:#94a3b8; font-weight:600; text-transform:uppercase; }
  .metric-val   { font-size:22px; font-weight:700; color:#1e293b; }
  .metric-sub   { font-size:11px; color:#64748b; margin-top:2px; }

  /* Table */
  .screener-table { width:100%; border-collapse:collapse; }
  .screener-table th { background:#f8fafc; color:#64748b; font-size:12px; font-weight:600;
                       text-transform:uppercase; padding:10px 14px; text-align:left; }
  .screener-table td { padding:10px 14px; font-size:13px; border-bottom:1px solid #f1f5f9; }
  .screener-table tr:hover td { background:#fafafa; }

  /* Trade ticket */
  .trade-ticket {
    background: white; border-radius:12px; padding:24px;
    box-shadow: 0 4px 12px rgba(0,0,0,.1); border:2px solid #e2e8f0;
  }
</style>
""", unsafe_allow_html=True)

# ── Initialise ────────────────────────────────────────────────────────────────
import database as db
db.init_db()

from config import (
    SP50_TICKERS, SECTOR_ETFS, DEFAULT_MAX_POSITION_PCT,
    DEFAULT_DAILY_LOSS_LIMIT, DEFAULT_MAX_POSITIONS,
    DEFAULT_COOLDOWN_MINUTES, DEFAULT_STOP_LOSS_PCT, DEFAULT_TAKE_PROFIT_PCT,
    ANTHROPIC_API_KEY,
)
from utils.data_fetcher import DataFetcher
from utils.portfolio import PortfolioManager
from agents import (
    MacroAgent, FundamentalAgent, TechnicalAgent, SentimentAgent,
    BullResearcher, BearResearcher, RiskManager, HeadTrader, HedgeAgent,
)

fetcher   = DataFetcher()
portfolio = PortfolioManager()

# Session defaults
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
_sdef("screener_results", [])
_sdef("analysis_result", None)
_sdef("autonomous_running", False)

# ── Helpers ───────────────────────────────────────────────────────────────────

def signal_badge(signal: str) -> str:
    s = (signal or "").upper()
    if s in ("BULLISH", "LONG"):
        return '<span class="badge-bull">BULLISH</span>'
    if s in ("BEARISH", "SHORT"):
        return '<span class="badge-bear">BEARISH</span>'
    return '<span class="badge-neutral">NEUTRAL</span>'


def action_badge(action: str) -> str:
    a = (action or "").upper()
    if a == "LONG":  return '<span class="badge-long">LONG</span>'
    if a == "SHORT": return '<span class="badge-short">SHORT</span>'
    return '<span class="badge-hold">HOLD</span>'


def conf_bar(confidence) -> str:
    pct = int((confidence or 0) * 100)
    color = "#22c55e" if pct >= 65 else "#f59e0b" if pct >= 45 else "#ef4444"
    return (
        f'<div style="background:#f1f5f9;border-radius:4px;height:6px;margin-top:4px;">'
        f'<div style="width:{pct}%;background:{color};height:6px;border-radius:4px;"></div></div>'
        f'<span style="font-size:11px;color:#64748b;">{pct}% confidence</span>'
    )


def run_full_analysis(ticker: str) -> dict:
    """Run the complete 9-agent pipeline for a ticker."""
    rc = st.session_state.risk_config

    with st.spinner(f"Fetching data for {ticker}..."):
        data = fetcher.get_full_data(ticker)

    port_summary = portfolio.get_portfolio_summary()
    port_summary["existing_exposure_pct"] = portfolio.get_ticker_exposure(ticker, port_summary)
    daily_pnl = db.get_daily_pnl()
    acc_val   = port_summary.get("account_value", 100000)
    port_summary["daily_pnl_pct"] = daily_pnl / acc_val * 100 if acc_val else 0

    cooldown_elapsed = db.get_cooldown_minutes(ticker)
    cooldown_remaining = None
    if cooldown_elapsed is not None and cooldown_elapsed < rc["cooldown_minutes"]:
        cooldown_remaining = rc["cooldown_minutes"] - cooldown_elapsed

    data["portfolio"]          = port_summary
    data["risk_config"]        = rc
    data["cooldown_remaining"] = cooldown_remaining

    agents_run = []

    with st.spinner("Macro Agent analysing market environment..."):
        macro_r = MacroAgent().analyze(data)
        data["macro_analysis"] = macro_r
        agents_run.append(macro_r)
        db.log_decision(ticker, "Macro Agent", macro_r.get("signal"),
                        macro_r.get("confidence"), macro_r.get("reasoning"), macro_r)

    with st.spinner("Fundamental Agent evaluating financials..."):
        fund_r = FundamentalAgent().analyze(data)
        data["fundamental_analysis"] = fund_r
        agents_run.append(fund_r)
        db.log_decision(ticker, "Fundamental Agent", fund_r.get("signal"),
                        fund_r.get("confidence"), fund_r.get("reasoning"), fund_r)

    with st.spinner("Technical Agent reading the charts..."):
        tech_r = TechnicalAgent().analyze(data)
        data["technical_analysis"] = tech_r
        agents_run.append(tech_r)
        db.log_decision(ticker, "Technical Agent", tech_r.get("signal"),
                        tech_r.get("confidence"), tech_r.get("reasoning"), tech_r)

    with st.spinner("Sentiment Agent scanning news..."):
        sent_r = SentimentAgent().analyze(data)
        data["sentiment_analysis"] = sent_r
        agents_run.append(sent_r)
        db.log_decision(ticker, "Sentiment Agent", sent_r.get("signal"),
                        sent_r.get("confidence"), sent_r.get("reasoning"), sent_r)

    with st.spinner("Bull Researcher building long case..."):
        bull_r = BullResearcher().analyze(data)
        data["bull_analysis"] = bull_r
        agents_run.append(bull_r)
        db.log_decision(ticker, "Bull Researcher", "BULLISH",
                        bull_r.get("confidence"), bull_r.get("bull_thesis"), bull_r)

    with st.spinner("Bear Researcher building short case..."):
        bear_r = BearResearcher().analyze(data)
        data["bear_analysis"] = bear_r
        agents_run.append(bear_r)
        db.log_decision(ticker, "Bear Researcher", "BEARISH",
                        bear_r.get("confidence"), bear_r.get("bear_thesis"), bear_r)

    with st.spinner("Risk Manager evaluating position risk (Opus)..."):
        risk_r = RiskManager().analyze(data)
        data["risk_analysis"] = risk_r
        agents_run.append(risk_r)
        db.log_decision(ticker, "Risk Manager",
                        "APPROVED" if risk_r.get("approved") else "VETOED",
                        risk_r.get("risk_score"), risk_r.get("reasoning"), risk_r)

    with st.spinner("Head Trader making final decision (Opus)..."):
        trader_r = HeadTrader().analyze(data)
        data["trader_analysis"] = trader_r
        agents_run.append(trader_r)
        db.log_decision(ticker, "Head Trader", trader_r.get("action"),
                        trader_r.get("confidence"), trader_r.get("reasoning"), trader_r)

    with st.spinner("Hedge Agent checking portfolio balance (Opus)..."):
        hedge_r = HedgeAgent().analyze(data)
        data["hedge_analysis"] = hedge_r
        agents_run.append(hedge_r)
        db.log_decision(ticker, "Hedge Agent",
                        "HEDGE" if hedge_r.get("hedge_needed") else "BALANCED",
                        None, hedge_r.get("reasoning"), hedge_r)

    data["agents_run"] = agents_run
    return data


def execute_trade(ticker: str, trader_result: dict) -> dict:
    action     = trader_result.get("action", "HOLD")
    entry      = trader_result.get("entry_price", 0)
    stop       = trader_result.get("stop_loss")
    target     = trader_result.get("take_profit")
    qty        = int(trader_result.get("quantity", 1))

    if action == "HOLD" or not stop or not target or qty <= 0:
        return {"status": "skipped", "reason": "HOLD or missing parameters"}

    order = portfolio.submit_bracket_order(ticker, action, qty, stop, target)
    db.log_trade(ticker, action, qty, entry, stop, target,
                 status=order.get("status", "error"),
                 alpaca_order_id=order.get("order_id"),
                 notes=trader_result.get("reasoning", "")[:500])
    if order.get("status") not in ("error",):
        db.set_cooldown(ticker)
    return order


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📈 AI Trading Agents")
    st.markdown("---")

    page = st.radio(
        "Navigation",
        ["Manual Analysis", "Screener", "Semi-Auto", "Autonomous",
         "Watchlist", "Trade Journal", "Settings"],
        label_visibility="collapsed",
    )

    st.markdown("---")
    acc = portfolio.get_account()
    connected = acc.get("connected", False)
    status_dot = "🟢" if connected else "🔴"
    st.markdown(f"{status_dot} Alpaca {'Connected' if connected else 'Not Connected'}")
    if connected:
        st.markdown(f"**Portfolio:** ${acc.get('account_value',0):,.0f}")
        st.markdown(f"**Buying Power:** ${acc.get('buying_power',0):,.0f}")

    if not ANTHROPIC_API_KEY:
        st.warning("⚠️ No ANTHROPIC_API_KEY found in .env")

    st.markdown("---")
    daily_pnl = db.get_daily_pnl()
    pnl_color = "green" if daily_pnl >= 0 else "red"
    st.markdown(f"**Today's P&L:** :{pnl_color}[${daily_pnl:+,.2f}]")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: MANUAL ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════
if page == "Manual Analysis":
    st.markdown("# Manual Analysis")
    st.markdown('<p style="color:#64748b;">Run all 9 agents on a ticker and get a trade recommendation.</p>', unsafe_allow_html=True)

    col1, col2 = st.columns([3, 1])
    with col1:
        ticker_input = st.text_input("Ticker Symbol", placeholder="e.g. AAPL, MSFT, NVDA",
                                      key="manual_ticker").upper().strip()
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        run_btn = st.button("Run Analysis", type="primary", use_container_width=True)

    if run_btn and ticker_input:
        result = run_full_analysis(ticker_input)
        st.session_state.analysis_result = result

    result = st.session_state.get("analysis_result")
    if result:
        ticker   = result.get("ticker", "")
        price    = result.get("current_price", 0)
        trader_r = result.get("trader_analysis", {})
        risk_r   = result.get("risk_analysis", {})
        hedge_r  = result.get("hedge_analysis", {})
        action   = trader_r.get("action", "HOLD")

        # ── Header card ──
        col_a, col_b, col_c, col_d, col_e = st.columns(5)
        with col_a:
            st.markdown(f'<div class="card"><div class="card-title">Ticker</div>'
                        f'<div class="card-value">{ticker}</div></div>', unsafe_allow_html=True)
        with col_b:
            st.markdown(f'<div class="card"><div class="card-title">Price</div>'
                        f'<div class="card-value">${price:,.2f}</div></div>', unsafe_allow_html=True)
        with col_c:
            st.markdown(f'<div class="card"><div class="card-title">Decision</div>'
                        f'<div class="card-value">{action_badge(action)}</div></div>',
                        unsafe_allow_html=True)
        with col_d:
            conf = trader_r.get("confidence", 0)
            st.markdown(f'<div class="card"><div class="card-title">Confidence</div>'
                        f'<div class="card-value">{int(conf*100)}%</div></div>',
                        unsafe_allow_html=True)
        with col_e:
            risk_approved = risk_r.get("approved", False)
            risk_txt = "✅ Approved" if risk_approved else "❌ Vetoed"
            st.markdown(f'<div class="card"><div class="card-title">Risk Manager</div>'
                        f'<div class="card-value" style="font-size:20px;">{risk_txt}</div></div>',
                        unsafe_allow_html=True)

        # ── Agent signal grid ──
        st.markdown("### Agent Signals")
        cols = st.columns(4)
        for i, key in enumerate(["macro_analysis","fundamental_analysis",
                                  "technical_analysis","sentiment_analysis"]):
            r = result.get(key, {})
            sig = r.get("signal", "NEUTRAL")
            cls = "agent-bull" if "BULL" in sig else "agent-bear" if "BEAR" in sig else "agent-neutral"
            with cols[i]:
                st.markdown(
                    f'<div class="agent-card {cls}">'
                    f'<div class="agent-name">{r.get("agent","")}</div>'
                    f'<div class="agent-signal">{signal_badge(sig)}</div>'
                    f'{conf_bar(r.get("confidence",0))}'
                    f'<hr class="card-divider">'
                    f'<div class="agent-reasoning">{(r.get("reasoning","") or "")[:200]}</div>'
                    f'</div>', unsafe_allow_html=True)

        # ── Bull vs Bear ──
        st.markdown("### Bull vs Bear Debate")
        col_bull, col_bear = st.columns(2)
        bull_r = result.get("bull_analysis", {})
        bear_r = result.get("bear_analysis", {})
        with col_bull:
            st.markdown(
                f'<div class="agent-card agent-bull">'
                f'<div class="agent-name">🐂 Bull Researcher</div>'
                f'{conf_bar(bull_r.get("confidence",0))}'
                f'<hr class="card-divider">'
                f'<div class="agent-reasoning"><b>Thesis:</b> {bull_r.get("bull_thesis","")}</div>'
                f'<div class="agent-reasoning" style="margin-top:8px;"><b>Target:</b> '
                f'${bull_r.get("upside_target","?")}</div>'
                f'<div class="agent-reasoning"><b>Catalysts:</b><ul>'
                + "".join(f'<li>{c}</li>' for c in (bull_r.get("key_catalysts") or [])[:3])
                + f'</ul></div></div>', unsafe_allow_html=True)
        with col_bear:
            st.markdown(
                f'<div class="agent-card agent-bear">'
                f'<div class="agent-name">🐻 Bear Researcher</div>'
                f'{conf_bar(bear_r.get("confidence",0))}'
                f'<hr class="card-divider">'
                f'<div class="agent-reasoning"><b>Thesis:</b> {bear_r.get("bear_thesis","")}</div>'
                f'<div class="agent-reasoning" style="margin-top:8px;"><b>Target:</b> '
                f'${bear_r.get("downside_target","?")}</div>'
                f'<div class="agent-reasoning"><b>Risks:</b><ul>'
                + "".join(f'<li>{c}</li>' for c in (bear_r.get("key_risks") or [])[:3])
                + f'</ul></div></div>', unsafe_allow_html=True)

        # ── Trade ticket ──
        st.markdown("### Trade Ticket")
        stop   = trader_r.get("stop_loss")
        target = trader_r.get("take_profit")
        qty    = trader_r.get("quantity", 0)

        col_t1, col_t2 = st.columns([2, 1])
        with col_t1:
            st.markdown(
                f'<div class="trade-ticket">'
                f'<div style="font-size:18px;font-weight:700;margin-bottom:16px;">'
                f'{action_badge(action)} {ticker} — {trader_r.get("time_horizon","?")}</div>'
                f'<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;">'
                f'<div><div class="metric-label">Entry</div>'
                f'<div style="font-size:20px;font-weight:700;">${trader_r.get("entry_price",price):,.2f}</div></div>'
                f'<div><div class="metric-label">Stop Loss</div>'
                f'<div style="font-size:20px;font-weight:700;color:#ef4444;">${stop or "N/A":}</div></div>'
                f'<div><div class="metric-label">Take Profit</div>'
                f'<div style="font-size:20px;font-weight:700;color:#22c55e;">${target or "N/A":}</div></div>'
                f'</div>'
                f'<div style="margin-top:16px;font-size:13px;color:#64748b;">'
                f'<b>Quantity:</b> {qty} shares &nbsp;|&nbsp; '
                f'<b>R:R:</b> {risk_r.get("risk_reward_ratio","?")}&nbsp;|&nbsp;'
                f'<b>Max Loss:</b> ${risk_r.get("max_loss_dollars","?")}'
                f'</div>'
                f'<div style="margin-top:12px;font-size:13px;color:#475569;">'
                f'{trader_r.get("reasoning","")[:400]}'
                f'</div></div>',
                unsafe_allow_html=True,
            )
        with col_t2:
            if action != "HOLD" and risk_r.get("approved"):
                if st.button(f"Execute {action} Trade", type="primary", use_container_width=True):
                    with st.spinner("Submitting order..."):
                        order = execute_trade(ticker, trader_r)
                    if order.get("status") == "error":
                        st.error(f"Order failed: {order.get('error')}")
                    else:
                        st.success(f"Order submitted! ID: {order.get('order_id','?')}")
            elif not risk_r.get("approved"):
                st.error(f"Vetoed: {risk_r.get('veto_reason','Risk controls')}")
            else:
                st.info("No trade recommended (HOLD)")

            if action != "HOLD":
                if st.button("Add to Watchlist", use_container_width=True):
                    db.add_to_watchlist(ticker)
                    st.success(f"{ticker} added to watchlist")

        # ── Hedge Recommendations ──
        if hedge_r.get("hedge_needed"):
            st.markdown("### Hedge Agent Alert")
            recs = hedge_r.get("recommendations", [])
            rec_html = "".join(
                f'<div style="padding:8px 0;border-bottom:1px solid #f1f5f9;">'
                f'{action_badge(r.get("action","?"))} <b>{r.get("instrument","?")}</b> '
                f'({r.get("allocation_pct","?"):.1f}% allocation) — {r.get("rationale","")}'
                f'</div>'
                for r in recs
            )
            urgency = hedge_r.get("urgency", "LOW")
            urgency_color = {"HIGH": "#ef4444", "MEDIUM": "#f59e0b", "LOW": "#22c55e"}.get(urgency, "#64748b")
            st.markdown(
                f'<div class="card" style="border-left:4px solid {urgency_color};">'
                f'<div class="card-title">Portfolio Hedge Needed — Urgency: '
                f'<span style="color:{urgency_color};">{urgency}</span></div>'
                f'<div style="font-size:13px;color:#475569;margin-bottom:12px;">'
                f'{hedge_r.get("reasoning","")}</div>'
                f'{rec_html}</div>',
                unsafe_allow_html=True,
            )

        # ── Price chart ──
        st.markdown("### Price Chart")
        df = fetcher.get_price_history(ticker, "6mo")
        if not df.empty:
            tech = result.get("technicals", {})
            fig = go.Figure()
            fig.add_trace(go.Candlestick(
                x=df.index, open=df["Open"], high=df["High"],
                low=df["Low"], close=df["Close"], name="Price",
            ))
            for label, col_key, color in [
                ("SMA 50", "sma_50", "#3b82f6"),
                ("SMA 200", "sma_200", "#f59e0b"),
            ]:
                if tech.get(col_key):
                    fig.add_hline(y=tech[col_key], line_dash="dash",
                                  line_color=color,
                                  annotation_text=label, annotation_position="right")
            if tech.get("bb_upper"):
                fig.add_hline(y=tech["bb_upper"], line_dash="dot", line_color="#94a3b8",
                              annotation_text="BB Upper")
            if tech.get("bb_lower"):
                fig.add_hline(y=tech["bb_lower"], line_dash="dot", line_color="#94a3b8",
                              annotation_text="BB Lower")
            if stop:
                fig.add_hline(y=stop, line_color="#ef4444", line_dash="solid",
                              annotation_text=f"Stop ${stop:.2f}", annotation_position="right")
            if target:
                fig.add_hline(y=target, line_color="#22c55e", line_dash="solid",
                              annotation_text=f"Target ${target:.2f}", annotation_position="right")

            fig.update_layout(
                height=450, paper_bgcolor="white", plot_bgcolor="white",
                xaxis_rangeslider_visible=False,
                margin=dict(l=10, r=60, t=20, b=10),
                xaxis=dict(gridcolor="#f1f5f9"),
                yaxis=dict(gridcolor="#f1f5f9"),
            )
            st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: SCREENER
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Screener":
    st.markdown("# S&P 50 Screener")
    st.markdown('<p style="color:#64748b;">Scan top S&P 500 stocks with all 9 agents for LONG/SHORT signals.</p>',
                unsafe_allow_html=True)

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        custom = st.text_input("Custom tickers (comma-separated, or leave blank for S&P 50)",
                               placeholder="AAPL, MSFT, NVDA ...")
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        run_screen = st.button("Run Screener", type="primary", use_container_width=True)
    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        filter_opt = st.selectbox("Filter", ["All", "LONG Only", "SHORT Only"])

    if run_screen:
        tickers = [t.strip().upper() for t in custom.split(",")] if custom.strip() else SP50_TICKERS
        st.session_state.screener_results = []

        progress_bar = st.progress(0)
        status_text  = st.empty()

        def progress_cb(i, total, ticker):
            progress_bar.progress((i + 1) / total)
            status_text.markdown(f"Analysing **{ticker}** ({i+1}/{total})...")

        from utils.screener import Screener
        screener = Screener(progress_callback=progress_cb)
        results  = screener.run(tickers)
        st.session_state.screener_results = results
        status_text.empty()
        progress_bar.empty()

    results = st.session_state.get("screener_results", [])
    if results:
        if filter_opt == "LONG Only":
            results = [r for r in results if r.get("action") == "LONG"]
        elif filter_opt == "SHORT Only":
            results = [r for r in results if r.get("action") == "SHORT"]

        longs  = len([r for r in results if r.get("action") == "LONG"])
        shorts = len([r for r in results if r.get("action") == "SHORT"])
        holds  = len([r for r in results if r.get("action") == "HOLD"])

        c1, c2, c3, c4 = st.columns(4)
        for col, label, val, color in [
            (c1, "Total Scanned", len(results), "#1e293b"),
            (c2, "LONG Signals",  longs,  "#166534"),
            (c3, "SHORT Signals", shorts, "#991b1b"),
            (c4, "HOLD",          holds,  "#854d0e"),
        ]:
            with col:
                st.markdown(
                    f'<div class="card">'
                    f'<div class="card-title">{label}</div>'
                    f'<div class="card-value" style="color:{color};">{val}</div>'
                    f'</div>', unsafe_allow_html=True)

        # Table
        rows_html = ""
        for r in results:
            action = r.get("action", "HOLD")
            score  = r.get("composite_score", 0)
            bar_w  = int(abs(score) * 100)
            bar_c  = "#22c55e" if score > 0 else "#ef4444"
            rows_html += (
                f'<tr>'
                f'<td><b>{r.get("ticker","")}</b></td>'
                f'<td>${r.get("price",0):,.2f}</td>'
                f'<td>{action_badge(action)}</td>'
                f'<td><div style="display:flex;align-items:center;gap:8px;">'
                f'<div style="background:#f1f5f9;border-radius:4px;width:80px;height:8px;">'
                f'<div style="width:{bar_w}%;background:{bar_c};height:8px;border-radius:4px;"></div></div>'
                f'<span style="font-size:12px;color:#64748b;">{score:+.2f}</span>'
                f'</div></td>'
                f'<td>{signal_badge(r.get("macro_signal","?"))}</td>'
                f'<td>{signal_badge(r.get("fund_signal","?"))}</td>'
                f'<td>{signal_badge(r.get("tech_signal","?"))}</td>'
                f'<td>{signal_badge(r.get("sent_signal","?"))}</td>'
                f'<td style="color:#64748b;">{r.get("tech_trend","?")}</td>'
                f'<td style="color:#64748b;">{r.get("rsi","?")}</td>'
                f'</tr>'
            )

        st.markdown(
            f'<div class="card" style="padding:0;overflow:hidden;">'
            f'<table class="screener-table">'
            f'<thead><tr>'
            f'<th>Ticker</th><th>Price</th><th>Signal</th><th>Score</th>'
            f'<th>Macro</th><th>Fund</th><th>Tech</th><th>Sent</th>'
            f'<th>Trend</th><th>RSI</th>'
            f'</tr></thead>'
            f'<tbody>{rows_html}</tbody>'
            f'</table></div>',
            unsafe_allow_html=True,
        )

        # Sector Rotation
        st.markdown("### Sector Rotation")
        with st.spinner("Loading sector performance..."):
            sector_data = fetcher.get_sector_performance()

        if sector_data:
            df_sector = pd.DataFrame([
                {"Sector": s, "ETF": v.get("etf",""), "1D%": v.get("ret_1d"),
                 "5D%": v.get("ret_5d"), "1M%": v.get("ret_1m")}
                for s, v in sector_data.items()
            ]).sort_values("1M%", ascending=False)

            fig = px.bar(
                df_sector.dropna(subset=["1M%"]),
                x="Sector", y="1M%", color="1M%",
                color_continuous_scale=["#ef4444", "#f8fafc", "#22c55e"],
                color_continuous_midpoint=0,
                title="Sector 1-Month Performance (%)",
            )
            fig.update_layout(
                height=350, paper_bgcolor="white", plot_bgcolor="white",
                coloraxis_showscale=False,
                margin=dict(l=10, r=10, t=40, b=80),
                xaxis=dict(tickangle=-30),
            )
            st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: SEMI-AUTO
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Semi-Auto":
    st.markdown("# Semi-Auto Trading")
    st.markdown('<p style="color:#64748b;">Agents find opportunities — you approve each trade.</p>',
                unsafe_allow_html=True)

    watchlist = db.get_watchlist()
    if not watchlist:
        st.info("Add tickers to your Watchlist first, then come back here.")
    else:
        if st.button("Scan Watchlist Now", type="primary"):
            for ticker in watchlist:
                with st.expander(f"📊 {ticker}", expanded=True):
                    result = run_full_analysis(ticker)
                    trader_r = result.get("trader_analysis", {})
                    risk_r   = result.get("risk_analysis", {})
                    action   = trader_r.get("action", "HOLD")

                    st.markdown(
                        f'{action_badge(action)} &nbsp;'
                        f'Confidence: {int(trader_r.get("confidence",0)*100)}% &nbsp;|&nbsp;'
                        f'Entry: ${trader_r.get("entry_price",0):,.2f} &nbsp;|&nbsp;'
                        f'Stop: ${trader_r.get("stop_loss","?")} &nbsp;|&nbsp;'
                        f'Target: ${trader_r.get("take_profit","?")}',
                        unsafe_allow_html=True,
                    )
                    st.write(trader_r.get("reasoning", ""))

                    if action != "HOLD" and risk_r.get("approved"):
                        col_approve, col_skip = st.columns(2)
                        with col_approve:
                            if st.button(f"✅ Execute {action}", key=f"exec_{ticker}",
                                         type="primary", use_container_width=True):
                                order = execute_trade(ticker, trader_r)
                                if order.get("status") == "error":
                                    st.error(order.get("error"))
                                else:
                                    st.success("Trade submitted!")
                        with col_skip:
                            st.button("Skip", key=f"skip_{ticker}", use_container_width=True)
                    elif not risk_r.get("approved"):
                        st.warning(f"Risk Manager vetoed: {risk_r.get('veto_reason','')}")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: AUTONOMOUS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Autonomous":
    st.markdown("# Autonomous Mode")
    st.warning("⚠️ Autonomous mode will execute real paper trades automatically. Ensure risk controls are properly set.")

    rc = st.session_state.risk_config
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Max Position", f"{rc['max_position_pct']*100:.0f}%")
    with col2:
        st.metric("Daily Loss Limit", f"{rc['daily_loss_limit']*100:.0f}%")
    with col3:
        st.metric("Max Positions", rc["max_positions"])

    running = st.session_state.get("autonomous_running", False)
    if not running:
        if st.button("Start Autonomous Trading", type="primary"):
            st.session_state.autonomous_running = True
            st.rerun()
    else:
        if st.button("Stop Autonomous Trading", type="secondary"):
            st.session_state.autonomous_running = False
            st.rerun()

        watchlist = db.get_watchlist() or SP50_TICKERS[:10]
        log_container = st.empty()
        logs = []

        for ticker in watchlist:
            # Check daily loss limit
            daily_pnl = db.get_daily_pnl()
            acc_val   = portfolio.get_account().get("account_value", 100000)
            if acc_val and (-daily_pnl / acc_val) >= rc["daily_loss_limit"]:
                logs.append(f"🛑 Daily loss limit hit. Stopping.")
                break

            # Check max positions
            port = portfolio.get_portfolio_summary()
            if port.get("open_positions", 0) >= rc["max_positions"]:
                logs.append(f"⏸ Max positions reached ({rc['max_positions']}). Skipping {ticker}.")
                continue

            logs.append(f"🔍 Analysing {ticker}...")
            log_container.text("\n".join(logs[-20:]))

            try:
                result = run_full_analysis(ticker)
                trader_r = result.get("trader_analysis", {})
                risk_r   = result.get("risk_analysis", {})
                action   = trader_r.get("action", "HOLD")

                if action != "HOLD" and risk_r.get("approved"):
                    order = execute_trade(ticker, trader_r)
                    if order.get("status") == "error":
                        logs.append(f"❌ {ticker}: {order.get('error')}")
                    else:
                        logs.append(f"✅ {ticker}: {action} order submitted ({order.get('order_id','?')})")
                else:
                    logs.append(f"⏭ {ticker}: {action} — skipped")
            except Exception as e:
                logs.append(f"⚠️ {ticker}: Error — {e}")

            log_container.text("\n".join(logs[-20:]))
            time.sleep(2)

        st.session_state.autonomous_running = False
        st.success("Autonomous scan complete.")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: WATCHLIST
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Watchlist":
    st.markdown("# Watchlist")

    col_add, col_btn = st.columns([3, 1])
    with col_add:
        new_ticker = st.text_input("Add ticker", placeholder="AAPL", key="wl_input").upper().strip()
    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Add", use_container_width=True) and new_ticker:
            db.add_to_watchlist(new_ticker)
            st.rerun()

    watchlist = db.get_watchlist()
    if not watchlist:
        st.info("Your watchlist is empty. Add tickers above.")
    else:
        if st.button("Refresh Prices", use_container_width=False):
            pass  # triggers rerun

        rows = []
        for ticker in watchlist:
            price = fetcher.get_current_price(ticker)
            tech  = fetcher.get_technicals(ticker)
            rows.append({
                "Ticker": ticker,
                "Price":  price,
                "1D%":    tech.get("ret_1d"),
                "5D%":    tech.get("ret_5d"),
                "RSI":    tech.get("rsi"),
                "vs SMA50": tech.get("pct_vs_sma50"),
                "vs SMA200": tech.get("pct_vs_sma200"),
            })

        df_wl = pd.DataFrame(rows)

        rows_html = ""
        for _, r in df_wl.iterrows():
            ticker = r["Ticker"]
            price  = r["Price"] or 0
            d1     = r["1D%"] or 0
            d5     = r["5D%"] or 0
            rsi    = r["RSI"] or 0
            vs50   = r["vs SMA50"] or 0
            vs200  = r["vs SMA200"] or 0

            def pct_cell(v):
                c = "#22c55e" if v >= 0 else "#ef4444"
                return f'<td style="color:{c};">{v:+.2f}%</td>'

            rows_html += (
                f'<tr>'
                f'<td><b>{ticker}</b></td>'
                f'<td>${price:,.2f}</td>'
                + pct_cell(d1) + pct_cell(d5)
                + f'<td style="color:{"#ef4444" if rsi>70 else "#22c55e" if rsi<30 else "#475569"};">{rsi:.1f}</td>'
                + pct_cell(vs50) + pct_cell(vs200)
                + f'<td><button onclick="return false;" style="background:#fee2e2;border:none;border-radius:4px;'
                  f'padding:3px 8px;cursor:pointer;font-size:11px;">Remove</button></td>'
                f'</tr>'
            )

        st.markdown(
            f'<div class="card" style="padding:0;overflow:hidden;">'
            f'<table class="screener-table">'
            f'<thead><tr><th>Ticker</th><th>Price</th><th>1D%</th><th>5D%</th>'
            f'<th>RSI</th><th>vs SMA50</th><th>vs SMA200</th><th></th></tr></thead>'
            f'<tbody>{rows_html}</tbody>'
            f'</table></div>',
            unsafe_allow_html=True,
        )

        # Remove buttons with Streamlit
        st.markdown("**Remove from watchlist:**")
        cols = st.columns(min(len(watchlist), 6))
        for i, t in enumerate(watchlist):
            with cols[i % len(cols)]:
                if st.button(f"Remove {t}", key=f"rm_{t}"):
                    db.remove_from_watchlist(t)
                    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: TRADE JOURNAL
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Trade Journal":
    st.markdown("# Trade Journal")

    tab_trades, tab_decisions = st.tabs(["Trades", "Decision Log"])

    with tab_trades:
        trades = db.get_trades(limit=100)
        if not trades:
            st.info("No trades logged yet.")
        else:
            df_t = pd.DataFrame(trades)
            # Color P&L column
            def style_pnl(val):
                if val is None:
                    return ""
                return f"color: {'green' if val >= 0 else 'red'}"

            cols_display = ["ticker", "action", "quantity", "entry_price",
                            "stop_loss", "take_profit", "status", "pnl", "created_at"]
            cols_display = [c for c in cols_display if c in df_t.columns]
            df_show = df_t[cols_display].copy()
            df_show.columns = [c.replace("_", " ").title() for c in cols_display]

            st.dataframe(
                df_show.style.applymap(style_pnl, subset=["Pnl"] if "Pnl" in df_show.columns else []),
                use_container_width=True,
                height=400,
            )

            # P&L chart
            closed = [t for t in trades if t.get("pnl") is not None]
            if closed:
                df_pnl = pd.DataFrame(closed)[["created_at", "pnl", "ticker"]].copy()
                df_pnl["created_at"] = pd.to_datetime(df_pnl["created_at"])
                df_pnl = df_pnl.sort_values("created_at")
                df_pnl["cumulative_pnl"] = df_pnl["pnl"].cumsum()

                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=df_pnl["created_at"], y=df_pnl["cumulative_pnl"],
                    mode="lines+markers", name="Cumulative P&L",
                    line=dict(color="#3b82f6", width=2),
                    fill="tozeroy",
                    fillcolor="rgba(59,130,246,0.1)",
                ))
                fig.update_layout(
                    title="Cumulative P&L", height=300,
                    paper_bgcolor="white", plot_bgcolor="white",
                    xaxis=dict(gridcolor="#f1f5f9"),
                    yaxis=dict(gridcolor="#f1f5f9", tickprefix="$"),
                    margin=dict(l=10, r=10, t=40, b=10),
                )
                st.plotly_chart(fig, use_container_width=True)

    with tab_decisions:
        ticker_filter = st.text_input("Filter by ticker", placeholder="Leave blank for all").upper().strip()
        decisions = db.get_decisions(ticker=ticker_filter or None, limit=300)
        if not decisions:
            st.info("No decisions logged yet.")
        else:
            df_d = pd.DataFrame(decisions)
            cols_d = ["ticker", "agent_name", "signal", "confidence", "reasoning", "created_at"]
            cols_d = [c for c in cols_d if c in df_d.columns]
            df_show_d = df_d[cols_d].copy()
            df_show_d.columns = [c.replace("_", " ").title() for c in cols_d]
            st.dataframe(df_show_d, use_container_width=True, height=500)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: SETTINGS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Settings":
    st.markdown("# Settings")

    with st.form("risk_settings"):
        st.markdown("### Risk Controls")
        rc = st.session_state.risk_config

        col1, col2 = st.columns(2)
        with col1:
            max_pos = st.slider(
                "Max Position Size (% of portfolio)", 1, 20,
                int(rc["max_position_pct"] * 100), step=1,
            )
            daily_loss = st.slider(
                "Daily Loss Limit (%)", 1, 10,
                int(rc["daily_loss_limit"] * 100), step=1,
            )
            max_positions = st.slider(
                "Max Concurrent Positions", 1, 30,
                int(rc["max_positions"]), step=1,
            )
        with col2:
            cooldown = st.slider(
                "Cooldown per Ticker (minutes)", 5, 480,
                int(rc["cooldown_minutes"]), step=5,
            )
            stop_loss = st.slider(
                "Default Stop Loss (%)", 1, 10,
                int(rc["stop_loss_pct"] * 100), step=1,
            )
            take_profit = st.slider(
                "Default Take Profit (%)", 1, 20,
                int(rc["take_profit_pct"] * 100), step=1,
            )

        if st.form_submit_button("Save Settings", type="primary"):
            st.session_state.risk_config = {
                "max_position_pct":  max_pos / 100,
                "daily_loss_limit":  daily_loss / 100,
                "max_positions":     max_positions,
                "cooldown_minutes":  cooldown,
                "stop_loss_pct":     stop_loss / 100,
                "take_profit_pct":   take_profit / 100,
            }
            st.success("Settings saved!")

    st.markdown("### API Status")
    api_checks = {
        "Anthropic": bool(ANTHROPIC_API_KEY),
        "Finnhub":   bool(__import__("config").FINNHUB_API_KEY),
        "Alpaca":    portfolio.connected,
        "NewsAPI":   bool(__import__("config").NEWS_API_KEY),
    }
    cols = st.columns(len(api_checks))
    for i, (name, ok) in enumerate(api_checks.items()):
        with cols[i]:
            icon = "✅" if ok else "❌"
            st.markdown(
                f'<div class="card" style="text-align:center;">'
                f'<div class="card-title">{name}</div>'
                f'<div style="font-size:28px;">{icon}</div>'
                f'</div>', unsafe_allow_html=True)

    st.markdown("### About")
    st.markdown("""
    <div class="card">
    <div class="card-title">AI Trading Agents v1.0</div>
    <p style="color:#475569;font-size:13px;">
    A 9-agent AI trading system powered by Claude.<br><br>
    <b>Haiku agents</b> (fast analysis): Macro, Fundamental, Technical, Sentiment, Bull Researcher, Bear Researcher<br>
    <b>Opus agents</b> (deep reasoning): Risk Manager, Head Trader, Hedge Agent<br><br>
    All trades are executed via Alpaca paper trading with bracket orders (stop loss + take profit).
    </p>
    </div>
    """, unsafe_allow_html=True)
