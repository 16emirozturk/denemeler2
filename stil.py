"""Arayüz stili: yerel sistem yazı tipleri, erişilebilir kontrast ve sade kurumsal düzen."""
import streamlit as st

CSS = """
<style>
:root { --ink:#18283b; --muted:#65758a; --line:#dce4ed; --navy:#193654; --blue:#315f96; --surface:#fff; --canvas:#f5f7fa; }
.stApp { background:var(--canvas); color:var(--ink); font-family:Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", Arial, sans-serif; }
.block-container { max-width:1380px; padding:1.2rem clamp(1rem,3vw,2.8rem) 2.5rem; }
h1,h2,h3 { color:var(--ink); letter-spacing:-.025em; }
h1 { font-weight:750; }
:focus-visible { outline:3px solid #3d78b5 !important; outline-offset:3px; }
[data-testid="stImage"] img { object-fit:contain; }
.brand-title { font-size:1.42rem; font-weight:760; letter-spacing:-.04em; color:#193654; line-height:1.2; }
.brand-subtitle { color:#52657b; font-size:.91rem; margin-top:.2rem; }
.brand-school { color:#7a899a; font-size:.75rem; margin-top:.25rem; letter-spacing:.025em; }
.brand-fallback { display:flex; width:62px; height:62px; border-radius:50%; align-items:center; justify-content:center; background:#193654; color:white; font-weight:800; }
.account-label { color:#7a899a; font-size:.73rem; text-align:right; text-transform:uppercase; letter-spacing:.08em; }
.account-name { color:#24384e; font-size:.92rem; font-weight:650; text-align:right; margin:.15rem 0 .4rem; }
.header-rule { border-top:1px solid var(--line); margin:.65rem 0 .75rem; }
/* Top navigation */
div[data-testid="stRadio"] { margin:.15rem 0 .8rem; }
div[data-testid="stRadio"] > div[role="radiogroup"] { display:flex; flex-wrap:wrap; gap:.35rem; padding:.35rem; background:#e9eef4; border:1px solid #dce4ed; border-radius:12px; }
div[data-testid="stRadio"] > div[role="radiogroup"] label { flex:0 1 auto; justify-content:center; border:1px solid transparent; border-radius:8px; padding:.58rem .82rem; color:#4b5e73; font-size:.86rem; font-weight:620; transition:background .15s ease; }
div[data-testid="stRadio"] > div[role="radiogroup"] label > div:first-child { display:none !important; }
div[data-testid="stRadio"] > div[role="radiogroup"] label:hover { background:#f8fafc; color:#1e4268; }
div[data-testid="stRadio"] > div[role="radiogroup"] label:has(input:checked) { background:#fff; color:#234f7c; border-color:#d8e2ed; box-shadow:0 1px 3px rgba(25,54,84,.07); }
.topbar { display:flex; align-items:center; justify-content:space-between; gap:1rem; padding:.1rem 0 .8rem; border-bottom:1px solid var(--line); margin-bottom:.8rem; }
.crumb { color:#6c7c90; font-size:.86rem; }.crumb span { margin:0 .4rem; color:#a4afbd; }.crumb b { color:#24384e; font-weight:650; }
.pills { display:flex; gap:.4rem; flex-wrap:wrap; justify-content:flex-end; }
.pill { display:inline-block; border-radius:7px; padding:.28rem .55rem; font-size:.74rem; font-weight:700; white-space:nowrap; }
.status-waiting { color:#805800; background:#fff2cf; }.status-active { color:#245b91; background:#e3edf9; }.status-followup { color:#93451e; background:#ffeadc; }.status-done { color:#236444; background:#e0f1e7; }
.prio-none { color:#526175; background:#edf1f5; }.prio-low { color:#245b91; background:#e3edf9; }.prio-mid { color:#805800; background:#fff2cf; }.prio-high { color:#93451e; background:#ffeadc; }.prio-urgent { color:#fff; background:#a52d2d; }
.notice-bar { display:flex; align-items:flex-start; gap:.6rem; padding:.72rem .9rem; margin:.2rem 0 1.2rem; border:1px solid #dce5ef; border-radius:10px; background:#fff; color:#56687c; font-size:.82rem; line-height:1.5; }
.notice-dot { width:7px; height:7px; flex-shrink:0; margin-top:.35rem; border-radius:50%; background:#477bad; }
.hero { padding:clamp(1.4rem,3vw,2.2rem); border-radius:15px; background:linear-gradient(115deg,#193654,#244c72); color:#fff; margin:.25rem 0 1.15rem; box-shadow:0 8px 24px rgba(25,54,84,.09); }
.hero h1 { color:#fff !important; margin:0 0 .6rem; font-size:clamp(1.75rem,3vw,2.55rem); line-height:1.16; max-width:920px; }
.hero p { color:#e3edf7; margin:0; max-width:760px; font-size:1rem; line-height:1.65; }
.eyebrow { text-transform:uppercase; letter-spacing:.13em; font-size:.7rem; font-weight:750; color:#c4d9ec; margin-bottom:.7rem; }
.eyebrow-dark { color:#315f96; font-size:.7rem; font-weight:800; letter-spacing:.13em; }
.page-heading h1 { margin:.12rem 0 .3rem; font-size:clamp(1.65rem,3vw,2.15rem); }.page-heading p { margin:0; color:var(--muted); max-width:800px; }
.soft-card { background:#fff; border:1px solid var(--line); border-radius:13px; padding:1.15rem 1.2rem; height:100%; box-shadow:0 2px 8px rgba(24,40,59,.025); }
.soft-card h3 { margin:.1rem 0 .45rem; font-size:1.04rem; }.soft-card p { color:var(--muted); margin:0; line-height:1.55; }
.emergency { border:1px solid #edc9c4; background:#fff7f5; color:#742c25; border-radius:10px; padding:.72rem .9rem; font-size:.88rem; line-height:1.55; }.emergency b { color:#9b3026; }
div[data-testid="stMetric"], div[data-testid="stForm"] { background:#fff; border:1px solid var(--line); border-radius:12px; padding:.9rem 1rem; box-shadow:0 2px 6px rgba(24,40,59,.025); }
.stButton > button, .stFormSubmitButton > button, .stDownloadButton > button { border-radius:8px; font-weight:650; min-height:2.55rem; }
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] { background:#315f96; border:1px solid #315f96; color:#fff; }
.stButton > button:hover, .stFormSubmitButton > button:hover, .stDownloadButton > button:hover { border-color:#315f96; }
[data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea, [data-testid="stSelectbox"] div[data-baseweb="select"] { border-radius:8px; }
[data-testid="stDataFrame"] { border:1px solid var(--line); border-radius:10px; overflow:hidden; }
.record-banner { display:flex; align-items:center; justify-content:space-between; gap:1rem; padding:.85rem 1rem; margin-bottom:1rem; border:1px solid #dce5ef; border-radius:11px; background:#fff; }
.record-kicker { color:var(--muted); font-size:.67rem; font-weight:800; letter-spacing:.11em; }.record-id { color:#172b46; font-size:1.16rem; font-weight:780; }
.access-panel { padding:1.1rem; border:1px solid #dbe5f1; border-radius:12px; background:#fff; }
hr { border-color:var(--line); }
@media (max-width:760px) { .block-container { padding-left:1rem; padding-right:1rem; } .hero { padding:1.35rem 1.15rem; } .topbar { align-items:flex-start; } .brand-title { font-size:1.15rem; } div[data-testid="stRadio"] > div[role="radiogroup"] label { padding:.5rem .62rem; font-size:.8rem; } }
@media (prefers-reduced-motion:reduce) { * { transition:none !important; animation:none !important; } }
</style>
"""

def uygula() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
