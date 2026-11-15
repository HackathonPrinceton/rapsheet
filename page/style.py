"""Rap Sheet's look, shared by every page (device page, patient page, Ask page) so they always match.

    import style
    style.page_config("Rap Sheet")   # optional: title and icon
    style.inject()                   # once, near the top of the page

Colours, fonts and card styles live here only. Change them here, never in a page.
"""
import base64
import os

import streamlit as st

BLUE, RED, INK, GREY, LIGHT, LINE = "#2563eb", "#dc2626", "#111827", "#6b7280", "#cbd5e1", "#e5e7eb"
EVENT_COLORS = {"Death": RED, "Injury": "#f59e0b", "Malfunction": "#cbd5e1", "Other": "#e2e8f0", "Not given": "#f1f5f9"}
NAVY, CLIP, PAPER_BG = "#2f3e6b", "#c0392b", "#eef0f5"

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")
with open(os.path.join(ASSETS, "logo.svg"), "rb") as _f:
    LOGO = "data:image/svg+xml;base64," + base64.b64encode(_f.read()).decode()


def page_config(title: str = "Rap Sheet", layout: str = "wide"):
    st.set_page_config(page_title=title, page_icon=os.path.join(ASSETS, "logo.png"), layout=layout)


def base_css() -> str:
    """The base layer: fonts, spacing and the shared components (pills, cards, quotes, witnesses, dots)."""
    return f"""
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
</style>"""


def paper_css() -> str:
    """The paper-record look: navy band, white paper card with the red clip, serif titles, tab segments."""
    return f"""
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
</style>"""


def inject():
    st.markdown(base_css(), unsafe_allow_html=True)
    st.markdown(paper_css(), unsafe_allow_html=True)


def patient_css() -> str:
    """Extra pieces for the patient page: a narrow phone-first column, action card, numbered steps."""
    return f"""<style>
.block-container {{ max-width: 620px !important; }}
.brand {{ font-size: 1.6rem !important; }} .brand img {{ height: 2.8rem !important; }}
.p-action {{ border: 1px solid #f2c9c3; background: #fdf3f1; border-radius: 12px; padding: 1rem 1.1rem; margin: .4rem 0 .8rem; }}
.p-action.calm {{ border-color: #c7d2fe; background: #f5f7ff; }}
.p-action .k {{ font-family: 'IBM Plex Mono', monospace; font-size: .72rem; letter-spacing: .1em; color: {CLIP}; }}
.p-action.calm .k {{ color: {NAVY}; }}
.p-action .t {{ font-family: 'Playfair Display', Georgia, serif; font-size: 1.45rem; line-height: 1.25; color: #1f2937; margin-top: .3rem; }}
.p-k {{ font-family: 'IBM Plex Mono', monospace; font-size: .72rem; letter-spacing: .1em; color: #4b5563; margin: .9rem 0 .5rem; }}
.p-step {{ display: flex; gap: .8rem; align-items: center; border: 1px solid {LINE}; border-radius: 12px;
          padding: .75rem .9rem; margin-bottom: .5rem; min-height: 44px; font-size: 1rem; line-height: 1.35; }}
.p-step .n {{ flex: none; width: 1.65rem; height: 1.65rem; border-radius: 50%; background: {NAVY}; color: #fff;
             font-weight: 700; font-size: .85rem; display: flex; align-items: center; justify-content: center; }}
.p-box {{ background: {PAPER_BG}; border-radius: 12px; padding: .8rem .9rem; font-size: .95rem; margin-top: .4rem; }}
.p-recall {{ border: 1px solid {LINE}; border-radius: 12px; padding: .9rem 1rem; margin-bottom: .6rem; }}
.p-recall .top {{ display: flex; justify-content: space-between; font-family: 'IBM Plex Mono', monospace;
                 font-size: .72rem; letter-spacing: .08em; color: #4b5563; }}
.p-recall .open {{ color: {CLIP}; font-weight: 600; font-family: 'IBM Plex Sans', sans-serif; font-size: .8rem; letter-spacing: 0; }}
.p-recall .r {{ font-size: 1rem; font-weight: 500; margin: .25rem 0 0; line-height: 1.45; }}
.p-recall a {{ display: block; margin-top: .6rem; padding-top: .6rem; border-top: 1px dashed #d1d5db;
              font-size: .9rem; font-weight: 600; color: {NAVY}; text-decoration: none; }}
.p-deaths {{ border: 1px solid #c7d2fe; background: #f5f7ff; border-radius: 12px; padding: .9rem 1rem; }}
.p-deaths .big {{ font-family: 'Playfair Display', Georgia, serif; font-size: 1.9rem; }}
.p-split {{ display: flex; height: 10px; border-radius: 999px; overflow: hidden; margin: .6rem 0 .5rem; }}
.p-quote {{ border: 1px solid {LINE}; border-radius: 12px; padding: .7rem .9rem; margin-bottom: .5rem; font-size: .95rem; line-height: 1.45; }}
.p-quote mark {{ background: #fdecea; color: {CLIP}; font-weight: 600; padding: 0 .1rem; }}
.p-trust {{ display: flex; gap: .7rem; align-items: center; margin-top: .8rem; color: {NAVY}; font-size: .88rem; }}
.p-trust .d {{ display: grid; grid-template-columns: repeat(10, 8px); gap: 3px; flex: none; }}
.p-trust .d span {{ width: 8px; height: 8px; border-radius: 50%; background: #1d4ed8; }}
.p-trust .d span.x {{ background: #fff; box-shadow: inset 0 0 0 1.5px #1d4ed8; }}
.p-small {{ font-size: .82rem; color: #4b5563; margin-top: .5rem; }}
.p-explain {{ font-size: 1rem; line-height: 1.55; margin: .6rem 0; color: #1f2937; }}
.p-term {{ background: #fdecea; color: {CLIP}; font-weight: 700; padding: 0 .3rem; border-radius: 4px; }}
.p-recall .lbl {{ font-family: 'IBM Plex Mono', monospace; font-size: .68rem; letter-spacing: .08em;
                 text-transform: uppercase; color: #4b5563; margin-top: .6rem; }}
.p-recall .num {{ margin-top: .6rem; padding-top: .6rem; border-top: 1px dashed #d1d5db; font-size: .92rem; color: {NAVY}; }}
.st-key-home {{ padding: 1.6rem 1.4rem !important; }}
.p-notfound {{ background: #fff7ed; border: 1px solid #fed7aa; color: #7c2d12; border-radius: 10px;
              padding: .75rem .9rem; font-size: .95rem; line-height: 1.45; margin-top: .4rem; }}
.st-key-home .stButton button {{ justify-content: flex-start; text-align: left; border-radius: 10px; }}
/* Three short tabs: always side by side, sharing the width, even on a phone. */
.st-key-paper [role="tab"] {{ flex: 1 1 0 !important; min-width: 0 !important; padding: 0 .3rem !important; }}
.st-key-paper [role="tab"] p {{ font-size: .95rem !important; white-space: nowrap; }}
.st-key-paper .stTabs [data-baseweb="tab-list"] {{ overflow-x: visible !important; gap: 0 !important; }}
@media (max-width: 900px) {{
  .st-key-paper [role="tab"] {{ flex: 1 1 0 !important; padding: 0 .3rem !important; }}
  .st-key-paper .stTabs [data-baseweb="tab-list"] {{ gap: 0 !important; overflow-x: visible !important; }}
}}
</style>"""
