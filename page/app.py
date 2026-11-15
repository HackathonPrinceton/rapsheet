"""The device page.  Run:  streamlit run page/app.py   (from the repo root)

A full-width dashboard with five tabs: Overview, Evidence, Timeline, Recalls & filing, Trust.
Every number opens the FDA reports behind it, and every model flag says why it was raised.
Explanations are precomputed by pipeline/explain.py, so the page loads no model.
"""
import base64
import html
import json
import os
import re
import sys

import altair as alt
import pandas as pd
import streamlit as st

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)
from pipeline.deathwords import STATES_DEATH  # noqa: E402
from service import record  # noqa: E402

BLUE, RED, INK, GREY, LIGHT, LINE = "#2563eb", "#dc2626", "#111827", "#6b7280", "#cbd5e1", "#e5e7eb"
EVENT_COLORS = {"Death": RED, "Injury": "#f59e0b", "Malfunction": "#cbd5e1", "Other": "#e2e8f0", "Not given": "#f1f5f9"}
METRICS = "https://github.com/HackathonPrinceton/rapsheet/blob/main/eval/metrics.md"
LINKS = {"fda_url": st.column_config.LinkColumn("FDA page", display_text="open ↗"),
         "fda_api_url": st.column_config.LinkColumn("Raw", display_text="json")}
DEATH_PHRASES = STATES_DEATH          # shared with the pipeline (pipeline/deathwords.py)

ASSETS = os.path.join(os.path.dirname(__file__), "..", "assets")
with open(os.path.join(ASSETS, "logo.svg"), "rb") as _f:
    LOGO = "data:image/svg+xml;base64," + base64.b64encode(_f.read()).decode()
st.set_page_config(page_title="Rap Sheet", page_icon=os.path.join(ASSETS, "logo.png"), layout="wide")
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"], p, li, label {{ font-family: 'Inter', sans-serif; }}
#MainMenu, footer, header [data-testid="stToolbar"] {{ visibility: hidden; }}
.block-container {{ padding: 3.6rem 2.2rem 2rem; max-width: 100%; }}
.logo {{ font-weight: 800; font-size: 1.15rem; color: {INK}; display: flex; align-items: center; gap: .45rem; padding-top: .45rem; }}
.logo .dot {{ width: .8rem; height: .8rem; border-radius: 50%; background: {BLUE}; box-shadow: 0 0 0 4px #dbeafe; }}
.devhead {{ display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: .6rem;
           padding: .9rem 0 .2rem; border-top: 1px solid {LINE}; margin-top: .6rem; }}
.devname {{ font-size: 1.7rem; font-weight: 800; color: {INK}; line-height: 1.15; }}
.devsub {{ color: {GREY}; font-size: .9rem; margin-top: .15rem; }}
.pills {{ display: flex; gap: .4rem; flex-wrap: wrap; }}
.pill {{ font-size: .8rem; font-weight: 600; padding: .3rem .7rem; border-radius: 999px; background: #f3f4f6; color: #374151; }}
.pill.red {{ background: #fee2e2; color: #b91c1c; }} .pill.blue {{ background: #dbeafe; color: #1d4ed8; }}
.kpis {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: .9rem; margin: .4rem 0 1rem; }}
.kpi {{ background: #f8fafc; border: 1px solid {LINE}; border-radius: 12px; padding: .9rem 1.1rem; }}
.kpi .v {{ font-size: 2rem; font-weight: 800; color: {INK}; line-height: 1.1; }}
.kpi.red .v {{ color: {RED}; }}
.kpi .l {{ font-size: .86rem; font-weight: 600; color: #374151; margin-top: .2rem; }}
.kpi .s {{ font-size: .76rem; color: {GREY}; margin-top: .25rem; }}
.panel {{ background: white; border: 1px solid {LINE}; border-radius: 12px; padding: 1rem 1.15rem; }}
.ptitle {{ font-size: .78rem; font-weight: 700; color: {GREY}; text-transform: uppercase; letter-spacing: .06em; margin-bottom: .5rem; }}
.quote {{ font-size: .88rem; line-height: 1.55; color: #1f2937; background: #f8fafc; border-left: 3px solid {RED};
         border-radius: 6px; padding: .65rem .8rem; margin: .4rem 0 .7rem; }}
.quote mark {{ background: #fee2e2; color: #b91c1c; font-weight: 700; padding: 0 .12rem; border-radius: 3px; }}
.wit {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: .5rem; margin: .3rem 0 .8rem; }}
.w {{ border: 1px solid {LINE}; border-radius: 10px; padding: .5rem .65rem; font-size: .76rem; color: {GREY}; }}
.w b {{ display: block; font-size: .9rem; color: {INK}; margin-top: .1rem; }}
.w.yes {{ border-color: #fecaca; background: #fef2f2; }} .w.yes b {{ color: {RED}; }}
.bar {{ display: flex; align-items: center; gap: .5rem; margin: .22rem 0; font-size: .8rem; }}
.bar .t {{ flex: 0 0 34%; text-align: right; color: #374151; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.bar .b {{ height: .6rem; border-radius: 4px; }}
.bar .n {{ color: {GREY}; font-size: .74rem; }}
.trust {{ background: #eff6ff; color: #1e3a8a; border-radius: 10px; padding: .6rem .8rem; font-size: .85rem; margin-top: .7rem; }}
.near {{ font-size: .8rem; color: #374151; margin-top: .6rem; }}
.near i {{ color: {GREY}; }}
a.btn {{ display: inline-block; margin-top: .7rem; font-size: .85rem; font-weight: 600; color: {BLUE}; text-decoration: none; }}
.flow {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: .6rem; }}
.step {{ background: #f8fafc; border: 1px solid {LINE}; border-radius: 12px; padding: .8rem; position: relative; }}
.step .v {{ font-size: 1.35rem; font-weight: 800; color: {BLUE}; }}
.step .l {{ font-size: .8rem; color: #374151; margin-top: .2rem; }}
.rc {{ background: white; border: 1px solid {LINE}; border-radius: 12px; padding: .85rem 1rem; height: 100%; }}
.rc .top {{ display: flex; justify-content: space-between; font-size: .8rem; color: {GREY}; }}
.rc .r {{ font-size: .9rem; color: {INK}; margin: .45rem 0; }}
.rc .f {{ font-size: .76rem; color: {GREY}; }}
.stTabs [data-baseweb="tab-list"] {{ gap: .3rem; border-bottom: 1px solid {LINE}; }}
.stTabs [data-baseweb="tab"] {{ height: 2.6rem; padding: 0 1.1rem; font-weight: 600; }}
.note {{ font-size: .78rem; color: {GREY}; }}
.src {{ display: inline-flex; align-items: center; gap: .3rem; font-size: .72rem; font-weight: 600; margin-top: .55rem;
       padding: .18rem .55rem; border-radius: 999px; }}
.src.fda {{ background: #ecfdf5; color: #047857; }} .src.model {{ background: #eff6ff; color: #1d4ed8; }}
.dots {{ display: flex; flex-wrap: wrap; gap: 3px; margin-top: .45rem; max-width: 17rem; }}
.dots span {{ width: .62rem; height: .62rem; border-radius: 50%; background: {BLUE}; }}
.dots span.x {{ background: #fca5a5; }}
.dotlbl {{ font-size: .74rem; color: {GREY}; margin-top: .25rem; }}
.miss {{ background: #fff7ed; border: 1px solid #fed7aa; border-radius: 12px; padding: .9rem 1.1rem; }}
.miss .h {{ font-weight: 700; color: #9a3412; font-size: .9rem; }}
.miss mark {{ background: #fed7aa; color: #9a3412; font-weight: 700; padding: 0 .1rem; border-radius: 3px; }}
.miss .q {{ font-size: .85rem; color: #1f2937; margin: .45rem 0; line-height: 1.5; }}
@media (max-width: 900px) {{ .kpis, .flow {{ grid-template-columns: repeat(2, 1fr); }} .wit {{ grid-template-columns: 1fr; }}
  .block-container {{ padding: 3.4rem 1rem .8rem; }} }}
</style>""", unsafe_allow_html=True)


# ---------------------------------------------------------------- section 1 design: paper record on navy
NAVY, CLIP, PAPER_BG = "#2f3e6b", "#c0392b", "#eef0f5"
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&family=Playfair+Display:wght@500;600&display=swap');
html, body, [class*="css"], p, li, label, .stMarkdown {{ font-family: 'IBM Plex Sans', sans-serif; }}
.stApp {{ background: linear-gradient({NAVY} 0, {NAVY} 300px, {PAPER_BG} 300px); }}
header[data-testid="stHeader"] {{ background: transparent; }}
.block-container {{ padding: 2.2rem 2.2rem 2rem; max-width: 1240px; }}
.brand {{ display: flex; align-items: center; gap: 1rem; color: #fff; font-weight: 700; font-size: 2.3rem;
          letter-spacing: -.01em; padding-top: .1rem; }}
.brand img {{ height: 3.9rem; border-radius: 14px; box-shadow: 0 0 0 1px rgba(255,255,255,.25); }}
/* Search: a clear search box on the navy band. White box, dark text, magnifier icon, hint that clears on focus. */
.st-key-search [data-baseweb="input"] {{ background: #fff !important; border: 2px solid rgba(255,255,255,.55) !important;
    border-radius: 999px !important; box-shadow: 0 6px 18px rgba(15,23,42,.25); }}
.st-key-search [data-baseweb="input"]:focus-within {{ border-color: #fff !important; box-shadow: 0 0 0 4px rgba(255,255,255,.25); }}
.st-key-search [data-baseweb="base-input"] {{ background: transparent !important; }}
.st-key-search input {{ background: transparent !important; color: #111827 !important; -webkit-text-fill-color: #111827 !important;
    caret-color: {NAVY}; font-size: 1rem !important; height: 2.9rem; padding-left: 2.9rem !important;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='20' height='20' viewBox='0 0 24 24' fill='none' stroke='%236b7280' stroke-width='2.4' stroke-linecap='round'%3E%3Ccircle cx='11' cy='11' r='7'/%3E%3Cline x1='16.5' y1='16.5' x2='21' y2='21'/%3E%3C/svg%3E") !important;
    background-repeat: no-repeat !important; background-position: 1rem center !important; }}
.st-key-search input::placeholder {{ color: #9ca3af !important; -webkit-text-fill-color: #9ca3af !important; opacity: 1; }}
.st-key-search input:focus::placeholder {{ color: transparent !important; -webkit-text-fill-color: transparent !important; }}
.st-key-search [data-testid="InputInstructions"] {{ display: none; }}
.st-key-paper, .st-key-home {{ background: #fff; border-radius: 14px; padding: 2.4rem 3rem 1.6rem; position: relative;
                              margin-top: 1.6rem; box-shadow: 0 12px 40px rgba(15,23,42,.18); }}
.st-key-paper::before, .st-key-home::before {{ content: ""; position: absolute; top: -.62rem; left: 50%;
    transform: translateX(-50%); width: 5.5rem; height: 1.25rem; background: {CLIP}; border-radius: 6px; }}
.rec-eyebrow {{ display: flex; justify-content: space-between; gap: 1rem; flex-wrap: wrap;
               font-family: 'IBM Plex Mono', monospace; font-size: .92rem; font-weight: 500; letter-spacing: .06em;
               color: #374151; text-transform: uppercase; }}
.rec-title {{ font-family: 'Playfair Display', Georgia, serif; font-weight: 500; color: {NAVY};
             font-size: 3.1rem; line-height: 1.1; margin: .55rem 0 1.4rem; }}
.facts {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 2rem; align-items: end; }}
.fact .k {{ font-family: 'IBM Plex Mono', monospace; font-size: .72rem; letter-spacing: .08em; color: {NAVY};
           text-transform: uppercase; }}
.fact .v {{ font-size: 1.3rem; font-weight: 500; color: #1f2937; padding: .35rem 0 .45rem;
           border-bottom: 1.5px solid #d1d5db; }}
/* Highlighter-pen labels: grey-blue for neutral facts, light red for the alarming ones. */
.fact .k {{ display: inline-block; background: #dde2ee; padding: .18rem .45rem .14rem; border-radius: 3px; }}
.fact.alarm .v {{ color: {CLIP}; font-weight: 600; }}
.fact.alarm .v {{ border-bottom-color: {CLIP}; }}
.rec-note {{ font-size: .85rem; color: #6b7280; margin: 1.1rem 0 2.6rem; }}
/* Tabs as equal segments: thin dividers between them, a navy bar on top of the selected one. */
.st-key-paper [data-testid="stTabs"] {{ width: 100%; }}
.st-key-paper [role="tablist"] {{ display: flex !important; width: 100% !important; gap: 0 !important;
    border-top: 1px solid #e5e7eb; border-bottom: 1px solid #e5e7eb; }}
.st-key-paper [role="tablist"] > div {{ display: flex !important; width: 100% !important; gap: 0 !important; }}
.st-key-paper [role="tab"] {{ flex: 1 1 0 !important; min-width: 0; justify-content: center !important; height: 3.2rem;
    margin: 0 !important; padding: 0 .5rem !important; font-weight: 500; color: #374151;
    border-right: 1px solid #e5e7eb !important; }}
.st-key-paper [role="tab"]:last-of-type {{ border-right: none !important; }}
.st-key-paper [role="tab"][aria-selected="true"] {{ box-shadow: inset 0 3px 0 {NAVY}; background: #fbfbfd; color: {NAVY};
    font-weight: 600; }}
.st-key-paper [data-baseweb="tab-highlight"], .st-key-paper [data-baseweb="tab-border"] {{ display: none !important; }}
.st-key-paper [role="tab"] p {{ font-size: 1.02rem; }}
.cards {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 1.1rem; margin: 1.6rem 0 1rem; }}
.card {{ background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; padding: 1.6rem 1.5rem 1.2rem;
        display: flex; flex-direction: column; }}
.card.main {{ background: #f3f7fe; border: 1.5px solid #b9cdf2; }}
.card .lab {{ font-family: 'IBM Plex Mono', monospace; font-size: .76rem; letter-spacing: .1em; color: #4b5563;
             text-transform: uppercase; }}
.card.main .lab {{ color: #1d4ed8; }}
.card .num {{ font-family: 'Playfair Display', Georgia, serif; font-size: 3.1rem; font-weight: 500; color: #1f2937;
             line-height: 1.05; margin: 1.1rem 0 .9rem; }}
.card.main .num {{ color: #b3261e; }}
.card .desc {{ font-size: 1rem; font-weight: 500; color: #1f2937; line-height: 1.35; }}
.card .open {{ color: #b3261e; font-weight: 600; font-size: .9rem; margin-top: .45rem; }}
.card .open::before {{ content: ""; display: inline-block; width: .5rem; height: .5rem; border-radius: 50%;
                      background: #b3261e; margin-right: .45rem; vertical-align: .08rem; }}
.tag {{ display: inline-flex; align-items: center; gap: .35rem; align-self: flex-start; font-size: .78rem; font-weight: 600;
       padding: .28rem .7rem; border-radius: 999px; margin-top: .8rem; }}
.tag.fda {{ background: #e8f3ec; color: #1b6b3a; }}
.tag.model {{ background: #dfe9fb; color: #1d4ed8; }}
.card .dots {{ display: flex; flex-wrap: wrap; gap: 4px; margin-top: 1.1rem; max-width: 15rem; }}
.card .dots span {{ width: .7rem; height: .7rem; border-radius: 50%; background: #1d4ed8; }}
.card .dots span.x {{ background: transparent; box-shadow: inset 0 0 0 1.5px #93b0e6; }}
.card .proof {{ font-size: .85rem; color: #4b5563; margin-top: .6rem; line-height: 1.45; }}
.card .foot {{ margin-top: auto; padding-top: 1.4rem; }}
.card .foot a {{ display: block; border-top: 1px dashed #d1d5db; padding-top: .9rem; font-size: .92rem; font-weight: 600; color: {NAVY};
                  text-decoration: underline; text-underline-offset: 3px; }}
.legend {{ font-size: .9rem; color: #4b5563; margin: 0 0 2rem; display: flex; flex-wrap: wrap; gap: .4rem 1.4rem; }}
.legend b {{ font-weight: 600; }}
.legend .sq {{ display: inline-block; width: .7rem; height: .7rem; border-radius: 2px; margin-right: .35rem; vertical-align: -.05rem; }}
.st-key-chartcard, .st-key-evcard {{ background: #fff; border: 1px solid #e5e7eb; border-radius: 10px;
    padding: 1.6rem 1.7rem 1.2rem; }}
.c-title {{ font-family: 'Playfair Display', Georgia, serif; font-size: 1.55rem; font-weight: 500; color: {NAVY}; }}
.c-sub {{ font-size: .95rem; color: #4b5563; margin: .3rem 0 .9rem; line-height: 1.45; }}
.c-legend {{ display: flex; flex-wrap: wrap; align-items: center; gap: .4rem 1.2rem; font-size: .9rem; color: #374151; }}
.c-legend b {{ font-weight: 600; color: #1f2937; }}
.c-legend .sw {{ display: inline-block; width: .75rem; height: .75rem; border-radius: 2px; margin-right: .35rem; vertical-align: -.08rem; }}
.c-legend .sep {{ width: 1px; height: 1rem; background: #d1d5db; }}
.strip-lab {{ font-size: .9rem; font-weight: 600; color: #4b5563; margin: 1rem 0 .15rem 2.75rem; line-height: 1.4;
              position: relative; z-index: 2; }}
.strip-lab small {{ font-weight: 400; color: #6b7280; font-size: .82rem; }}
.st-key-chartcard [data-testid="stVegaLiteChart"], .st-key-chartcard2 [data-testid="stVegaLiteChart"] {{ margin-top: 0; }}
.strip-lab.red {{ color: #b3261e; }}
.hl {{ display: inline-block; font-family: 'IBM Plex Mono', monospace; font-size: .8rem; font-weight: 600;
      letter-spacing: .1em; text-transform: uppercase; color: #1f2937; background: #fde68a; padding: .12rem .4rem;
      border-radius: 3px; transform: rotate(-1deg); }}
.ev-id {{ font-family: 'IBM Plex Mono', monospace; font-size: .86rem; color: #4b5563; margin: .5rem 0 .9rem; }}
.ev-q {{ font-family: 'IBM Plex Mono', monospace; font-size: .86rem; line-height: 1.6; color: #1f2937;
        background: #f6f5f0; border-radius: 6px; padding: 1rem 1.05rem; }}
.ev-q mark {{ background: #fdecea; color: #b3261e; font-weight: 600; text-decoration: underline;
             text-decoration-color: #b3261e; text-underline-offset: 3px; padding: 0 .15rem; border-radius: 3px; }}
.wh {{ font-weight: 600; color: #1f2937; margin: 1.2rem 0 .55rem; }}
.w3 {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: .55rem; }}
.w3 .b {{ border: 1px solid #e5e7eb; border-radius: 6px; padding: .6rem .7rem; font-size: .8rem; color: #4b5563; min-height: 4.6rem; }}
.w3 .b strong {{ display: block; font-size: 1rem; color: #1f2937; margin-top: .2rem; line-height: 1.25; }}
.w3 .b.odd {{ border: 1.5px dashed #9ca3af; }}
.w3 .b.odd strong {{ text-decoration: line-through; text-decoration-thickness: 2px; }}
.w3 .b.death {{ background: #fdecea; border-color: #f5c2bd; }}
.w3 .b.death strong {{ color: #b3261e; }}
.w3cap {{ display: grid; grid-template-columns: 1fr 2fr; gap: .55rem; font-size: .8rem; margin-top: .4rem; }}
.w3cap .l {{ text-align: center; color: #4b5563; }}
.w3cap .r {{ text-align: center; color: #b3261e; font-weight: 600; border-top: 2px solid #b3261e; padding-top: .3rem; }}
.conf {{ background: #f3f7fe; border: 1px solid #d6e2f8; border-radius: 8px; padding: .9rem 1rem; margin-top: 1.1rem; }}
.conf .h {{ font-size: .82rem; font-weight: 600; color: #1d4ed8; }}
.conf .t {{ font-size: .95rem; color: #1f2937; margin-top: .45rem; line-height: 1.45; }}
.conf .t b {{ color: #1d4ed8; }}
.conf .dots {{ display: flex; flex-wrap: wrap; gap: 4px; margin-top: .7rem; }}
.conf .dots span {{ width: .7rem; height: .7rem; border-radius: 50%; background: #1d4ed8; }}
.conf .dots span.x {{ background: transparent; box-shadow: inset 0 0 0 1.5px #93b0e6; }}
a.fda {{ display: inline-block; margin-top: 1rem; font-weight: 600; color: {NAVY}; text-decoration: underline;
        text-underline-offset: 3px; }}
a.below, .card .foot a {{ color: {NAVY} !important; }}
a.below {{ font-size: .95rem; font-weight: 600; text-decoration: underline; text-underline-offset: 3px; }}
a.below:hover, .card .foot a:hover {{ color: #1d4ed8 !important; }}
@media (max-width: 900px) {{
  .st-key-chartcard, .st-key-evcard {{ padding: 1.1rem .9rem 1rem; }}
  .w3 {{ grid-template-columns: 1fr; }} .w3cap {{ display: none; }} }}
.ev-h {{ font-family: 'Playfair Display', Georgia, serif; font-size: 2.05rem; font-weight: 500; color: {NAVY};
         line-height: 1.2; margin: 1.6rem 0 .35rem; max-width: 46rem; }}
.ev-h em {{ font-style: normal; color: #b3261e; }}
.ev-top {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem; }}
.ev-sub {{ font-size: 1.02rem; color: #4b5563; margin-bottom: 1.4rem; }}
.st-key-evlist, .st-key-whycard {{ background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; padding: 1.1rem 1.1rem .9rem; }}
.st-key-whycard {{ border: 1.5px solid #c9d6ee; box-shadow: 0 8px 26px rgba(47,62,107,.10); padding: 1.6rem 1.7rem 1.4rem; }}
.lst-h {{ display: flex; justify-content: space-between; font-size: .85rem; color: #6b7280; margin-bottom: .6rem; }}
.lst-h .m {{ font-family: 'IBM Plex Mono', monospace; letter-spacing: .08em; color: {NAVY}; text-transform: uppercase; font-size: .76rem; }}
.why-top {{ display: flex; justify-content: space-between; gap: 1rem; }}
.why-score {{ text-align: right; }}
.why-score .k {{ font-family: 'IBM Plex Mono', monospace; font-size: .7rem; letter-spacing: .1em; color: #6b7280; text-transform: uppercase; }}
.why-score .v {{ font-family: 'Playfair Display', Georgia, serif; font-size: 2.2rem; color: #1d4ed8; line-height: 1.1; }}
.step {{ display: flex; align-items: center; gap: .55rem; font-weight: 600; color: #1f2937; margin: 1.4rem 0 .6rem; }}
.step .n {{ display: inline-flex; align-items: center; justify-content: center; width: 1.45rem; height: 1.45rem;
           border-radius: 50%; background: {NAVY}; color: #fff; font-size: .78rem; font-weight: 600; }}
.why-note {{ font-size: .88rem; color: #4b5563; margin-top: .55rem; }}
.wbars {{ display: grid; grid-template-columns: 9rem 1fr 3.5rem; align-items: center; gap: .45rem .7rem; font-size: .92rem; }}
.wbars .hd {{ font-size: .78rem; color: #6b7280; }}
.wbars .t {{ text-align: right; color: #1f2937; }}
.wbars .track {{ position: relative; height: .7rem; }}
.wbars .track span {{ position: absolute; top: 0; height: .7rem; border-radius: 2px; }}
.wbars .track .zero {{ left: 12%; width: 1px; height: 1.2rem; top: -.25rem; background: #d1d5db; }}
.wbars .num {{ font-family: 'IBM Plex Mono', monospace; font-size: .8rem; color: #1d4ed8; }}
.wbars .num.neg {{ color: #6b7280; }}
.sim {{ border: 1px solid #e5e7eb; border-radius: 6px; padding: .75rem .9rem; margin-top: .55rem; }}
.sim .top {{ display: flex; justify-content: space-between; align-items: center; gap: .6rem;
            font-family: 'IBM Plex Mono', monospace; font-size: .8rem; color: #4b5563; }}
.sim .txt {{ font-family: 'IBM Plex Mono', monospace; font-size: .84rem; color: #1f2937; margin-top: .5rem; line-height: 1.5; }}
.sim .txt mark {{ background: none; color: #b3261e; font-weight: 600; }}
.who {{ font-family: 'IBM Plex Sans', sans-serif; font-size: .74rem; font-weight: 600; padding: .2rem .55rem; border-radius: 999px;
       white-space: nowrap; }}
.who.person {{ background: #dfe9fb; color: #1d4ed8; }}
.who.llm {{ background: #f3f4f6; color: #374151; border: 1px dashed #9ca3af; }}
.why-actions {{ border-top: 1px solid #e5e7eb; margin-top: 1.4rem; padding-top: 1.1rem; display: flex; gap: .7rem; flex-wrap: wrap; }}
a.b1, a.b2 {{ display: inline-block; padding: .7rem 1.1rem; border-radius: 6px; font-weight: 600; font-size: .95rem;
             text-decoration: none; }}
a.b1 {{ background: {NAVY}; color: #fff !important; }}
a.b2 {{ border: 1px solid #d1d5db; color: {NAVY} !important; }}
.st-key-paper [data-testid="stExpander"] {{ background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; margin-top: .9rem; }}
.st-key-paper [data-testid="stExpander"] summary p {{ font-size: 1.02rem; font-weight: 600; color: #1f2937; }}
@media (max-width: 900px) {{
  .ev-h {{ font-size: 1.5rem; }} .ev-top {{ flex-direction: column; }}
  .st-key-whycard {{ padding: 1.1rem .9rem 1rem; }}
  .wbars {{ grid-template-columns: 6.5rem 1fr 3rem; }} }}
.pcard, .st-key-chartcard2, .st-key-latecard, .st-key-calcard, .st-key-srccard {{ background: #fff; border: 1px solid #e5e7eb;
    border-radius: 10px; padding: 1.5rem 1.6rem 1.3rem; margin-top: 1.1rem; }}
.st-key-chartcard2 {{ margin-top: 1.6rem; }}
.lab2 {{ font-family: 'IBM Plex Mono', monospace; font-size: .76rem; letter-spacing: .1em; text-transform: uppercase; color: {NAVY}; }}
.st {{ display: inline-block; font-size: .76rem; font-weight: 600; padding: .18rem .6rem; border-radius: 999px; margin-left: .4rem;
      background: #f3f4f6; color: #374151; vertical-align: .1rem; }}
.st.open {{ background: #fdecea; color: #b3261e; border: 1px solid #f5c2bd; }}
.st.open::before {{ content: ""; display: inline-block; width: .42rem; height: .42rem; border-radius: 50%; background: #b3261e;
                   margin-right: .35rem; vertical-align: .06rem; }}
.tl-top {{ display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: .6rem; margin-bottom: 1.2rem; }}
.tl-leg {{ display: flex; gap: 1.1rem; font-size: .88rem; color: #4b5563; }}
.tl {{ position: relative; }}
.tl::before {{ content: ""; position: absolute; left: 1.05rem; top: 1rem; bottom: 1rem; width: 1px; background: #d1d5db; }}
.tl-row {{ display: grid; grid-template-columns: 2.2rem 9.5rem 1fr; gap: 1.1rem; align-items: start; margin-bottom: 1.5rem; position: relative; }}
.tl-ic {{ width: 2.2rem; height: 2.2rem; display: flex; align-items: center; justify-content: center; font-size: 1rem;
         background: #fff; border: 1.5px solid #9ca3af; border-radius: 50%; color: #4b5563; z-index: 1; }}
.tl-ic.rising {{ background: #1f2937; border-color: #1f2937; color: #fff; }}
.tl-ic.recall {{ background: {NAVY}; border-color: {NAVY}; color: #fff; border-radius: 6px; }}
.tl-when .d {{ font-family: 'IBM Plex Mono', monospace; font-size: .98rem; color: #1f2937; }}
.tl-when .k {{ font-family: 'IBM Plex Mono', monospace; font-size: .72rem; letter-spacing: .1em; text-transform: uppercase; color: #6b7280; margin-top: .2rem; }}
.tl-what .h {{ font-weight: 600; color: #1f2937; font-size: 1.02rem; }}
.tl-what .p {{ color: #4b5563; font-size: .95rem; line-height: 1.5; margin-top: .3rem; }}
.tl-what.box {{ background: #f3f4f8; border: 1px solid #e0e3ec; border-radius: 6px; padding: .9rem 1rem; }}
.limit {{ background: #fdf9e6; border: 1px solid #f1e6b5; border-radius: 10px; padding: 1.4rem 1.4rem 1.2rem; margin-top: 1.1rem; }}
.limit .big {{ font-family: 'Playfair Display', Georgia, serif; font-size: 1.25rem; color: #1f2937; line-height: 1.4; margin: .9rem 0 1.1rem; }}
.limit .lb, .peers .pr {{ display: grid; grid-template-columns: 6.5rem 1fr 3rem; align-items: center; gap: .6rem; font-size: .88rem;
    color: #374151; margin: .45rem 0; }}
.limit .tr, .peers .tr, .mrow .tr {{ height: .5rem; background: #ece9d8; border-radius: 3px; overflow: hidden; }}
.peers .tr, .mrow .tr {{ background: #efeff1; height: .85rem; }}
.limit .tr i, .peers .tr i, .mrow .tr i {{ display: block; height: 100%; border-radius: 3px; }}
.limit .end {{ margin-top: 1rem; font-size: .95rem; color: #1f2937; }}
.rgrid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 1.4rem; }}
.rcard {{ background: #fff; border: 1px solid #e5e7eb; border-top: 3px solid {NAVY}; border-radius: 8px; padding: 1.3rem 1.4rem 1rem; }}
.rcard .rtop {{ display: flex; justify-content: space-between; align-items: center; gap: .6rem; }}
.rcard .num {{ font-family: 'IBM Plex Mono', monospace; font-size: 1.15rem; color: {NAVY}; font-weight: 500; }}
.rcard .when {{ font-family: 'IBM Plex Mono', monospace; font-size: .86rem; color: #4b5563; margin: .3rem 0 1rem; }}
.rcard .why {{ font-size: 1.02rem; color: #1f2937; line-height: 1.45; margin: .35rem 0 1rem; }}
.rcard .desc2 {{ font-family: 'IBM Plex Mono', monospace; font-size: .82rem; color: #4b5563; line-height: 1.5; margin-top: .35rem; }}
.rcard .desc2 mark {{ background: #fde68a; color: #1f2937; font-weight: 600; padding: 0 .2rem; border-radius: 2px; }}
.rcard .rfoot {{ display: flex; justify-content: space-between; gap: .8rem; flex-wrap: wrap; border-top: 1px dashed #d1d5db;
                margin-top: 1rem; padding-top: .8rem; font-size: .88rem; color: #4b5563; }}
.rcard .rfoot a, .wr a, .src2 a {{ color: {NAVY} !important; font-weight: 600; text-decoration: underline; text-underline-offset: 3px; }}
.late-top {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem; border-bottom: 1px solid #e5e7eb;
            padding-bottom: 1rem; margin-bottom: 1.2rem; }}
.late-h {{ display: flex; align-items: baseline; gap: 1rem; flex-wrap: wrap; }}
.late-h .n {{ font-family: 'Playfair Display', Georgia, serif; font-size: 3.6rem; color: #1f2937; line-height: 1; }}
.late-h .s {{ font-family: 'Playfair Display', Georgia, serif; font-size: 1.35rem; color: #1f2937; max-width: 32rem; line-height: 1.35; }}
.peers {{ margin-top: 1rem; }}
.peers .pr {{ grid-template-columns: 9rem 1fr 3.4rem; font-size: .95rem; margin: .8rem 0; }}
.peers .pr span {{ text-align: right; }} .peers .pr b {{ font-family: 'IBM Plex Mono', monospace; font-weight: 400; font-size: .86rem; }}
.peers .pr i {{ background: #cdd2dc; }} .peers .pr.me i {{ background: {NAVY}; }}
.peers .pr.me span, .peers .pr.me b {{ color: {NAVY}; font-weight: 700; }}
.hero {{ background: {NAVY}; border-radius: 10px; padding: 2rem 2.2rem; margin-top: 1.6rem; display: grid;
        grid-template-columns: 1fr auto; gap: 2.5rem; align-items: center; color: #fff; }}
.hero .k {{ font-family: 'IBM Plex Mono', monospace; font-size: .74rem; letter-spacing: .12em; text-transform: uppercase; color: #c8cfe3; }}
.hero .h {{ font-family: 'Playfair Display', Georgia, serif; font-size: 1.9rem; line-height: 1.3; margin: .6rem 0 .7rem; color: #fff; }}
.hero .h em {{ font-style: normal; color: #f6c945; }}
.hero .p {{ font-size: .95rem; color: #dfe3ef; }}
.hero .side {{ border-left: 1px solid rgba(255,255,255,.25); padding-left: 2.2rem; }}
.hero .side .v {{ font-family: 'Playfair Display', Georgia, serif; font-size: 2.1rem; margin: .4rem 0 .3rem; }}
.flow2 {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 0; padding: 1.2rem 1rem; }}
.flow2 .fs {{ padding: 0 1.2rem; border-left: 1px solid #e5e7eb; }} .flow2 .fs:first-child {{ border-left: none; }}
.flow2 .v {{ font-family: 'Playfair Display', Georgia, serif; font-size: 1.7rem; color: {NAVY}; }}
.flow2 .l {{ font-size: .88rem; color: #4b5563; line-height: 1.4; margin-top: .15rem; }}
.mrow {{ display: grid; grid-template-columns: 11rem 1fr 1fr; gap: 1.2rem; align-items: center; padding: .9rem .6rem;
        border-bottom: 1px solid #eef0f3; }}
.mrow.hd {{ font-size: .82rem; font-weight: 600; color: #374151; border-bottom: none; padding-bottom: .2rem; }}
.mrow .nm {{ font-weight: 600; color: #1f2937; font-size: .95rem; }}
.mrow .cap {{ font-family: 'IBM Plex Mono', monospace; font-size: .8rem; color: #4b5563; margin-top: .35rem; }}
.mrow.ours {{ background: #f3f7fe; border-radius: 6px; border-bottom: none; }}
.mrow.ours .nm, .mrow.ours .cap {{ color: #1d4ed8; }}
.wr {{ border: 1px solid #e5e7eb; border-left: 3px solid #6b7280; border-radius: 6px; padding: .8rem 1rem; margin-bottom: .8rem; }}
.wr .top {{ display: flex; justify-content: space-between; gap: .6rem; font-family: 'IBM Plex Mono', monospace; font-size: .8rem; color: #4b5563; }}
.wr .txt {{ font-family: 'IBM Plex Mono', monospace; font-size: .82rem; color: #1f2937; line-height: 1.55; margin: .55rem 0; }}
.wr .txt mark {{ background: none; color: inherit; text-decoration: underline; text-decoration-color: #b3261e; text-underline-offset: 3px; }}
.wr .rs {{ font-size: .9rem; color: #374151; }}
.cant div {{ font-size: .98rem; color: #1f2937; line-height: 1.5; margin: .9rem 0 0; padding-left: 1.6rem; position: relative; }}
.cant div::before {{ content: "!"; position: absolute; left: 0; top: .12rem; width: 1.05rem; height: 1.05rem; border: 1.5px solid #6b7280;
    border-radius: 50%; font-size: .7rem; font-weight: 700; color: #6b7280; display: flex; align-items: center; justify-content: center; }}
.src2 {{ display: grid; grid-template-columns: 5.5rem 1fr; gap: .5rem 1rem; font-size: .95rem; color: #1f2937; }}
.src2 span {{ font-family: 'IBM Plex Mono', monospace; font-size: .76rem; letter-spacing: .1em; text-transform: uppercase; color: {NAVY};
             padding-top: .15rem; }}
.st-key-srccard button[kind="primary"] {{ background: {NAVY}; border-color: {NAVY}; }}
@media (max-width: 900px) {{
  .rgrid, .hero {{ grid-template-columns: 1fr; }} .hero .side {{ border-left: none; padding-left: 0; }}
  .hero .h {{ font-size: 1.4rem; }} .flow2 {{ grid-template-columns: 1fr 1fr; gap: 1rem 0; }}
  .tl-row {{ grid-template-columns: 2.2rem 1fr; }} .tl-what {{ grid-column: 2; }}
  .mrow {{ grid-template-columns: 1fr; gap: .5rem; }} .mrow.hd {{ display: none; }}
  .late-h .n {{ font-size: 2.6rem; }} .late-h .s {{ font-size: 1.1rem; }} }}
.st-key-unitcard, .st-key-yearcard, .st-key-peercard {{ background: #fff; border: 1px solid #e5e7eb; border-radius: 10px;
    padding: 1.6rem 1.7rem 1.3rem; height: 100%; }}
.viz-k {{ font-family: 'IBM Plex Mono', monospace; font-size: .76rem; letter-spacing: .1em; text-transform: uppercase; color: {NAVY}; }}
.viz-h {{ font-family: 'Playfair Display', Georgia, serif; font-size: 1.5rem; font-weight: 500; color: #1f2937; line-height: 1.3;
         margin: .5rem 0 .35rem; }}
.viz-h b {{ font-weight: 600; color: #b3261e; }}
.viz-s {{ font-size: .95rem; color: #4b5563; line-height: 1.45; }}
.unit {{ display: flex; flex-wrap: wrap; gap: 7px; margin: 1.2rem 0 1rem; max-width: 30rem; }}
.unit span {{ width: 1.05rem; height: 1.05rem; border-radius: 50%; background: #3d5a9e; }}
.unit span.m {{ background: #c0392b; }}
.unit-leg {{ display: flex; flex-wrap: wrap; gap: .4rem 1.6rem; font-size: .95rem; color: #1f2937; }}
.unit-leg i {{ display: inline-block; width: .8rem; height: .8rem; border-radius: 50%; margin-right: .45rem; vertical-align: -.05rem; }}
.unit-leg b {{ font-weight: 600; }}
.viz-n {{ font-size: .85rem; color: #6b7280; margin-top: .9rem; line-height: 1.45; }}
@media (max-width: 900px) {{
  .st-key-unitcard, .st-key-yearcard, .st-key-peercard {{ padding: 1.1rem .9rem 1rem; }}
  .viz-h {{ font-size: 1.25rem; }} .unit {{ gap: 6px; }} .unit span {{ width: .95rem; height: .95rem; }} }}
@media (max-width: 900px) {{
  .block-container {{ padding: 1.4rem .8rem .8rem; }}
  .st-key-paper, .st-key-home {{ padding: 1.8rem 1.1rem 1rem; }}
  .rec-title {{ font-size: 2.1rem; }}
  .brand {{ font-size: 1.5rem; }} .brand img {{ height: 2.6rem; }}
  .rec-eyebrow {{ font-size: .78rem; }}
  .st-key-paper [role="tablist"], .st-key-paper [role="tablist"] > div {{ overflow-x: auto; }}
  .st-key-paper [role="tab"] {{ flex: 0 0 auto !important; padding: 0 .9rem !important; }}
  .cards {{ grid-template-columns: repeat(2, 1fr); gap: .8rem; }}
  .card {{ padding: 1.1rem 1rem; }} .card .num {{ font-size: 2.4rem; }}
  .facts {{ grid-template-columns: repeat(2, 1fr); gap: 1.1rem 1.4rem; }}
  .st-key-paper .stTabs [data-baseweb="tab-list"] {{ gap: 1.2rem; overflow-x: auto; }} }}
.st-key-evpick {{ display: none; }}
@media (max-width: 640px) {{
  /* top of the page */
  .brand {{ font-size: 1.3rem; gap: .6rem; }} .brand img {{ height: 2.3rem; border-radius: 9px; }}
  .st-key-search input {{ height: 2.5rem; font-size: 1rem !important; }}
  .st-key-paper, .st-key-home {{ padding: 1.6rem 1rem .9rem; margin-top: 1rem; border-radius: 12px; }}
  .rec-eyebrow {{ font-size: .8rem; letter-spacing: .03em; text-transform: none; flex-direction: column; gap: .15rem;
                 font-family: 'IBM Plex Sans', sans-serif; }}
  .rec-title {{ font-size: 1.9rem; margin: .4rem 0 1rem; }}
  .fact .k {{ font-size: .8rem; text-transform: none; letter-spacing: 0; font-family: 'IBM Plex Sans', sans-serif; font-weight: 600; }}
  .fact .v {{ font-size: 1.15rem; }}
  .rec-note {{ margin: .9rem 0 1.4rem; }}
  /* four numbers: the main finding first, the rest as compact rows */
  .cards {{ grid-template-columns: 1fr; gap: .8rem; margin-top: 1.1rem; }}
  .card {{ display: grid; grid-template-columns: 5.4rem 1fr; column-gap: .9rem; padding: 1.1rem 1rem; }}
  .card > * {{ grid-column: 2; }}
  .card .num {{ grid-column: 1; grid-row: 1 / span 6; margin: 0; font-size: 2.1rem; align-self: start; }}
  .card .lab {{ text-transform: none; letter-spacing: 0; font-family: 'IBM Plex Sans', sans-serif; font-weight: 600;
               font-size: .95rem; color: {NAVY}; margin-bottom: .3rem; }}
  .card .desc {{ font-weight: 400; }}
  .card .foot {{ padding-top: .7rem; }} .card .foot a {{ border-top: none; padding-top: 0; }}
  .card.main {{ order: -1; grid-template-columns: auto 1fr; }}
  .card.main .lab {{ grid-column: 1 / -1; color: #1d4ed8; margin-bottom: .2rem; }}
  .card.main .num {{ grid-column: 1; grid-row: auto; font-size: 3rem; align-self: center; }}
  .card.main .desc {{ grid-column: 2; align-self: center; font-weight: 600; font-size: 1.05rem; }}
  .card.main .tag, .card.main .dots, .card.main .proof, .card.main .foot {{ grid-column: 1 / -1; }}
  .legend {{ font-size: .88rem; gap: .2rem .8rem; margin-bottom: 1.2rem; }}
  /* charts and cards */
  .viz-h {{ font-size: 1.2rem; }} .c-title {{ font-size: 1.3rem; }}
  .unit-leg {{ flex-direction: column; gap: .3rem; }}
  .strip-lab {{ margin-left: 0; }} .strip-lab small {{ display: block; }}
  /* three witnesses as rows: label left, value right */
  .w3 {{ grid-template-columns: 1fr; gap: .45rem; }}
  .w3 .b {{ display: flex; justify-content: space-between; align-items: center; min-height: 0; padding: .7rem .85rem; font-size: .9rem; }}
  .w3 .b strong {{ margin: 0; font-size: 1rem; }}
  .w3cap {{ display: none; }}
  /* big tap targets */
  a.fda, .why-actions a.b1, .why-actions a.b2 {{ display: block; width: 100%; text-align: center; padding: .85rem 1rem;
      border-radius: 8px; text-decoration: none; }}
  a.fda {{ background: {NAVY}; color: #fff !important; }}
  .why-actions {{ flex-direction: column; gap: .55rem; }}
  .teaser, .ev-top {{ flex-direction: column; align-items: flex-start; }}
  /* Evidence: a picker instead of the table */
  .st-key-evpick {{ display: block; }}
  .st-key-evlist [data-testid="stDataFrame"], .st-key-evlist .lst-h {{ display: none; }}
  .st-key-evlist {{ border: none; padding: 0; background: transparent; }}
  .ev-h {{ font-size: 1.35rem; margin-top: 1rem; }} .ev-sub {{ font-size: .95rem; margin-bottom: .8rem; }}
  .st-key-whycard {{ padding: 1.1rem .9rem 1rem; }}
  .why-score .v {{ font-size: 1.7rem; }}
  .wbars {{ grid-template-columns: 6.2rem 1fr 3rem; font-size: .88rem; }}
  .sim .top {{ flex-direction: column; align-items: flex-start; gap: .35rem; }}
  /* other tabs */
  .tl-row {{ grid-template-columns: 2.2rem 1fr; gap: .2rem .8rem; margin-bottom: 1.2rem; }}
  .tl-what {{ grid-column: 2; }} .tl-leg {{ display: none; }}
  .rgrid {{ grid-template-columns: 1fr; gap: 1rem; }}
  .rcard .rtop {{ flex-direction: column; align-items: flex-start; }} .rcard .st {{ margin-left: 0; margin-right: .4rem; }}
  .late-top {{ flex-direction: column; }}
  .peers .pr {{ grid-template-columns: 6.5rem 1fr 3rem; font-size: .88rem; }}
  .hero {{ padding: 1.4rem 1.2rem; gap: 1.2rem; }} .hero .h {{ font-size: 1.3rem; }}
  .flow2 {{ grid-template-columns: 1fr; gap: .8rem 0; }} .flow2 .fs {{ border-left: none; padding: 0 .4rem; display: flex; gap: .8rem; align-items: baseline; }}
  .flow2 .v {{ min-width: 5.5rem; }}
  .src2 {{ grid-template-columns: 1fr; gap: .1rem; }} .src2 span {{ margin-top: .6rem; }}
  .pcard, .st-key-chartcard, .st-key-chartcard2, .st-key-evcard, .st-key-latecard, .st-key-calcard, .st-key-srccard,
  .st-key-unitcard, .st-key-yearcard, .st-key-peercard {{ padding: 1.1rem .9rem 1rem; }}
}}
</style>""", unsafe_allow_html=True)


# ---------------------------------------------------------------- cached data
@st.cache_data(show_spinner=False)
def has_data():
    return record.has_data()


@st.cache_data(show_spinner=False)
def build(key):
    return record.build(key)


@st.cache_data(show_spinner=False)
def search(q):
    return record.search(q)


@st.cache_data(show_spinner=False)
def reports(key, which):
    return record.reports(key, which)


@st.cache_data(show_spinner=False)
def months_by_type(key):
    return record.months_by_type(key)


@st.cache_data(show_spinner=False)
def maker_reports(maker):
    return record.maker_reports(maker)


@st.cache_data(show_spinner=False)
def makers_late(code):
    return record.makers_late(code)


@st.cache_data(show_spinner=False)
def peer_devices(code):
    return record.peer_devices(code)


@st.cache_data(show_spinner=False)
def provenance():
    return record.provenance()


def mtime(*names) -> float:
    """Latest change time of eval files, so cached results refresh when the files are updated."""
    paths = [os.path.join(ROOT, "eval", n) for n in names]   # names are paths inside eval/
    return max([os.path.getmtime(p) for p in paths if os.path.exists(p)] or [0])


@st.cache_data(show_spinner=False)
def _load_json(name, changed):
    path = os.path.join(ROOT, "eval", name)
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_json(name):
    return _load_json(name, mtime(name))


@st.cache_data(show_spinner=False)
def _gold_mistakes(changed):
    """Reports where the model and the person disagreed, so the page can show them openly."""
    import csv
    from pipeline.store import connect
    out = {"false_pos": [], "missed": 0}
    seen = set()
    con = connect()
    for name in ("hand_check/checker_A.csv", "hand_check/checker_B.csv"):
        path = os.path.join(ROOT, "eval", name)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        col = next(c for c in rows[0] if c.lower().startswith("died"))
        for r in rows:
            if r[col] not in ("0", "1") or r["report_number"] in seen:
                continue
            seen.add(r["report_number"])
            x = con.execute("SELECT hidden_death, death_excerpt, event_type, product_code, mdr_report_key, report_number "
                            "FROM reports WHERE report_number=?", (r["report_number"],)).fetchone()
            if not x or x["event_type"] == "Death":
                continue
            if x["hidden_death"] == 1 and r[col] == "0":
                out["false_pos"].append({"report_number": x["report_number"], "excerpt": x["death_excerpt"],
                                         "product_code": x["product_code"], **record.links(x)})
            elif r[col] == "1" and not x["hidden_death"]:
                out["missed"] += 1
    return out


def gold_mistakes():
    return _gold_mistakes(mtime("hand_check/checker_A.csv", "hand_check/checker_B.csv"))


def dots(right: int, total: int) -> str:
    return ('<div class="dots">' + "".join('<span></span>' if i < right else '<span class="x"></span>'
                                            for i in range(total)) + '</div>')


def esc(x) -> str:
    return html.escape(str(x if x is not None else ""))


def marked(text: str) -> str:
    return DEATH_PHRASES.sub(lambda m: f"<mark>{m.group(0)}</mark>", esc(text))


def table(rows, cols, height=380):
    if not rows:
        st.caption("No reports.")
        return
    st.dataframe(pd.DataFrame(rows)[cols + ["fda_url", "fda_api_url"]], hide_index=True, width="stretch",
                 height=min(height, 40 + 35 * len(rows)), column_config=LINKS)


def chart_cfg(c, height):
    return (c.properties(height=height).configure_view(stroke=None)
            .configure_axis(labelColor=GREY, domainColor=LINE, gridColor="#f1f5f9", labelFont="Inter", titleFont="Inter")
            .configure_legend(labelFont="Inter", labelFontSize=12, symbolType="circle"))


# ---------------------------------------------------------------- top bar
using_sample = not has_data()
key = st.query_params.get("d")
c_logo, c_search = st.columns([3, 2], vertical_alignment="center")
c_pick = c_search
c_logo.markdown(f'<div class="brand"><img src="{LOGO}" alt="">Rap Sheet</div>', unsafe_allow_html=True)
q = c_search.text_input("Search a device", placeholder="Search for a device, e.g. LIFEPAK CR2", key="search",
                        label_visibility="collapsed")
if q and not using_sample:
    matches = search(q)
    if not matches:
        c_pick.caption("No device with that name. Try the model name printed on the label.")
    else:
        pick = c_pick.selectbox("Matches", matches, label_visibility="collapsed",
                                format_func=lambda m: f"{m['brand']} · {m['manufacturer'].title()} · {m['n']:,} reports")
        key = pick["device_key"]

rec = record.sample_record() if using_sample else (build(key) if key else None)
if using_sample:
    st.warning("Showing made-up example data. Run the pipeline to load real FDA reports.")
if not rec:
    home = st.container(key="home")
    home.markdown("<div style='padding:1.5rem 0 1rem;text-align:center;color:#6b7280'>"
                "<div class='rec-title' style='margin:0 0 .6rem'>The safety record of any medical device</div>"
                "<div style='margin-top:.5rem'>Search a device above. Every number comes from the FDA's public reports "
                "and links to them.</div></div>", unsafe_allow_html=True)
    # Starting points, so a first-time visitor has something to open. Only devices that are in the data.
    examples = [(name, m[0]["device_key"]) for name in ("LIFEPAK CR2", "Zoll AED Plus", "HeartStart FRx", "DreamStation")
                for m in [search(name)] if m]
    if examples:
        links = " ".join(f'<a href="?d={esc(k)}" target="_self" style="display:inline-block;margin:.3rem;padding:.55rem 1rem;'
                         f'border:1px solid #cbd5e1;border-radius:999px;color:#111827;text-decoration:none;'
                         f'font-weight:600">{esc(n)}</a>' for n, k in examples)
        home.markdown(f"<div style='text-align:center;margin:.5rem 0 1.5rem'><div style='color:#6b7280;"
                      f"margin-bottom:.4rem'>Or open an example:</div>{links}</div>", unsafe_allow_html=True)
    st.stop()

d, t, m = rec["device"], rec["totals"], rec["manufacturer"]
maker = " ".join(w for w in d["manufacturer"].split() if not w.isdigit()).title()
explain = load_json("results/explanations.json")
gold = load_json("results/final_results.json")
reps = explain.get("reports", {})
cal = explain.get("meta", {}).get("calibration", {}).get("hand_checked", [])
top_band = cal[-1] if cal else None
clf = gold.get("methods", {}).get("classifier", {})
kw = gold.get("methods", {}).get("death word", {})
hidden_n = t["deaths_hidden"] if t.get("hidden_death_model_ran") else None
open_recalls = [r for r in rec["recalls"] if "terminated" not in (r["status"] or "").lower()]

# ---------------------------------------------------------------- device header
kind = {"MKJ": "Defibrillator (AED)", "BZD": "CPAP / BiPAP machine"}.get(d["product_code"], "Medical device")
n_rec, rising = len(rec["recalls"]), rec["warning"]["spiking_now"]
thing_plural = {"MKJ": "AED", "BZD": "CPAP"}.get(d["product_code"], "device")
facts = [
    ("Recalls", f"{len(open_recalls)} open" if open_recalls else (f"{n_rec} closed" if n_rec else "None found"),
     bool(open_recalls)),
    ("Deaths filed as something else", f"{hidden_n:,}" if hidden_n is not None else "Not scored", bool(hidden_n)),
    ("Reports", "Rising" if rising else "Steady", rising),
    ("Device type", kind, False),
]
fact_html = "".join(f'<div class="fact{" alarm" if alarm else ""}"><div class="k">{esc(k)}</div>'
                    f'<div class="v">{esc(v)}</div></div>' for k, v, alarm in facts)
paper = st.container(key="paper")
paper.markdown(f"""<div class="rec-eyebrow"><span>FDA safety record</span>
  <span>{esc(maker)} · {t['reports']:,} reports · {esc(rec['period']['first'][:7])} to {esc(rec['period']['last'][:7])}</span></div>
  <div class="rec-title">{esc(d['brand'])}</div>
  <div class="facts">{fact_html}</div>
  <div class="rec-note">From the FDA's public reports. A report is an allegation, not proof.</div>""",
               unsafe_allow_html=True)
TAB_LABELS = {"overview": "Overview", "evidence": f"Evidence :gray-background[{hidden_n or 0}]",
              "timeline": "Timeline", "recalls": "Recalls & filing", "trust": "Why trust this"}
# A link such as ?d=<device>&tab=evidence opens that tab when the page loads.
tab_over, tab_ev, tab_time, tab_rec, tab_trust = paper.tabs(
    list(TAB_LABELS.values()), default=TAB_LABELS.get(st.query_params.get("tab", ""), "Overview"))


def tab_link(tab: str, text: str, cls: str = "") -> str:
    """An HTML link that reopens this device's page on the given tab."""
    return (f'<a class="{cls}" href="?d={esc(rec["device_key"])}&tab={tab}" target="_self">{text}</a>')


# ---------------------------------------------------------------- shared pieces
def kpis():
    late = f"{m['pct_late']:g}%" if m.get("pct_late") is not None else "–"
    fda = '<span class="src fda">✓ FDA record · no model</span>'
    if clf:
        right, total = clf["true_pos"], clf["true_pos"] + clf["false_pos"]
        proof = (f'{dots(right, total)}<div class="dotlbl">{right} of {total} confirmed by a person who never saw '
                 f'the model\'s answer</div>')
    else:
        proof = ""
    fda = '<span class="tag fda">&#10003; FDA record, no model</span>'
    person = ('<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">'
              '<circle cx="12" cy="8" r="4"/><path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6"/></svg>')
    if clf:
        right, total = clf["true_pos"], clf["true_pos"] + clf["false_pos"]
        proof = (f'{dots(right, total)}<div class="proof">{right} of {total} confirmed by a person who never saw '
                 f'the model\'s answer</div>')
    else:
        proof = ""
    foot = lambda tab, where: f'<div class="foot">{tab_link(tab, f"See the reports in the {where} tab &rarr;")}</div>'
    still_open = f'<div class="open">{len(open_recalls)} still open</div>' if open_recalls else ""
    st.markdown(f"""<div class="cards">
      <div class="card"><div class="lab">Deaths</div><div class="num">{t['deaths_coded']:,}</div>
        <div class="desc">Deaths filed as deaths</div>{fda}{foot("evidence", "Evidence")}</div>
      <div class="card main"><div class="lab">Main finding</div>
        <div class="num">{hidden_n if hidden_n is not None else '&ndash;'}</div>
        <div class="desc">Deaths filed as malfunction or injury</div>
        <span class="tag model">{person} Our model, checked by hand</span>{proof}{foot("evidence", "Evidence")}</div>
      <div class="card"><div class="lab">Late filing</div><div class="num">{late}</div>
        <div class="desc">Maker's reports filed after the 30-day legal deadline</div>{fda}{foot("recalls", "Recalls &amp; filing")}</div>
      <div class="card"><div class="lab">Recalls</div><div class="num">{len(rec['recalls'])}</div>
        <div class="desc">Recalls for this model</div>{still_open}{fda}{foot("recalls", "Recalls &amp; filing")}</div>
    </div>""", unsafe_allow_html=True)


def timeline_chart(height=280, labels=True):
    if using_sample:
        months = pd.DataFrame(rec["months"]).rename(columns={"n_reports": "n"}).assign(event_type="Malfunction")
    else:
        months = pd.DataFrame(months_by_type(rec["device_key"]))
        months["event_type"] = months["event_type"].where(months["event_type"].isin(EVENT_COLORS), "Other")
    if months.empty:
        st.caption("No reports.")
        return
    months["date"] = pd.to_datetime(months["month"] + "-01")
    lo, hi = months["date"].min(), months["date"].max() + pd.offsets.MonthEnd(0)
    xs = alt.Scale(domain=[lo.isoformat(), hi.isoformat()])
    domain = [k for k in EVENT_COLORS if k in set(months["event_type"])]
    layers = [alt.Chart(months).mark_bar(width=3, cornerRadiusTopLeft=1, cornerRadiusTopRight=1).encode(
        x=alt.X("date:T", title=None, scale=xs, axis=alt.Axis(format="%Y", tickCount="year", grid=False)),
        y=alt.Y("sum(n):Q", title=None, axis=alt.Axis(tickCount=4, minExtent=120, maxExtent=120)),
        color=alt.Color("event_type:N", title=None, scale=alt.Scale(domain=domain, range=[EVENT_COLORS[k] for k in domain]),
                        legend=alt.Legend(orient="top-left", direction="horizontal")),
        order=alt.Order("event_type:N"),
        tooltip=[alt.Tooltip("date:T", title="Month", format="%b %Y"), alt.Tooltip("event_type:N", title="Filed as"),
                 alt.Tooltip("n:Q", title="Reports")])]
    recalls = pd.DataFrame([{"date": pd.to_datetime(r["date"]), "label": f"Recall {r['number']}",
                             "reason": (r["reason"] or "")[:140]}
                            for r in rec["recalls"] if r.get("date") and pd.to_datetime(r["date"]) >= lo])
    if not recalls.empty:
        layers.append(alt.Chart(recalls).mark_rule(color=BLUE, strokeDash=[6, 4], size=2).encode(
            x="date:T", tooltip=["label:N", "reason:N"]))
        if labels:
            layers.append(alt.Chart(recalls).mark_text(align="left", dx=5, dy=8, fontSize=11, color=BLUE,
                                                       fontWeight=600).encode(x="date:T", y=alt.value(0), text="label:N"))
    spikes = pd.DataFrame([{"date": pd.to_datetime(x["month"] + "-01")} for x in rec["months"] if x.get("spike")])
    if not spikes.empty:
        tot = months.groupby("date")["n"].sum().rename("n").reset_index()
        spikes = spikes.merge(tot, on="date", how="left").fillna(0)
        layers.append(alt.Chart(spikes).mark_point(shape="triangle-down", filled=True, size=60, color="#f59e0b",
                                                   yOffset=-8).encode(
            x="date:T", y="n:Q", tooltip=alt.value("Reports far above this device's usual level")))
    st.altair_chart(chart_cfg(alt.layer(*layers), height), width="stretch")

    dm = pd.DataFrame(rec["months"])
    if not dm.empty and {"n_deaths_coded", "n_deaths_hidden"} <= set(dm.columns):
        dm["date"] = pd.to_datetime(dm["month"] + "-01")
        long = pd.concat([dm[["date"]].assign(row="Filed as death", n=dm["n_deaths_coded"]),
                          dm[["date"]].assign(row="Filed as malfunction", n=dm["n_deaths_hidden"])])
        long = long[long["n"] > 0]
        if not long.empty:
            strip = alt.Chart(long).mark_circle(opacity=.85).encode(
                x=alt.X("date:T", title=None, scale=xs, axis=alt.Axis(labels=False, ticks=False, domain=False, grid=False)),
                y=alt.Y("row:N", title=None, sort=["Filed as death", "Filed as malfunction"],
                        axis=alt.Axis(minExtent=120, maxExtent=120, labelFontSize=11, labelLimit=118, domain=False, ticks=False)),
                size=alt.Size("n:Q", legend=None, scale=alt.Scale(range=[20, 160])),
                color=alt.Color("row:N", legend=None, scale=alt.Scale(domain=["Filed as death", "Filed as malfunction"],
                                                                      range=["#374151", RED])),
                tooltip=[alt.Tooltip("date:T", title="Month", format="%b %Y"), alt.Tooltip("row:N", title="Deaths"),
                         alt.Tooltip("n:Q", title="Reports")])
            st.altair_chart(chart_cfg(strip, 70), width="stretch")


AXW = 44     # width of the left axis, shared by the chart and its strips so they line up


def chart_card(rec_n_coded, rec_n_hidden):
    """Section 3, left: reports per month with recalls, unusual jumps and the two death strips."""
    if using_sample:
        months = pd.DataFrame(rec["months"]).rename(columns={"n_reports": "n"}).assign(event_type="Malfunction")
    else:
        months = pd.DataFrame(months_by_type(rec["device_key"]))
        months["event_type"] = months["event_type"].where(months["event_type"].isin(EVENT_COLORS), "Other")
    if months.empty:
        st.caption("No reports.")
        return
    months["date"] = pd.to_datetime(months["month"] + "-01")
    lo, hi = months["date"].min(), months["date"].max() + pd.offsets.MonthEnd(0)
    xs = alt.Scale(domain=[lo.isoformat(), hi.isoformat()])
    y0, y1 = months["date"].min().year, months["date"].max().year
    st.markdown(f"""<div class="c-title">Reports per month, {y0} to {y1}</div>
      <div class="c-sub">Each bar is one month of FDA reports, split by how the maker filed them. The strips below show
      when deaths were reported.</div>
      <div class="c-legend"><b>Filed as</b>
        <span><span class="sw" style="background:#c0392b"></span>Death</span>
        <span><span class="sw" style="background:#e08a1e"></span>Injury</span>
        <span><span class="sw" style="background:#cdd2dc"></span>Malfunction</span>
        <span class="sep"></span><span>&#9660; Unusual jump</span>
        <span>&#8942; Recall started</span></div>""", unsafe_allow_html=True)
    colors = {"Death": "#c0392b", "Injury": "#e08a1e", "Malfunction": "#cdd2dc", "Other": "#e5e7eb", "Not given": "#eef0f3"}
    domain = [k for k in colors if k in set(months["event_type"])]
    order = {"Death": 0, "Injury": 1, "Malfunction": 2, "Other": 3, "Not given": 4}
    months["o"] = months["event_type"].map(order)
    xaxis = alt.Axis(format="%Y", tickCount="year", grid=False, labelFontSize=12, labelColor="#4b5563", domainColor="#d1d5db")
    yaxis = alt.Axis(tickCount=4, minExtent=AXW, maxExtent=AXW, labelColor="#6b7280", gridColor="#eef0f3", domain=False, ticks=False)
    layers = [alt.Chart(months).mark_bar(width=4).encode(
        x=alt.X("date:T", title=None, scale=xs, axis=xaxis), y=alt.Y("sum(n):Q", title=None, axis=yaxis),
        color=alt.Color("event_type:N", legend=None, scale=alt.Scale(domain=domain, range=[colors[k] for k in domain])),
        order=alt.Order("o:Q"),
        tooltip=[alt.Tooltip("date:T", title="Month", format="%b %Y"), alt.Tooltip("event_type:N", title="Filed as"),
                 alt.Tooltip("n:Q", title="Reports")])]
    recalls = pd.DataFrame([{"date": pd.to_datetime(r["date"]), "num": r["number"], "reason": (r["reason"] or "")[:140]}
                            for r in rec["recalls"] if r.get("date") and pd.to_datetime(r["date"]) >= lo])
    if not recalls.empty:
        layers += [
            alt.Chart(recalls).mark_rule(color="#1f2937", strokeDash=[4, 3], size=1.4).encode(
                x="date:T", tooltip=[alt.Tooltip("num:N", title="Recall"), alt.Tooltip("reason:N", title="Reason")]),
            alt.Chart(recalls).mark_text(align="left", dx=5, fontSize=11, fontWeight=700, color=NAVY).encode(
                x="date:T", y=alt.value(-30), text=alt.value("Recall started")),
            alt.Chart(recalls).mark_text(align="left", dx=5, fontSize=11, font="IBM Plex Mono", color="#4b5563").encode(
                x="date:T", y=alt.value(-16), text="num:N")]
    spikes = pd.DataFrame([{"date": pd.to_datetime(x["month"] + "-01")} for x in rec["months"] if x.get("spike")])
    if not spikes.empty:
        tot = months.groupby("date")["n"].sum().rename("n").reset_index()
        spikes = spikes.merge(tot, on="date", how="left").fillna(0)
        layers.append(alt.Chart(spikes).mark_point(shape="triangle-down", filled=True, size=55, color="#1f2937",
                                                   yOffset=-9).encode(
            x="date:T", y="n:Q", tooltip=alt.value("Reports far above this device's usual level")))
        top = spikes.sort_values("n").tail(1)
        layers += [
            alt.Chart(top).mark_text(align="right", dx=-14, dy=-9, fontSize=11.5, fontWeight=700, color="#1f2937").encode(
                x="date:T", y="n:Q", text=alt.value("Unusual jump")),
            alt.Chart(top).mark_text(align="right", dx=-14, dy=5, fontSize=10, color="#6b7280").encode(
                x="date:T", y="n:Q", text=alt.value("far above this device's usual month"))]
    chart = (alt.layer(*layers).properties(height=300, padding={"top": 38, "left": 0, "right": 10, "bottom": 0})
             .configure_view(stroke=None).configure_axis(labelFont="IBM Plex Sans"))
    st.altair_chart(chart, width="stretch")

    dm = pd.DataFrame(rec["months"])
    if dm.empty or not {"n_deaths_coded", "n_deaths_hidden"} <= set(dm.columns):
        return
    dm["date"] = pd.to_datetime(dm["month"] + "-01")
    strips = [("n_deaths_coded", f"Filed as death &middot; {rec_n_coded:,} reports", "#6b7280", ""),
              ("n_deaths_hidden", f"Filed as malfunction, but the text describes a death &middot; {rec_n_hidden or 0:,} reports",
               "#c0392b", " red")]
    for col, label, color, cls in strips:
        pts = dm[dm[col] > 0][["date", col]].rename(columns={col: "n"})
        st.markdown(f'<div class="strip-lab{cls}">{label} <small>&nbsp;Each dot is a month; a bigger dot means more '
                    f'reports that month.</small></div>', unsafe_allow_html=True)
        base = [alt.Chart(pd.DataFrame({"date": [lo, hi]})).mark_rule(color="#eef0f3").encode(
                    x=alt.X("date:T", scale=xs, axis=None), y=alt.value(17))]
        if not pts.empty:
            base.append(alt.Chart(pts).mark_circle(color=color, opacity=.8, stroke="#fff", strokeWidth=.8).encode(
                x=alt.X("date:T", scale=xs, axis=None),
                y=alt.Y("k:N", axis=alt.Axis(labels=False, ticks=False, domain=False, title=None, minExtent=AXW, maxExtent=AXW)),
                size=alt.Size("n:Q", legend=None, scale=alt.Scale(range=[22, 95])),
                tooltip=[alt.Tooltip("date:T", title="Month", format="%b %Y"), alt.Tooltip("n:Q", title="Reports")]
            ).transform_calculate(k="'x'"))
        if not recalls.empty:
            base.append(alt.Chart(recalls).mark_rule(color="#9ca3af", strokeDash=[2, 3]).encode(x="date:T"))
        st.altair_chart(alt.layer(*base).properties(height=34, padding={"left": 0, "right": 10, "top": 0, "bottom": 0})
                        .configure_view(stroke=None), width="stretch")


def strongest_card(e: dict):
    """Section 3, right: the strongest evidence, its three witnesses and the hand-checked confidence."""
    x = reps.get(e["report_number"], {})
    passage = (x.get("passage") or e.get("excerpt") or "")
    passage = passage[:340] + "..." if len(passage) > 340 else passage
    od = bool(x.get("witnesses", {}).get("outcome_field_says_death"))
    filed = esc(e.get("coded_as") or e.get("event_type") or "Malfunction")
    if od:
        head, cap = "Three witnesses, one disagrees", ('<div class="w3cap"><div class="l">The maker\'s label</div>'
                                                      '<div class="r">These two agree: a death</div></div>')
        outcome = '<div class="b death">Outcome field<strong>Death</strong></div>'
    else:
        head, cap = "Three witnesses: only the text records the death", ""
        outcome = '<div class="b">Outcome field<strong>Not death</strong></div>'
    conf = ""
    if top_band:
        right, total = top_band["deaths"], top_band["n"]
        conf = (f'<div class="conf"><div class="h">&#9673; Confidence</div><div class="t">Reports scored this high, checked '
                f'by a person: <b>{right} of {total}</b> really described a death.</div>{dots(right, total)}</div>')
    st.markdown(f"""<span class="hl">Strongest evidence</span>
      <div class="ev-id">Report {esc(e['report_number'])} &middot; {esc(e.get('date') or e.get('date_received') or '')}</div>
      <div class="ev-q">{marked(passage)}</div>
      <div class="wh">{head}</div>
      <div class="w3"><div class="b odd">Filed as<strong>{filed}</strong></div>{outcome}
        <div class="b death">Report text<strong>Patient died</strong></div></div>{cap}
      {conf}
      <a class="fda" href="{esc(e.get('fda_url'))}" target="_blank">Open the FDA report &#8599;</a>""",
                unsafe_allow_html=True)


def evidence_card(e: dict, compact=False):
    x = reps.get(e["report_number"], {})
    passage = (x.get("passage") or e.get("excerpt") or "")
    passage = passage[:300] + "…" if compact and len(passage) > 300 else passage
    wit = x.get("witnesses", {})
    od = bool(wit.get("outcome_field_says_death"))
    witnesses = (f'<div class="w">Filed as<b>{esc(e.get("coded_as") or e.get("event_type"))}</b></div>'
                 f'<div class="w {"yes" if od else ""}">Outcome field<b>{"Death" if od else "Not death"}</b></div>'
                 f'<div class="w yes">Report text<b>Patient died</b></div>')
    prob = e.get("death_prob") or x.get("prob")
    trust = (f'<b>Confidence {min(prob, 0.999):.1%}.</b> Reports scored this high, checked by a person:'
             f'{dots(top_band["deaths"], top_band["n"])}<div class="dotlbl">{top_band["deaths"]} of {top_band["n"]} '
             f'really described a death</div>' if prob is not None and top_band else "")
    why = ""
    if not compact:
        up, down = x.get("words_up", [])[:4], x.get("words_down", [])[:2]
        scale = max([abs(w["weight"]) for w in up + down] + [0.01])
        why = '<div class="ptitle" style="margin-top:.2rem">Why the model flagged it</div>' + "".join(
            f'<div class="bar"><span class="t">{esc(w["term"])}</span><span class="b" style="width:{max(3, 50 * abs(w["weight"]) / scale):.0f}%;'
            f'background:{RED if w["weight"] > 0 else LIGHT}"></span><span class="n">{w["weight"]:+.2f}</span></div>'
            for w in up + down)
        near = x.get("similar_confirmed", [])
        if near:
            why += (f'<div class="near"><b>Similar confirmed case</b> <i>({esc(near[0]["source"])})</i><br>'
                    f'"{esc(near[0]["text"][:170])}"</div>')
    st.markdown(f"""<div class="panel">
      <div class="ptitle">Report {esc(e['report_number'])} · {esc(e.get('date') or e.get('date_received'))}</div>
      <div class="quote">{marked(passage)}</div>
      <div class="wit">{witnesses}</div>{why}
      <div class="trust">{trust}</div>
      <a class="btn" href="{esc(e.get('fda_url'))}" target="_blank">Open the FDA report ↗</a></div>""",
                unsafe_allow_html=True)


C_FILED, C_MISSED = "#3d5a9e", "#c0392b"      # checked together for colour-blind separation and contrast
FOUND_SHARE = f"{clf['recall']:.0%}" if clf else "under half"


def unit_card():
    """Every report that describes a patient death as one dot: filed as a death, or filed as something else."""
    coded, missed = t["deaths_coded"], hidden_n or 0
    total = coded + missed
    if not total:
        st.markdown('<div class="viz-k">Every death, one dot</div><div class="viz-h">No reports for this device '
                    'involve a patient death.</div>', unsafe_allow_html=True)
        return
    if missed:
        share = missed / total
        frac = ("more than 1 in 2" if share > .5 else "about 1 in 2" if share > .45 else "more than 1 in 3" if share > 1 / 3
                else "about 1 in 3" if share > .3 else "about 1 in 4" if share > .22 else "about 1 in 5" if share > .17
                else f"{share:.0%}")
        head = (f'Of {total} reports that involve a patient death, <b>{missed} were not filed as deaths</b>: {frac}.')
    else:
        head = f"All {total} reports that involve a patient death were filed as deaths."
    cap = 400                                    # keep the grid readable for devices with very many deaths
    scale = max(1, -(-total // cap))
    dots_html = ('<span></span>' * round(coded / scale)) + ('<span class="m"></span>' * round(missed / scale))
    per = "" if scale == 1 else f" Each dot stands for {scale} reports."
    st.markdown(f"""<div class="viz-k">Every death, one dot</div><div class="viz-h">{head}</div>
      <div class="unit" role="img" aria-label="{coded} filed as deaths, {missed} filed as something else">{dots_html}</div>
      <div class="unit-leg"><span><i style="background:{C_FILED}"></i><b>{coded:,}</b> filed as deaths</span>
        <span><i style="background:{C_MISSED}"></i><b>{missed:,}</b> filed as a malfunction or injury</span></div>
      <div class="viz-n">A count of the FDA's "Death" category sees only the blue dots.{per} The red count is a floor:
      our model finds about {FOUND_SHARE} of such reports, and is right 27 times in 29 when it flags one.
      A report is an allegation, not proof.</div>""", unsafe_allow_html=True)


def year_card():
    """Deaths per year: filed as deaths, with those filed as something else stacked on top."""
    dm = pd.DataFrame(rec["months"])
    if dm.empty or "n_deaths_coded" not in dm:
        st.caption("No deaths by year to show.")
        return
    dm["year"] = dm["month"].str[:4]
    by = dm.groupby("year")[["n_deaths_coded", "n_deaths_hidden"]].sum().reset_index()
    long = pd.concat([by[["year"]].assign(kind="Filed as deaths", n=by["n_deaths_coded"], o=0),
                      by[["year"]].assign(kind="Filed as a malfunction or injury", n=by["n_deaths_hidden"], o=1)])
    by["total"] = by["n_deaths_coded"] + by["n_deaths_hidden"]
    worst = by.sort_values("n_deaths_hidden").tail(1).iloc[0]
    full = by.sort_values("year")
    if rec["period"]["last"][5:7] != "12":                 # the newest year is not finished: compare full years only
        full = full[full["year"] < rec["period"]["last"][:4]]
    last2 = full.tail(2)
    recent, all_missed = int(last2["n_deaths_hidden"].sum()), int(by["n_deaths_hidden"].sum())
    head = (f"These are not old news: <b>{recent} of the {all_missed}</b> filed as something else arrived in "
            f"{' and '.join(last2['year'])}." if all_missed and recent else
            ("Deaths reported each year." if not all_missed else "When the deaths were reported."))
    st.markdown(f"""<div class="viz-k">Deaths per year</div><div class="viz-h">{head}</div>
      <div class="unit-leg" style="margin:.2rem 0 .4rem"><span><i style="background:{C_FILED};border-radius:2px"></i>Filed as deaths</span>
        <span><i style="background:{C_MISSED};border-radius:2px"></i>Filed as a malfunction or injury</span></div>""",
                unsafe_allow_html=True)
    x = alt.X("year:O", title=None, axis=alt.Axis(labelAngle=0, domain=False, ticks=False, labelFontSize=12, labelPadding=8))
    bars = alt.Chart(long).mark_bar(size=34, stroke="#fff", strokeWidth=1.5, cornerRadiusTopLeft=2, cornerRadiusTopRight=2).encode(
        x=x, y=alt.Y("n:Q", title=None, axis=alt.Axis(tickCount=4, gridColor="#eef0f3", domain=False, ticks=False, labelColor="#6b7280")),
        color=alt.Color("kind:N", legend=None, scale=alt.Scale(domain=["Filed as deaths", "Filed as a malfunction or injury"],
                                                               range=[C_FILED, C_MISSED])),
        order=alt.Order("o:Q"),
        tooltip=[alt.Tooltip("year:O", title="Year"), alt.Tooltip("kind:N", title="How it was filed"),
                 alt.Tooltip("n:Q", title="Reports describing a death")])
    labels = alt.Chart(by).mark_text(dy=-8, fontSize=12, fontWeight=600, color="#1f2937").encode(
        x=x, y="total:Q", text="total:Q")
    layers = [bars, labels]
    rc = pd.DataFrame([{"year": r_["date"][:4], "t": "Recall"} for r_ in rec["recalls"]
                       if r_.get("date") and r_["date"][:4] in set(by["year"])]).drop_duplicates()
    if not rc.empty:
        layers.append(alt.Chart(rc).mark_text(fontSize=11, fontWeight=700, color=NAVY, dy=14).encode(
            x=x, y=alt.value(248), text=alt.value("\u2691 Recall")))
    st.altair_chart(alt.layer(*layers).properties(height=250, padding={"bottom": 18, "top": 14}).configure_view(stroke=None)
                    .configure_axis(labelFont="IBM Plex Sans"), width="stretch")
    st.markdown('<div class="viz-n">Each bar counts reports that involve a patient death, by the year the FDA received '
                'them. The number on top is the total. A flag marks a year in which a recall started.</div>',
                unsafe_allow_html=True)


def peer_card():
    """This device among every other device of its type."""
    peers = pd.DataFrame(peer_devices(d["product_code"]))
    if peers.empty or len(peers) < 5:
        st.caption("Not enough devices of this type to compare.")
        return
    peers["me"] = peers["device_key"] == rec["device_key"]
    peers["name"] = peers["brand"].str.slice(0, 40)
    peers.loc[peers["me"], "name"] = d["brand"]            # the name shown in the page title, not the raw FDA spelling
    peers["maker"] = peers["manufacturer"].map(lambda x_: " ".join(w for w in x_.split() if not w.isdigit()).title())
    mine = peers[peers["me"]]
    kind_word = {"MKJ": "defibrillators", "BZD": "CPAP and BiPAP machines"}.get(d["product_code"], "devices of its type")
    if not mine.empty and mine.iloc[0]["hidden"]:
        rank = int((peers["hidden"] > mine.iloc[0]["hidden"]).sum()) + 1
        head = (f"Among {len(peers)} {kind_word}, this one has the <b>{'most' if rank == 1 else f'{rank}{chr(39)}th most' if rank > 3 else ['', '', '2nd most', '3rd most'][rank]}"
                f"</b> deaths filed as something else.")
    else:
        head = f"How this device compares with {len(peers) - 1} other {kind_word}."
    st.markdown(f"""<div class="viz-k">This device among its peers</div><div class="viz-h">{head}</div>
      <div class="viz-s">Each dot is one device model. Further right = more FDA reports. Higher = more reports that describe
      a death but were filed as something else.</div>""", unsafe_allow_html=True)
    xs = alt.X("n:Q", scale=alt.Scale(type="log"), title="Total FDA reports (each step is 10 times more)",
               axis=alt.Axis(gridColor="#eef0f3", domain=False, ticks=False, tickCount=4, labelColor="#6b7280", titleColor="#4b5563",
                             titleFontWeight="normal", titlePadding=10))
    ys = alt.Y("hidden:Q", title="Deaths filed as something else",
               axis=alt.Axis(gridColor="#eef0f3", domain=False, ticks=False, tickCount=5, labelColor="#6b7280", titleColor="#4b5563",
                             titleFontWeight="normal", titlePadding=10))
    tip = [alt.Tooltip("name:N", title="Device"), alt.Tooltip("maker:N", title="Maker"), alt.Tooltip("n:Q", title="Reports", format=","),
           alt.Tooltip("coded:Q", title="Filed as deaths"), alt.Tooltip("hidden:Q", title="Filed as something else")]
    others = alt.Chart(peers[~peers["me"]]).mark_circle(size=90, color="#9aa3b5", opacity=.75, stroke="#fff", strokeWidth=1.5).encode(
        x=xs, y=ys, tooltip=tip)
    layers = [others]
    if not mine.empty:
        layers += [alt.Chart(mine).mark_circle(size=230, color=C_MISSED, stroke="#fff", strokeWidth=2).encode(x=xs, y=ys, tooltip=tip),
                   alt.Chart(mine).mark_text(align="right", dx=-14, dy=-2, fontSize=12.5, fontWeight=700, color="#1f2937").encode(
                       x=xs, y=ys, text="name:N")]
    top = peers[~peers["me"]].sort_values("hidden").tail(2)
    top = top[top["hidden"] > 0]
    if not top.empty:
        layers.append(alt.Chart(top).mark_text(align="right", dx=-10, dy=-2, fontSize=11, color="#4b5563").encode(
            x=xs, y=ys, text="name:N"))
    st.altair_chart(alt.layer(*layers).properties(height=320).configure_view(stroke=None)
                    .configure_axis(labelFont="IBM Plex Sans", titleFont="IBM Plex Sans"), width="stretch")
    st.markdown('<div class="viz-n">Device models with at least 50 reports. More reports can simply mean more units in use, '
                'so this shows where to look, not which device is worse. Hover a dot for its name.</div>', unsafe_allow_html=True)


def why_card(e: dict):
    """Section 4: why one report was flagged, in four numbered steps."""
    x = reps.get(e["report_number"], {})
    passage = x.get("passage") or e.get("excerpt") or ""
    prob = x.get("prob") or e.get("death_prob")
    wit = x.get("witnesses", {})
    od = bool(wit.get("outcome_field_says_death"))
    filed = esc(wit.get("event_type") or e.get("event_type") or e.get("coded_as") or "Malfunction")
    denies = re.search(r"not (cause or )?contribut", passage, re.I)
    note = ('<div class="why-note">The maker also states the device did not contribute to the outcome. '
            'A report is an allegation, not proof.</div>' if denies else
            '<div class="why-note">A report is an allegation, not proof.</div>')
    outcome = ('<div class="b death">Outcome field<strong>Death</strong></div>' if od else
               '<div class="b">Outcome field<strong>Not death</strong></div>')
    wnote = ("The outcome field and the report text agree: a death. Only the maker's label says otherwise." if od else
             "Only the report text says the patient died. The two coded fields do not.")
    up, down = x.get("words_up", [])[:4], x.get("words_down", [])[:2]
    scale = max([abs(w["weight"]) for w in up + down] + [0.01])
    bars = '<div class="wbars"><div></div><div class="hd">Down &nbsp; | &nbsp; Up, toward "a death"</div><div></div>'
    for w in up + down:
        width = 86 * abs(w["weight"]) / scale
        if w["weight"] >= 0:
            bar = f'<span style="left:12%;width:{width:.0f}%;background:#1d4ed8"></span>'
        else:
            bar = f'<span style="left:{12 - min(width, 12):.0f}%;width:{min(width, 12):.0f}%;background:#9ca3af"></span>'
        bars += (f'<div class="t">{esc(w["term"])}</div><div class="track"><span class="zero"></span>{bar}</div>'
                 f'<div class="num{" neg" if w["weight"] < 0 else ""}">{w["weight"]:+.2f}</div>')
    bars += "</div>"
    sims = ""
    for n in x.get("similar_confirmed", [])[:2]:
        person = "person" in (n.get("source") or "").lower() or "hand" in (n.get("source") or "").lower()
        who = ('<span class="who person">&#9673; Confirmed by a person</span>' if person else
               '<span class="who llm">Confirmed by a large language model</span>')
        sims += (f'<div class="sim"><div class="top"><span>Report {esc(n.get("report_number", ""))}</span>{who}</div>'
                 f'<div class="txt">{marked(n.get("text", "")[:200])}</div></div>')
    conf = ""
    if top_band:
        right, total = top_band["deaths"], top_band["n"]
        conf = (f'<div class="conf"><div class="t">Reports scored this high, checked by a person: <b>{right} of {total}</b> '
                f'really described a death.</div>{dots(right, total)}</div>')
    date = esc(e.get("date_received") or e.get("date") or "")
    st.markdown(f"""<div class="why-top"><div><span class="hl">Why this was flagged</span>
        <div class="ev-id">Report {esc(e['report_number'])} &middot; {date} &middot; Filed as {filed}</div></div>
        <div class="why-score"><div class="k">Model score</div><div class="v">{min(prob or 0, 0.999):.2f}</div></div></div>
      <div class="step"><span class="n">1</span>What the report says</div>
      <div class="ev-q">{marked(passage)}</div>{note}
      <div class="step"><span class="n">2</span>Three witnesses</div>
      <div class="w3"><div class="b{"" if not od else " odd"}">Filed as<strong>{filed}</strong></div>{outcome}
        <div class="b death">Report text<strong>Patient died</strong></div></div>
      <div class="why-note">{wnote}</div>
      <div class="step"><span class="n">3</span>Words that moved the score</div>{bars}
      {'<div class="step"><span class="n">4</span>Similar reports already confirmed as deaths</div>' + sims if sims else ''}
      {conf}
      <div class="why-actions"><a class="b1" href="{esc(e.get('fda_url'))}" target="_blank">Open the FDA report &#8599;</a>
        <a class="b2" href="{esc(e.get('fda_api_url'))}" target="_blank">Raw data &#8599;</a></div>""",
                unsafe_allow_html=True)


# ---------------------------------------------------------------- Overview
with tab_over:
    kpis()
    st.markdown('<div class="legend"><span>Every number on this page opens the FDA reports behind it.</span>'
                '<span><span class="sq" style="background:#1b6b3a"></span><b style="color:#1b6b3a">Green:</b> '
                'counted straight from the FDA record.</span>'
                '<span><span class="sq" style="background:#1d4ed8"></span><b style="color:#1d4ed8">Blue:</b> '
                'found by our model and checked by a person.</span></div>', unsafe_allow_html=True)
    if not using_sample:
        left, right = st.columns([1, 1.15], gap="medium")
        with left:
            with st.container(key="unitcard"):
                unit_card()
        with right:
            with st.container(key="yearcard"):
                year_card()
        st.write("")
    left, right = st.columns([1.55, 1], gap="medium")
    with left:
        if using_sample:
            with st.container(key="chartcard"):
                chart_card(t["deaths_coded"], hidden_n)
        else:
            with st.container(key="peercard"):
                peer_card()
            st.markdown(f'<div style="margin:.7rem 0 0 .2rem">{tab_link("timeline", "See reports month by month in the Timeline tab &rarr;", "below")}</div>',
                        unsafe_allow_html=True)
    with right:
        with st.container(key="evcard"):
            if rec.get("evidence"):
                strongest_card(rec["evidence"][0])
            else:
                st.markdown('<span class="hl">Strongest evidence</span><div class="c-sub" style="margin-top:.8rem">No deaths '
                            'filed under another category were found for this device.</div>', unsafe_allow_html=True)
        if rec.get("evidence"):
            st.markdown(f'<div style="margin:.7rem 0 0 .2rem">{tab_link("evidence", f"See all {hidden_n} in the Evidence tab &rarr;", "below")}</div>',
                        unsafe_allow_html=True)
    st.caption("A report is an allegation, not proof the device caused harm. Do not stop using a device because of this page"
               + ("; keep an AED in service unless the manufacturer says otherwise." if d["product_code"] == "MKJ" else "."))

# ---------------------------------------------------------------- Evidence
with tab_ev:
    if not t.get("hidden_death_model_ran"):
        st.info("The text model has not scored this device yet.")
    elif not rec.get("evidence"):
        st.caption("No reports whose text says the patient died were filed as something else.")
    else:
        rows = reports(rec["device_key"], "deaths_hidden") if not using_sample else rec["evidence"]
        df = pd.DataFrame(rows)
        if "date_received" in df:
            df = df.sort_values("date_received", ascending=False).reset_index(drop=True)
        n = len(df)
        st.markdown(f"""<div class="ev-top"><div class="ev-h"><em>{n} report{"s" if n != 1 else ""}</em> say the patient died
            but were filed as a malfunction or injury.</div>
            <span class="tag model" style="margin-top:1.9rem">&#9673; Our model, checked by hand</span></div>
            <div class="ev-sub">Read them yourself. Pick a report on the left to see exactly why it was flagged.</div>""",
                    unsafe_allow_html=True)

        def phrase(text):
            hit = DEATH_PHRASES.search(str(text or ""))
            return f'"{hit.group(0).lower()}"' if hit else ""
        df["phrase"] = [phrase(reps.get(r, {}).get("passage") or x)
                        for r, x in zip(df["report_number"], df.get("excerpt", [""] * n))]
        left, right = st.columns([1, 1.12], gap="medium")
        with left:
            with st.container(key="evpick"):          # shown on phones only (CSS); the table is shown on wider screens
                picked = st.selectbox("Choose a report", range(n), key="evpickbox",
                                      format_func=lambda i: f"{df.iloc[i]['date_received']} · {df.iloc[i]['phrase'] or 'report'} · "
                                                            f"{(df.iloc[i]['death_prob'] or 0):.2f}")
                st.caption(f"Report {picked + 1} of {n}, newest first")
            with st.container(key="evlist"):
                st.markdown(f'<div class="lst-h"><span class="m">{n} reports &middot; newest first</span>'
                            f'<span>1 selected</span></div>', unsafe_allow_html=True)
                view = df[["date_received", "event_type", "death_prob", "phrase"]].rename(columns={
                    "date_received": "Date", "event_type": "Filed as", "death_prob": "Model score", "phrase": "Death phrase found"})
                sel = st.dataframe(view, hide_index=True, width="stretch", height=min(640, 38 + 35 * n), on_select="rerun",
                                   selection_mode="single-row", key="evsel",
                                   column_config={"Model score": st.column_config.ProgressColumn(
                                       format="%.2f", min_value=0, max_value=1)})
                st.download_button(f"Download all {n} as CSV", df.drop(columns=["phrase"]).to_csv(index=False),
                                   file_name=f"rapsheet-{rec['device_key']}-filed-as-something-else.csv", mime="text/csv")
        with right:
            chosen = sel.selection.rows[0] if sel and sel.selection.rows else picked
            with st.container(key="whycard"):
                why_card(dict(df.iloc[chosen]))
    if not using_sample:
        with st.expander(f"All {t['deaths_coded']:,} reports filed as deaths &nbsp; :green-background[✓ FDA record, no model]"):
            table(reports(rec["device_key"], "deaths_coded"), ["report_number", "date_received", "excerpt"])
        with st.expander(f"{t.get('deaths_outcome_field') or 0} reports where the FDA's two death fields disagree "
                         f"&nbsp; :blue-background[Checked by hand]"):
            st.caption("Filed as a malfunction, but the outcome field says Death. Checked by hand, only about half "
                       "describe a death, so these are not counted above.")
            table(reports(rec["device_key"], "deaths_outcome_field"), ["report_number", "date_received", "outcomes", "excerpt"])

# ---------------------------------------------------------------- Timeline
def spike_runs(events):
    """Join months flagged one after another into one 'reports rising' entry, so the list stays readable."""
    runs = []
    for e in [x for x in events if x["kind"] == "spike"]:
        month = e["date"][:7]
        y, m = int(month[:4]), int(month[5:7])
        if runs and (y * 12 + m) - runs[-1]["last_idx"] <= 3:
            runs[-1]["last_idx"], runs[-1]["last"], runs[-1]["n"] = y * 12 + m, month, runs[-1]["n"] + 1
        else:
            runs.append({"date": month, "last": month, "last_idx": y * 12 + m, "n": 1, "text": e["text"]})
    return runs


with tab_time:
    with st.container(key="chartcard2"):
        chart_card(t["deaths_coded"], hidden_n)
    bt = load_json("results/reports_rising_backtest.json")
    events = rec.get("timeline", [])
    items = []
    for e in events:
        if e["kind"] == "first_report":
            items.append((e["date"], "first", "First report", "First report in our data",
                          f"{t['reports']:,} reports in total from {rec['period']['first'][:7]} to {rec['period']['last'][:7]}.", ""))
        elif e["kind"] == "recall":
            is_open = "terminated" not in (e.get("status") or "").lower()
            lead = e.get("lead_months")
            reason = next((r["reason"] for r in rec["recalls"] if r["number"] == e.get("number")), "")
            body = esc(reason) + (f" Reports had been rising for {lead} months before this." if lead else
                                  " No rise in reports was flagged before it.")
            pill = f'<span class="st {"open" if is_open else "closed"}">{"Open" if is_open else "Closed"}</span>'
            items.append((e["date"], "recall", "Recall", f"Recall {esc(e.get('number', ''))} started {pill}", body, " box"))
    for r in spike_runs(events):
        more = f" Flagged in {r['n']} months, through {r['last']}." if r["n"] > 1 else ""
        items.append((r["date"], "rising", "Reports rising", "Reports far above this device's usual level",
                      esc(r["text"].replace("Reports rising: ", "").capitalize()) + more, ""))
    items.sort(key=lambda x: x[0])
    icons = {"first": "&#9634;", "rising": "&#8599;", "recall": "&#9873;"}
    rows_html = "".join(
        f'<div class="tl-row"><div class="tl-ic {kind}">{icons[kind]}</div>'
        f'<div class="tl-when"><div class="d">{esc(date)}</div><div class="k">{label}</div></div>'
        f'<div class="tl-what{box}"><div class="h">{head}</div><div class="p">{body}</div></div></div>'
        for date, kind, label, head, body, box in items)
    left, right = st.columns([2.2, 1], gap="medium")
    with left:
        st.markdown(f"""<div class="pcard"><div class="tl-top"><div class="c-title">What happened, in order</div>
          <div class="tl-leg"><span>&#9634; First report</span><span>&#9679; Reports rising</span><span>&#9632; Recall</span></div></div>
          <div class="tl">{rows_html}</div></div>""", unsafe_allow_html=True)
    with right:
        if bt:
            a, b = bt.get("pct_recalls_with_warning", 0), bt.get("pct_control_windows_with_warning", 0)
            st.markdown(f"""<div class="limit"><span class="hl">The honest limit</span>
              <div class="big">A rise in reports came before {a:.0f}% of {bt.get('recall_events_testable', 0)} past recalls,
              against {b:.0f}% by chance.</div>
              <div class="lb"><span>Before a recall</span><div class="tr"><i style="width:{a:.0f}%;background:#1f2937"></i></div><b>{a:.0f}%</b></div>
              <div class="lb"><span>By chance</span><div class="tr"><i style="width:{b:.0f}%;background:#9ca3af"></i></div><b>{b:.0f}%</b></div>
              <div class="end">It is a signal to look closer, <b>not a prediction.</b></div></div>""", unsafe_allow_html=True)
    with st.expander("See every event as a table"):
        st.dataframe(pd.DataFrame([{"Date": e["date"], "Event": {"recall": "Recall", "spike": "Reports rising",
                                                                 "first_report": "First report"}.get(e["kind"], e["kind"]),
                                    "Detail": e["text"]} for e in events if e["kind"] != "hidden_death"]),
                     hide_index=True, width="stretch", column_config={"Detail": st.column_config.TextColumn(width="large")})

# ---------------------------------------------------------------- Recalls & filing
FDA_TAG = '<span class="tag fda" style="margin-top:0">&#10003; FDA record, no model</span>'
with tab_rec:
    n_all, n_open = len(rec["recalls"]), len(open_recalls)
    if n_all == 0:
        head = "No recalls name this model."
    elif n_open == n_all:
        head = f"{n_all} recall{'s' if n_all != 1 else ''} name{'s' if n_all == 1 else ''} this model. " + (
            "Both are still open." if n_all == 2 else ("It is still open." if n_all == 1 else "All are still open."))
    else:
        head = f"{n_all} recall{'s' if n_all != 1 else ''} name{'s' if n_all == 1 else ''} this model. " + (
            f"{n_open} still open." if n_open else "None are open now.")
    match = rec.get("recall_match") or {}
    rule = (f"Matched because the recall's product text names the maker (\"{esc(match.get('maker_word', ''))}\") and the "
            f"model (\"{esc(match.get('phrase', ''))}\"). We read all {match.get('recalls_checked', 0):,} recall records for "
            f"this device type.") if match else ""
    st.markdown(f"""<div class="ev-top"><div class="ev-h" style="font-size:1.6rem">{head}</div>
        <span style="margin-top:1.9rem">{FDA_TAG}</span></div><div class="ev-sub">{rule}</div>""", unsafe_allow_html=True)
    words = [w for w in [match.get("phrase")] + (match.get("brand_words") or []) if w]
    cards = ""
    for r in rec["recalls"]:
        lead = next((e.get("lead_months") for e in rec.get("timeline", [])
                     if e["kind"] == "recall" and e.get("number") == r["number"]), None)
        parts = [x.strip() for x in (r["status"] or "").split(",") if x.strip()]
        is_open = "terminated" not in (r["status"] or "").lower()
        pills = "".join(f'<span class="st {"open" if (is_open and i == 0) else "closed"}">{esc(x)}</span>'
                        for i, x in enumerate(parts or ["Unknown"]))
        desc = esc(" ".join((r.get("description") or "").split())[:230])
        for w in sorted(set(words), key=len, reverse=True):
            desc = re.sub(f"({re.escape(esc(w))})", r"<mark>\1</mark>", desc, flags=re.I)
            break                                   # highlight the full model phrase once found
        api = "https://api.fda.gov/device/recall.json?search=product_res_number:%22" + esc(r["number"]) + "%22"
        cards += f"""<div class="rcard"><div class="rtop"><div class="num">{esc(r['number'])}</div><div>{pills}</div></div>
          <div class="when">Started {esc(r['date'] or '')}</div>
          <div class="lab2">FDA's reason</div><div class="why">{esc(r['reason'])}</div>
          <div class="lab2">Product description</div><div class="desc2">{desc}...</div>
          <div class="rfoot"><span>{f"Reports rose {lead} months before" if lead else "No rise in reports before it"}</span>
            <a href="{api}" target="_blank">Open the FDA recall record</a></div></div>"""
    if cards:
        st.markdown(f'<div class="rgrid">{cards}</div>', unsafe_allow_html=True)
    if not using_sample and m.get("pct_late") is not None:
        mr = pd.DataFrame(maker_reports(d["manufacturer"]))
        peers = pd.DataFrame(makers_late(d["product_code"]))
        with st.container(key="latecard"):
            st.markdown(f"""<div class="late-top"><div class="late-h"><span class="n">{m['pct_late']:g}%</span>
                <span class="s">of {esc(maker)}'s reports arrived after the 30-day legal deadline.</span></div>{FDA_TAG}</div>""",
                        unsafe_allow_html=True)
            a, b = st.columns(2, gap="large")
            with a:
                st.markdown(f'<div class="lab2">How fast {esc(maker)} reports</div>', unsafe_allow_html=True)
                if not mr.empty:
                    mr["days"] = mr["days_to_report"].clip(upper=180)
                    mr["late"] = mr["days"] > 30
                    hist = alt.Chart(mr).mark_bar().encode(
                        x=alt.X("days:Q", bin=alt.Bin(step=5), title="Days from the maker learning of an event to the FDA "
                                                                      "receiving the report (180+ grouped)"),
                        y=alt.Y("count():Q", title=None, axis=alt.Axis(tickCount=5, gridColor="#eef0f3", domain=False, ticks=False)),
                        color=alt.Color("late:N", legend=None, scale=alt.Scale(domain=[False, True], range=["#cdd2dc", "#1f2937"])))
                    line = alt.Chart(pd.DataFrame({"x": [30]}))
                    st.altair_chart((hist + line.mark_rule(color=NAVY, size=2).encode(x="x:Q")
                                     + line.mark_text(align="left", dx=7, fontSize=12, fontWeight=700, color=NAVY).encode(
                                         x="x:Q", y=alt.value(8), text=alt.value("30-day legal deadline"))
                                     + line.mark_text(align="left", dx=7, fontSize=11, color="#4b5563").encode(
                                         x="x:Q", y=alt.value(24), text=alt.value(f"Dark bars arrived late ({m['pct_late']:g}%)"))
                                     ).properties(height=250).configure_view(stroke=None)
                                    .configure_axis(labelFont="IBM Plex Mono", labelColor="#4b5563", titleFont="IBM Plex Sans",
                                                    titleColor="#4b5563", titleFontWeight="normal"), width="stretch")
            with b:
                st.markdown(f'<div class="lab2">Share filed late, other {esc(thing_plural)} makers</div>', unsafe_allow_html=True)
                if len(peers) > 1:
                    peers["name"] = peers["manufacturer"].map(lambda x: " ".join(w for w in x.split() if not w.isdigit()).title()[:28])
                    mine = peers[peers["manufacturer"] == d["manufacturer"]]
                    show = pd.concat([peers.head(6), mine]).drop_duplicates("manufacturer").sort_values("pct_late", ascending=False)
                    top = max(show["pct_late"].max(), 1)
                    bars = "".join(
                        f'<div class="pr{" me" if r_.manufacturer == d["manufacturer"] else ""}"><span>{esc(r_.name)}</span>'
                        f'<div class="tr"><i style="width:{100 * r_.pct_late / top:.0f}%"></i></div><b>{r_.pct_late:g}%</b></div>'
                        for r_ in show.itertuples())
                    rank = int((peers["pct_late"] > m["pct_late"]).sum()) + 1
                    st.markdown(f'<div class="peers">{bars}</div><div class="why-note">Lower is better. {esc(maker)} ranks '
                                f'{rank} of {len(peers)} makers with at least 20 reports (1 = files late most often).</div>',
                                unsafe_allow_html=True)

# ---------------------------------------------------------------- Why trust this
with tab_trust:
    two = gold.get("two_checkers", {})
    if clf:
        right, total = clf["true_pos"], clf["true_pos"] + clf["false_pos"]
        st.markdown(f"""<div class="hero"><div><div class="k">The one number to check</div>
            <div class="h">When this site says a death was filed as something else, a person agreed
            <em>{right} times out of {total}.</em></div>
            <div class="p">The other {total - right} are shown below. The checkers never saw the model's answer.</div></div>
          <div class="side"><div class="k">Checkers agreed</div><div class="v">{two.get('agreed', '–')} of {two.get('reports_both_labelled', '–')}</div>
            <div class="p">kappa {two.get('kappa', 0):.2f}, 200 reports read blind</div></div></div>""", unsafe_allow_html=True)
    if not using_sample:
        p = provenance()
        steps = [(f"{p['reports']:,}", "FDA reports downloaded"), ("2,675", "labelled by a large language model"),
                 ("1", "small model learns from them and reads every report"),
                 (f"{explain.get('meta', {}).get('flagged', '–')}", "reports flagged, each with reasons"),
                 (f"{gold.get('gold_reports_used', '–')}", "checked blind by a person")]
        st.markdown('<div class="pcard flow2">' + "".join(
            f'<div class="fs"><div class="v">{esc(v)}</div><div class="l">{esc(l)}</div></div>' for v, l in steps) + "</div>",
            unsafe_allow_html=True)
    a, b = st.columns([1.25, 1], gap="medium")
    with a:
        names = [("death word", "Keyword search"), ("outcome field", "FDA outcome field"), ("classifier", "Our classifier"),
                 ("large model", "Large language model, every report")]
        rows_m = ""
        for k, label in names:
            mm = gold.get("methods", {}).get(k)
            if not mm or mm.get("precision") is None:
                continue
            ours = k == "classifier"
            flagged = mm["true_pos"] + mm["false_pos"]
            c1, c2 = ("#1d4ed8", "#7c9be0") if ours else ("#9ca3af", "#c5c9d3")
            rows_m += (f'<div class="mrow{" ours" if ours else ""}"><div class="nm">{label}</div>'
                       f'<div><div class="tr"><i style="width:{100 * mm["precision"]:.0f}%;background:{c1}"></i></div>'
                       f'<div class="cap">{mm["true_pos"]} of {flagged} &middot; {mm["precision"]:.0%}</div></div>'
                       f'<div><div class="tr"><i style="width:{100 * (mm["recall"] or 0):.0f}%;background:{c2}"></i></div>'
                       f'<div class="cap">{(mm["recall"] or 0):.0%} of deaths</div></div></div>')
        st.markdown(f"""<div class="pcard"><div class="lab2">Four ways to find hidden deaths &middot; same {gold.get('gold_reports_used', '')} reports</div>
          <div class="c-title" style="font-size:1.3rem;margin:.5rem 0 1rem">As sure as the large model. Finds fewer, on purpose.</div>
          <div class="mrow hd"><div></div><div>Right when it flags</div><div>Finds this share of deaths</div></div>{rows_m}</div>""",
                    unsafe_allow_html=True)
    with b:
        with st.container(key="calcard"):
            st.markdown('<div class="lab2">When the model is sure, is it right?</div>'
                        '<div class="c-title" style="font-size:1.3rem;margin:.5rem 0 .4rem">Only the top range reaches this site.</div>',
                        unsafe_allow_html=True)
            if cal:
                cdf = pd.DataFrame([{"band": f"{c['from']:.2f}-{c['to']:.2f}", "rate": c["deaths"] / c["n"] if c["n"] else 0,
                                     "label": f"{c['deaths']} of {c['n']}", "flag": i == len(cal) - 1,
                                     "use": "Used on this site" if i == len(cal) - 1 else "Not shown"} for i, c in enumerate(cal)])
                base = alt.Chart(cdf).encode(x=alt.X("band:N", title=None, sort=None, axis=alt.Axis(labelAngle=0, domain=False, ticks=False)),
                                             y=alt.Y("rate:Q", title=None, scale=alt.Scale(domain=[0, 1.12]), axis=None))
                st.altair_chart((base.mark_bar(width={"band": .6}).encode(
                    color=alt.condition("datum.flag", alt.value("#1d4ed8"), alt.value("#cdd2dc")))
                    + base.mark_text(dy=-9, font="IBM Plex Mono", fontSize=12).encode(
                        text="label:N", color=alt.condition("datum.flag", alt.value("#1d4ed8"), alt.value("#1f2937")))
                    + base.mark_text(fontSize=11, fontWeight=600).encode(
                        y=alt.value(238), text="use:N", color=alt.condition("datum.flag", alt.value("#1d4ed8"), alt.value("#6b7280")))
                    ).properties(height=250, padding={"bottom": 4}).configure_view(stroke=None)
                    .configure_axis(labelFont="IBM Plex Mono", labelColor="#4b5563"), width="stretch")
                st.caption("Model confidence. Bar height = share that really described a death, hand-checked.")
    a, b = st.columns([1.25, 1], gap="medium")
    with a:
        mk = gold_mistakes() if not using_sample else {"false_pos": [], "missed": 0}
        if clf:
            wrong = ""
            for i, fp in enumerate(mk["false_pos"][:2], 1):
                wrong += (f'<div class="wr"><div class="top"><span>Wrong flag {i} &middot; Report {esc(fp["report_number"])}</span>'
                          f'<span class="st closed">&#10005; Not a death</span></div>'
                          f'<div class="txt">{marked((fp["excerpt"] or "")[:300])}</div>'
                          f'<div class="rs"><b>Why it was wrong:</b> the text mentions a death, but a person judged it does not '
                          f'say this patient died. <a href="{esc(fp["fda_url"])}" target="_blank">Read the report</a></div></div>')
            n_wrong = clf["false_pos"]
            st.markdown(f"""<div class="pcard"><div class="lab2">Where the model was wrong</div>
              <div class="c-title" style="font-size:1.3rem;margin:.5rem 0 .9rem">{n_wrong} of {clf['true_pos'] + n_wrong} flags
              were not deaths</div>{wrong or '<div class="why-note">The wrong flags are for a device type not loaded on this copy.</div>'}
              <div class="why-note">It also missed {clf.get('false_neg', mk['missed'])} deaths that a person found.</div></div>""",
                        unsafe_allow_html=True)
    with b:
        recall_pct = f"{clf['recall']:.0%}" if clf else "under half"
        st.markdown(f"""<div class="pcard"><div class="lab2">What this page cannot tell you</div><div class="cant">
          <div><b>A report is an allegation.</b> It is not proof that the device caused harm.</div>
          <div><b>Two device types only.</b> The model was trained and checked on AEDs and CPAP/BiPAP machines.</div>
          <div><b>Brand names vary.</b> Filers type device names by hand, so some reports may sit under another spelling.</div>
          <div><b>The model misses deaths.</b> It finds about {recall_pct} of them. It aims to be right when it flags,
          not to find every one.</div></div></div>""", unsafe_allow_html=True)
    with st.container(key="srccard"):
        a, b = st.columns([1.6, 1], vertical_alignment="center")
        a.markdown(f"""<div class="src2"><span>Data</span><div>The FDA's public openFDA API. Nothing edited.</div>
          <span>Code</span><div><a href="https://github.com/HackathonPrinceton/rapsheet" target="_blank">github.com/HackathonPrinceton/rapsheet</a>
          &middot; <a href="{METRICS}" target="_blank">full results and limits</a></div>
          <span>Rebuild</span><div><code>make pull models</code> downloads and rebuilds everything.</div></div>""",
                   unsafe_allow_html=True)
        if not using_sample:
            b.download_button("Download every report behind this page (CSV)",
                              pd.DataFrame(reports(rec["device_key"], "all")).to_csv(index=False),
                              file_name=f"rapsheet-{rec['device_key']}.csv", mime="text/csv", type="primary")
