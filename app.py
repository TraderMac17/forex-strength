import sys
sys.path.insert(0, '/Users/genesisinfinity/Library/Python/3.9/lib/python/site-packages')

import streamlit as st
import pandas as pd
import time
from streamlit_autorefresh import st_autorefresh
from data import fetch_all_scores
from scorer import CURRENCIES, compute_currency_scores, format_score, strength_label
from trading_plan import generate_plan, best_trade
from history import save_snapshot, load_history, get_score_change

st.set_page_config(
    page_title="Forex Currency Strength",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

TIMEFRAMES = ["Daily", "4H", "1H"]

st_autorefresh(interval=3_600_000, key="hourly_refresh")

STRONG_BG,  STRONG_FG  = "#dcfce7", "#16a34a"
WEAK_BG,    WEAK_FG    = "#fee2e2", "#dc2626"
NEUTRAL_BG, NEUTRAL_FG = "#f3f4f6", "#6b7280"

LABEL_STYLE = {
    "STRONG":  (STRONG_BG,  STRONG_FG),
    "WEAK":    (WEAK_BG,    WEAK_FG),
    "NEUTRAL": (NEUTRAL_BG, NEUTRAL_FG),
}

CONF_COLOR = {"High": STRONG_FG, "Medium": "#d97706", "Low": NEUTRAL_FG}
DIR_COLOR  = {"LONG": STRONG_FG, "SHORT": WEAK_FG,    "NEUTRAL": NEUTRAL_FG}
DIR_ICON   = {"LONG": "▲",       "SHORT": "▼",         "NEUTRAL": "—"}

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; }
    h1 { font-size: 1.6rem !important; margin-bottom: 0 !important; }
    h2 { font-size: 1.2rem !important; }
    h3 { font-size: 1rem !important; }
    .section-header {
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 2px;
        color: #9ca3af;
        text-transform: uppercase;
        margin: 0.5rem 0 0.75rem 0;
    }
    .last-update { font-size: 11px; color: #9ca3af; margin-top: 2px; }
    .best-trade-box {
        background: linear-gradient(135deg, #f0fdf4, #dcfce7);
        border: 2px solid #16a34a;
        border-radius: 12px;
        padding: 16px 20px;
        margin-bottom: 16px;
    }
    .stale-warning {
        background: #fef9c3;
        border: 1px solid #ca8a04;
        border-radius: 8px;
        padding: 8px 14px;
        font-size: 12px;
        color: #854d0e;
        margin-bottom: 10px;
    }
    .failed-warning {
        background: #fee2e2;
        border: 1px solid #dc2626;
        border-radius: 8px;
        padding: 8px 14px;
        font-size: 12px;
        color: #991b1b;
        margin-bottom: 10px;
    }
    .retry-warning {
        background: #fef3c7;
        border: 1px solid #d97706;
        border-radius: 8px;
        padding: 8px 14px;
        font-size: 12px;
        color: #92400e;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)


def load_data():
    progress_bar   = st.progress(0, text="Starting data fetch…")
    status_box     = st.empty()

    def update_progress(pct, label):
        progress_bar.progress(pct, text=label)

    def update_status(msg):
        status_box.markdown('<div class="retry-warning">🔄 ' + msg + '</div>', unsafe_allow_html=True)

    all_scores, failed = fetch_all_scores(
        progress_callback=update_progress,
        status_callback=update_status,
    )
    progress_bar.empty()
    status_box.empty()

    currency_scores = {
        tf: compute_currency_scores(all_scores[tf]) for tf in TIMEFRAMES
    }
    save_snapshot(currency_scores)
    return all_scores, currency_scores, failed


if "all_scores" not in st.session_state:
    st.session_state.all_scores, st.session_state.currency_scores, st.session_state.failed = load_data()
    st.session_state.last_fetch  = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
    st.session_state.fetch_time  = time.time()

# ── Header ────────────────────────────────────────────────────────────────────
header_col, btn_col = st.columns([6, 1])
with header_col:
    st.markdown("# 📈 Forex Currency Strength")
    elapsed   = int((time.time() - st.session_state.fetch_time) / 60)
    remaining = max(0, 60 - elapsed)
    st.markdown(
        '<div class="last-update">Last updated: ' + st.session_state.last_fetch +
        ' · Next refresh in <b>' + str(remaining) + ' min</b></div>',
        unsafe_allow_html=True
    )
with btn_col:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("↺ Refresh", type="primary", use_container_width=True):
        st.session_state.all_scores, st.session_state.currency_scores, st.session_state.failed = load_data()
        st.session_state.last_fetch = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
        st.session_state.fetch_time = time.time()
        st.rerun()

# ── Warnings ──────────────────────────────────────────────────────────────────
if st.session_state.get("failed"):
    failed_list = ", ".join(st.session_state.failed[:10])
    more = len(st.session_state.failed) - 10
    msg  = "⚠️ Failed to load: " + failed_list
    if more > 0:
        msg += " and " + str(more) + " more"
    st.markdown('<div class="failed-warning">' + msg + '</div>', unsafe_allow_html=True)

if int((time.time() - st.session_state.fetch_time) / 60) >= 60:
    st.markdown('<div class="stale-warning">⚠️ Data may be stale — last fetched over 60 minutes ago.</div>', unsafe_allow_html=True)

all_scores      = st.session_state.all_scores
currency_scores = st.session_state.currency_scores

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — CURRENCY STRENGTH SCOREBOARD
# ══════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="section-header">Currency Strength Scoreboard</div>', unsafe_allow_html=True)

tf_cols = st.columns(3)


def currency_card(currency, data, tf):
    label       = strength_label(data)
    bg, fg      = LABEL_STYLE[label]
    score_str   = format_score(data)
    net         = data["net"]
    score_color = STRONG_FG if net > 0 else (WEAK_FG if net < 0 else NEUTRAL_FG)
    bar_pct     = int(abs(net) / 6 * 100)

    change = get_score_change(currency_scores, tf, currency)
    if change is None:
        arrow = ""
    elif change > 0:
        arrow = ' <span style="color:#16a34a;font-size:10px;">▲</span>'
    elif change < 0:
        arrow = ' <span style="color:#dc2626;font-size:10px;">▼</span>'
    else:
        arrow = ' <span style="color:#9ca3af;font-size:10px;">—</span>'

    bar_html = (
        '<div style="display:flex;align-items:flex-end;justify-content:center;height:80px;margin-bottom:4px;position:relative;">'
        '<div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:36px;height:1px;background:#d1d5db;"></div>'
        '<div style="width:32px;background:#e5e7eb;border-radius:6px;height:80px;position:relative;overflow:hidden;">'
    )
    if net >= 0:
        bar_html += '<div style="position:absolute;bottom:50%;width:100%;background:' + score_color + ';height:' + str(bar_pct // 2) + '%;border-radius:6px 6px 0 0;"></div>'
    else:
        bar_html += '<div style="position:absolute;top:50%;width:100%;background:' + score_color + ';height:' + str(bar_pct // 2) + '%;border-radius:0 0 6px 6px;"></div>'
    bar_html += '</div></div>'

    return (
        '<div style="background:' + bg + ';border-radius:10px;padding:10px 6px 8px;margin-bottom:6px;border:1px solid ' + fg + '22;text-align:center;">'
        '<div style="font-size:12px;font-weight:800;color:#1f2937;letter-spacing:1px;">' + currency + arrow + '</div>'
        '<div style="font-size:10px;font-weight:700;color:' + fg + ';letter-spacing:1px;margin-bottom:4px;">' + label + '</div>'
        + bar_html +
        '<div style="font-size:16px;font-weight:800;color:' + score_color + ';">' + score_str + '</div>'
        '</div>'
    )


for col, tf in zip(tf_cols, TIMEFRAMES):
    with col:
        st.markdown("**" + tf + "**")
        sorted_curs = sorted(
            CURRENCIES,
            key=lambda c: currency_scores[tf][c]["net"],
            reverse=True,
        )
        cards_html = "".join(currency_card(c, currency_scores[tf][c], tf) for c in sorted_curs)
        st.markdown(
            '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px;">' + cards_html + '</div>',
            unsafe_allow_html=True
        )

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — SUMMARY TABLE
# ══════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="section-header">Summary Table</div>', unsafe_allow_html=True)

header_cells = "".join(
    '<th style="padding:8px 14px;text-align:center;font-size:11px;letter-spacing:1px;">' + tf + '</th>'
    for tf in TIMEFRAMES
)

rows = ""
for cur in CURRENCIES:
    cells = '<td style="padding:8px 14px;font-weight:700;font-size:13px;">' + cur + '</td>'
    for tf in TIMEFRAMES:
        d       = currency_scores[tf][cur]
        label   = strength_label(d)
        net     = d["net"]
        abs_net = abs(net)
        if abs_net >= 5:
            opacity = 1.0
        elif abs_net >= 3:
            opacity = 0.75
        elif abs_net >= 1:
            opacity = 0.5
        else:
            opacity = 0.3
        bg, fg = LABEL_STYLE[label]
        score  = format_score(d)
        cells += (
            '<td style="padding:6px 14px;text-align:center;">'
            '<span style="background:' + bg + ';color:' + fg + ';font-weight:700;padding:3px 10px;border-radius:6px;font-size:13px;opacity:' + str(opacity) + ';">'
            + score +
            '</span></td>'
        )
    rows += '<tr style="border-bottom:1px solid #f3f4f6;">' + cells + '</tr>'

st.markdown(
    '<table style="width:100%;border-collapse:collapse;font-size:13px;">'
    '<thead><tr style="background:#f9fafb;border-bottom:2px solid #e5e7eb;">'
    '<th style="padding:8px 14px;text-align:left;font-size:11px;letter-spacing:1px;">CURRENCY</th>'
    + header_cells +
    '</tr></thead><tbody>' + rows + '</tbody></table>',
    unsafe_allow_html=True
)

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — TRADING PLAN
# ══════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="section-header">Trading Plan</div>', unsafe_allow_html=True)


def diff_color(net_diff):
    abs_diff = abs(net_diff)
    if abs_diff >= 8:
        return STRONG_FG
    elif abs_diff >= 5:
        return "#d97706"
    else:
        return NEUTRAL_FG


def trade_table(trades, direction):
    if not trades:
        return '<p style="color:#9ca3af;font-size:13px;padding:8px 0;">No signals for this timeframe.</p>'

    header = (
        '<tr style="background:#f9fafb;border-bottom:2px solid #e5e7eb;">'
        '<th style="padding:8px 12px;text-align:left;font-size:10px;letter-spacing:1px;color:#6b7280;">PAIR</th>'
        '<th style="padding:8px 12px;text-align:left;font-size:10px;letter-spacing:1px;color:#6b7280;">BASE</th>'
        '<th style="padding:8px 12px;text-align:left;font-size:10px;letter-spacing:1px;color:#6b7280;">QUOTE</th>'
        '<th style="padding:8px 12px;text-align:left;font-size:10px;letter-spacing:1px;color:#6b7280;">CONFIDENCE</th>'
        '<th style="padding:8px 12px;text-align:left;font-size:10px;letter-spacing:1px;color:#6b7280;">DIFF</th>'
        '<th style="padding:8px 12px;text-align:left;font-size:10px;letter-spacing:1px;color:#6b7280;">NOTE</th>'
        '</tr>'
    )

    body = ""
    for t in trades:
        conf       = t["confidence"] or "—"
        conf_clr   = CONF_COLOR.get(t["confidence"], NEUTRAL_FG)
        dir_clr    = DIR_COLOR[direction]
        icon       = DIR_ICON[direction]
        b_bg, b_fg = LABEL_STYLE[t["base_label"]]
        q_bg, q_fg = LABEL_STYLE[t["quote_label"]]
        diff_sign  = "+" if t["net_diff"] > 0 else ""
        d_color    = diff_color(t["net_diff"])
        corr_note  = '<span style="color:#d97706;font-size:10px;font-weight:700;">⚠ Correlated</span>' if t.get("correlated") else ""

        body += (
            '<tr style="border-bottom:1px solid #f3f4f6;' + ('background:#fffbeb;' if t.get("correlated") else '') + '">'
            '<td style="padding:9px 12px;font-weight:800;font-size:14px;color:' + dir_clr + ';">' + icon + ' ' + t['pair'] + '</td>'
            '<td style="padding:9px 12px;">'
            '<span style="font-weight:700;">' + t['base'] + '</span> '
            '<span style="background:' + b_bg + ';color:' + b_fg + ';font-size:10px;font-weight:700;padding:2px 7px;border-radius:4px;margin-left:4px;">' + t['base_label'] + ' ' + t['base_score'] + '</span>'
            '</td>'
            '<td style="padding:9px 12px;">'
            '<span style="font-weight:700;">' + t['quote'] + '</span> '
            '<span style="background:' + q_bg + ';color:' + q_fg + ';font-size:10px;font-weight:700;padding:2px 7px;border-radius:4px;margin-left:4px;">' + t['quote_label'] + ' ' + t['quote_score'] + '</span>'
            '</td>'
            '<td style="padding:9px 12px;font-weight:700;color:' + conf_clr + ';">' + conf + '</td>'
            '<td style="padding:9px 12px;font-weight:800;color:' + d_color + ';">' + diff_sign + str(t['net_diff']) + '</td>'
            '<td style="padding:9px 12px;">' + corr_note + '</td>'
            '</tr>'
        )

    return '<table style="width:100%;border-collapse:collapse;font-size:13px;"><thead>' + header + '</thead><tbody>' + body + '</tbody></table>'


def neutral_table(trades):
    if not trades:
        return ""
    rows_html = ""
    for t in trades:
        b_bg, b_fg = LABEL_STYLE[t["base_label"]]
        q_bg, q_fg = LABEL_STYLE[t["quote_label"]]
        rows_html += (
            '<tr style="border-bottom:1px solid #f3f4f6;">'
            '<td style="padding:7px 12px;font-weight:700;color:#6b7280;">' + t['pair'] + '</td>'
            '<td style="padding:7px 12px;">' + t['base'] + ' '
            '<span style="background:' + b_bg + ';color:' + b_fg + ';font-size:10px;font-weight:700;padding:2px 7px;border-radius:4px;">' + t['base_label'] + '</span></td>'
            '<td style="padding:7px 12px;">' + t['quote'] + ' '
            '<span style="background:' + q_bg + ';color:' + q_fg + ';font-size:10px;font-weight:700;padding:2px 7px;border-radius:4px;">' + t['quote_label'] + '</span></td>'
            '<td style="padding:7px 12px;color:#9ca3af;font-size:11px;">' + t['base_label'] + ' vs ' + t['quote_label'] + '</td>'
            '</tr>'
        )

    return (
        '<table style="width:100%;border-collapse:collapse;font-size:12px;">'
        '<thead><tr style="background:#f9fafb;border-bottom:1px solid #e5e7eb;">'
        '<th style="padding:7px 12px;text-align:left;font-size:10px;color:#9ca3af;letter-spacing:1px;">PAIR</th>'
        '<th style="padding:7px 12px;text-align:left;font-size:10px;color:#9ca3af;letter-spacing:1px;">BASE</th>'
        '<th style="padding:7px 12px;text-align:left;font-size:10px;color:#9ca3af;letter-spacing:1px;">QUOTE</th>'
        '<th style="padding:7px 12px;text-align:left;font-size:10px;color:#9ca3af;letter-spacing:1px;">REASON</th>'
        '</tr></thead>'
        '<tbody>' + rows_html + '</tbody></table>'
    )


plan_tabs = st.tabs(TIMEFRAMES)

for tab, tf in zip(plan_tabs, TIMEFRAMES):
    with tab:
        trades  = generate_plan(currency_scores[tf])
        longs   = [t for t in trades if t["direction"] == "LONG"]
        shorts  = [t for t in trades if t["direction"] == "SHORT"]
        neutral = [t for t in trades if t["direction"] == "NEUTRAL"]
        top     = best_trade(trades)

        if top:
            dir_clr    = DIR_COLOR[top["direction"]]
            icon       = DIR_ICON[top["direction"]]
            b_bg, b_fg = LABEL_STYLE[top["base_label"]]
            q_bg, q_fg = LABEL_STYLE[top["quote_label"]]
            diff_sign  = "+" if top["net_diff"] > 0 else ""
            st.markdown(
                '<div class="best-trade-box">'
                '<div style="font-size:11px;font-weight:700;color:#16a34a;letter-spacing:2px;margin-bottom:6px;">⭐ BEST TRADE OF THE SESSION</div>'
                '<div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;">'
                '<span style="font-size:20px;font-weight:900;color:' + dir_clr + ';">' + icon + ' ' + top['pair'] + '</span>'
                '<span style="background:' + b_bg + ';color:' + b_fg + ';font-size:11px;font-weight:700;padding:3px 10px;border-radius:6px;">' + top['base'] + ' ' + top['base_label'] + ' ' + top['base_score'] + '</span>'
                '<span style="background:' + q_bg + ';color:' + q_fg + ';font-size:11px;font-weight:700;padding:3px 10px;border-radius:6px;">' + top['quote'] + ' ' + top['quote_label'] + ' ' + top['quote_score'] + '</span>'
                '<span style="font-size:13px;font-weight:700;color:' + CONF_COLOR.get(top["confidence"], NEUTRAL_FG) + ';">Confidence: ' + str(top["confidence"]) + '</span>'
                '<span style="font-size:13px;font-weight:700;color:' + diff_color(top["net_diff"]) + ';">Diff: ' + diff_sign + str(top["net_diff"]) + '</span>'
                '</div>'
                '</div>',
                unsafe_allow_html=True
            )

        m1, m2, m3 = st.columns(3)
        m1.metric("Long Signals",     len(longs))
        m2.metric("Short Signals",    len(shorts))
        m3.metric("No Trade (Pairs)", len(neutral))

        st.markdown("<br>", unsafe_allow_html=True)

        long_col, short_col = st.columns(2)

        with long_col:
            st.markdown('<span style="color:' + STRONG_FG + ';font-weight:800;font-size:14px;">▲ LONG OPPORTUNITIES (' + str(len(longs)) + ')</span>', unsafe_allow_html=True)
            st.markdown(trade_table(longs, "LONG"), unsafe_allow_html=True)

        with short_col:
            st.markdown('<span style="color:' + WEAK_FG + ';font-weight:800;font-size:14px;">▼ SHORT OPPORTUNITIES (' + str(len(shorts)) + ')</span>', unsafe_allow_html=True)
            st.markdown(trade_table(shorts, "SHORT"), unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        with st.expander("No Trade / Neutral Pairs (" + str(len(neutral)) + ")"):
            st.markdown(neutral_table(neutral), unsafe_allow_html=True)

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — SCORE HISTORY LOG
# ══════════════════════════════════════════════════════════════════════════════
with st.expander("📊 Score History Log"):
    history = load_history()
    if len(history) < 2:
        st.markdown('<p style="color:#9ca3af;font-size:13px;">Not enough history yet — check back after the next refresh.</p>', unsafe_allow_html=True)
    else:
        hist_tf = st.selectbox("Timeframe", TIMEFRAMES, key="hist_tf")
        hist_rows = ""
        for cur in CURRENCIES:
            hist_cells = '<td style="padding:7px 12px;font-weight:700;font-size:13px;">' + cur + '</td>'
            for snap in history[-10:]:
                score_data = snap["scores"].get(hist_tf, {}).get(cur)
                if score_data:
                    net    = score_data["net"]
                    label  = "STRONG" if net >= 4 else ("WEAK" if net <= -4 else "NEUTRAL")
                    bg, fg = LABEL_STYLE[label]
                    s      = score_data["strong"]
                    w      = score_data["weak"]
                    if w == 0 and s == 0:
                        score_str = "0"
                    elif w == 0:
                        score_str = "+" + str(s)
                    elif s == 0:
                        score_str = "-" + str(w)
                    else:
                        score_str = "-" + str(w) + "/+" + str(s)
                    hist_cells += (
                        '<td style="padding:6px 10px;text-align:center;">'
                        '<span style="background:' + bg + ';color:' + fg + ';font-weight:700;padding:2px 8px;border-radius:5px;font-size:12px;">' + score_str + '</span>'
                        '</td>'
                    )
                else:
                    hist_cells += '<td style="padding:6px 10px;text-align:center;color:#9ca3af;">—</td>'
            hist_rows += '<tr style="border-bottom:1px solid #f3f4f6;">' + hist_cells + '</tr>'

        time_headers = "".join(
            '<th style="padding:7px 10px;text-align:center;font-size:10px;color:#6b7280;white-space:nowrap;">' + snap["timestamp"][11:16] + '</th>'
            for snap in history[-10:]
        )

        st.markdown(
            '<table style="width:100%;border-collapse:collapse;font-size:12px;">'
            '<thead><tr style="background:#f9fafb;border-bottom:2px solid #e5e7eb;">'
            '<th style="padding:7px 12px;text-align:left;font-size:10px;color:#6b7280;">CURRENCY</th>'
            + time_headers +
            '</tr></thead><tbody>' + hist_rows + '</tbody></table>',
            unsafe_allow_html=True
        )

st.divider()

with st.expander("Raw Pair Scores (debug)"):
    pair_tabs = st.tabs(TIMEFRAMES)
    for tab, tf in zip(pair_tabs, TIMEFRAMES):
        with tab:
            pair_data = []
            for symbol, raw in all_scores[tf].items():
                direction = "▲ Bullish" if raw > 0 else ("▼ Bearish" if raw < 0 else "— Neutral")
                pair_data.append({"Pair": symbol, "Candle Score": raw, "Direction": direction})
            st.dataframe(pd.DataFrame(pair_data), width='stretch', hide_index=True)