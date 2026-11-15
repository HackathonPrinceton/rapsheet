"""The device page.  Run:  streamlit run page/app.py   (from the repo root)

A full-width dashboard with five tabs: Overview, Evidence, Timeline, Recalls & filing, Trust.
Every number opens the FDA reports behind it, and every model flag says why it was raised.
Explanations are precomputed by pipeline/explain.py, so the page loads no model.
"""
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
from service import record  # noqa: E402

BLUE, RED, INK, GREY, LIGHT, LINE = "#2563eb", "#dc2626", "#111827", "#6b7280", "#cbd5e1", "#e5e7eb"
EVENT_COLORS = {"Death": RED, "Injury": "#f59e0b", "Malfunction": "#cbd5e1", "Other": "#e2e8f0", "Not given": "#f1f5f9"}
METRICS = "https://github.com/HackathonPrinceton/rapsheet/blob/main/eval/metrics.md"
LINKS = {"fda_url": st.column_config.LinkColumn("FDA page", display_text="open ↗"),
         "fda_api_url": st.column_config.LinkColumn("Raw", display_text="json")}
DEATH_PHRASES = re.compile(r"did not survive|not survive|died|passed away|deceased|expired|not (?:be )?resuscitated|"
                           r"pronounced|death|fatal|demise|succumbed", re.I)

st.set_page_config(page_title="Rap Sheet", page_icon="◉", layout="wide")
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"], p, li, label {{ font-family: 'Inter', sans-serif; }}
#MainMenu, footer, header [data-testid="stToolbar"] {{ visibility: hidden; }}
.block-container {{ padding: 1rem 2.2rem 2rem; max-width: 100%; }}
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
  .block-container {{ padding: .8rem 1rem; }} }}
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
def provenance():
    return record.provenance()


@st.cache_data(show_spinner=False)
def load_json(name):
    path = os.path.join(ROOT, "eval", name)
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@st.cache_data(show_spinner=False)
def gold_mistakes():
    """Reports where the model and the person disagreed, so the page can show them openly."""
    import csv
    from pipeline.store import connect
    out = {"false_pos": [], "missed": 0}
    con = connect()
    for name in ("gold_A.csv", "gold_B.csv"):
        path = os.path.join(ROOT, "eval", name)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        col = next(c for c in rows[0] if c.lower().startswith("died"))
        for r in rows:
            if r[col] not in ("0", "1"):
                continue
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
c_logo, c_search, c_pick = st.columns([1.1, 2.4, 2.5])
c_logo.markdown('<div class="logo"><span class="dot"></span>Rap Sheet</div>', unsafe_allow_html=True)
q = c_search.text_input("Search a device", placeholder="Search a device: LIFEPAK CR2, HeartStart FRx, DreamStation",
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
    st.markdown("<div style='padding:4rem 0;text-align:center;color:#6b7280'>"
                "<div style='font-size:1.6rem;font-weight:800;color:#111827'>The safety record of any medical device</div>"
                "<div style='margin-top:.5rem'>Search a device above. Every number comes from the FDA's public reports "
                "and links to them.</div></div>", unsafe_allow_html=True)
    st.stop()

d, t, m = rec["device"], rec["totals"], rec["manufacturer"]
maker = " ".join(w for w in d["manufacturer"].split() if not w.isdigit()).title()
explain = load_json("explanations.json")
gold = load_json("gold_results.json")
reps = explain.get("reports", {})
cal = explain.get("meta", {}).get("calibration", {}).get("hand_checked", [])
top_band = cal[-1] if cal else None
clf = gold.get("methods", {}).get("classifier", {})
kw = gold.get("methods", {}).get("death word", {})
hidden_n = t["deaths_hidden"] if t.get("hidden_death_model_ran") else None
open_recalls = [r for r in rec["recalls"] if "terminated" not in (r["status"] or "").lower()]

# ---------------------------------------------------------------- device header
kind = {"MKJ": "Defibrillator (AED)", "BZD": "CPAP / BiPAP machine"}.get(d["product_code"], "Medical device")
pills = []
if open_recalls:
    pills.append(f'<span class="pill red">● {len(open_recalls)} open recall{"s" if len(open_recalls) != 1 else ""}</span>')
if hidden_n:
    pills.append(f'<span class="pill red">{hidden_n} deaths filed as something else</span>')
pills.append('<span class="pill red">Reports rising</span>' if rec["warning"]["spiking_now"]
             else '<span class="pill">Reports steady</span>')
pills.append(f'<span class="pill blue">{esc(kind)}</span>')
st.markdown(f"""<div class="devhead"><div><div class="devname">{esc(d['brand'])}</div>
  <div class="devsub">{esc(maker)} · {t['reports']:,} FDA reports · {esc(rec['period']['first'][:7])} to {esc(rec['period']['last'][:7])}</div></div>
  <div class="pills">{''.join(pills)}</div></div>""", unsafe_allow_html=True)

tab_over, tab_ev, tab_time, tab_rec, tab_trust = st.tabs(
    ["Overview", f"Evidence ({hidden_n or 0})", "Timeline", "Recalls & filing", "Why trust this"])


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
    st.markdown(f"""<div class="kpis">
      <div class="kpi"><div class="v">{t['deaths_coded']:,}</div><div class="l">Deaths filed as deaths</div>{fda}</div>
      <div class="kpi red"><div class="v">{hidden_n if hidden_n is not None else '–'}</div>
        <div class="l">Deaths filed as malfunction or injury</div>
        <span class="src model">◎ Our model · checked by hand</span>{proof}</div>
      <div class="kpi"><div class="v">{late}</div><div class="l">Maker's reports filed after the 30-day deadline</div>{fda}</div>
      <div class="kpi"><div class="v">{len(rec['recalls'])}</div><div class="l">Recalls for this model ({len(open_recalls)} open)</div>{fda}</div>
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


# ---------------------------------------------------------------- Overview
with tab_over:
    kpis()
    st.markdown('<div class="note" style="margin:-.4rem 0 .8rem">Every number on this page opens the FDA reports behind it. '
                'Green = counted straight from the FDA record. Blue = found by our model and checked by a person.</div>',
                unsafe_allow_html=True)
    left, right = st.columns([2.1, 1], gap="large")
    with left:
        st.markdown('<div class="ptitle">Reports per month · recalls in blue · ▼ unusual jump</div>', unsafe_allow_html=True)
        timeline_chart(260, labels=False)
    with right:
        st.markdown('<div class="ptitle">Strongest evidence</div>', unsafe_allow_html=True)
        if rec.get("evidence"):
            evidence_card(rec["evidence"][0], compact=True)
            st.caption(f"See all {hidden_n} in the Evidence tab.")
        else:
            st.caption("No deaths filed under another category were found for this device.")
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
        left, right = st.columns([1.15, 1.35], gap="large")
        with left:
            st.markdown(f'<div class="ptitle">{len(df)} reports: text says the patient died, filed as something else</div>',
                        unsafe_allow_html=True)
            def around(text):
                text = str(text or "")
                hit = DEATH_PHRASES.search(text)
                if not hit:
                    return text[:110]
                a = max(0, hit.start() - 45)
                return ("…" if a else "") + text[a:hit.end() + 60] + "…"
            df["excerpt"] = df["excerpt"].map(around)
            view = df[["date_received", "event_type", "death_prob", "excerpt"]].rename(columns={
                "date_received": "Date", "event_type": "Filed as", "death_prob": "Confidence", "excerpt": "What it says"})
            sel = st.dataframe(view, hide_index=True, width="stretch", height=520, on_select="rerun",
                               selection_mode="single-row",
                               column_config={"Confidence": st.column_config.ProgressColumn(format="%.2f", min_value=0, max_value=1),
                                              "What it says": st.column_config.TextColumn(width="large")})
            st.caption("Click a row to see why it was flagged.")
        with right:
            chosen = sel.selection.rows[0] if sel and sel.selection.rows else 0
            evidence_card(dict(df.iloc[chosen]))
    if not using_sample:
        with st.expander(f"All {t['deaths_coded']:,} reports filed as deaths"):
            table(reports(rec["device_key"], "deaths_coded"), ["report_number", "date_received", "excerpt"])
        with st.expander(f"{t.get('deaths_outcome_field') or 0} reports where the FDA's two death fields disagree"):
            st.caption("Filed as a malfunction, but the outcome field says Death. Checked by hand, only about 1 in 3 "
                       "describe a death, so these are not counted above.")
            table(reports(rec["device_key"], "deaths_outcome_field"), ["report_number", "date_received", "outcomes", "excerpt"])

# ---------------------------------------------------------------- Timeline
with tab_time:
    st.markdown('<div class="ptitle">Reports per month, by how they were filed</div>', unsafe_allow_html=True)
    timeline_chart(360)
    st.caption("Dots: deaths per month. ▼ a month far above this device's usual level, which came before 49% of 88 "
               "past recalls, against 36% by chance. Not a prediction.")
    events = [e for e in rec.get("timeline", []) if e["kind"] in ("recall", "spike")]
    if events:
        st.dataframe(pd.DataFrame([{"Date": e["date"], "Event": "Recall" if e["kind"] == "recall" else "Reports jumped",
                                    "Detail": e["text"]} for e in events]), hide_index=True, width="stretch",
                     height=min(320, 40 + 35 * len(events)), column_config={"Detail": st.column_config.TextColumn(width="large")})

# ---------------------------------------------------------------- Recalls & filing
with tab_rec:
    st.markdown(f'<div class="ptitle">{len(rec["recalls"])} recalls name this model</div>', unsafe_allow_html=True)
    if rec["recalls"]:
        cols = st.columns(min(3, len(rec["recalls"])))
        for i, r in enumerate(rec["recalls"]):
            lead = next((e.get("lead_months") for e in rec.get("timeline", [])
                         if e["kind"] == "recall" and e.get("number") == r["number"]), None)
            status = "red" if "terminated" not in (r["status"] or "").lower() else ""
            cols[i % len(cols)].markdown(f"""<div class="rc"><div class="top"><span>{esc(r['date'])} · {esc(r['number'])}</span>
              <span class="pill {status}">{esc(r['status'])}</span></div><div class="r">{esc(r['reason'])}</div>
              <div class="f">{f"Reports rose {lead} months before" if lead else "No rise in reports before it"}</div></div>""",
                                         unsafe_allow_html=True)
    else:
        st.caption("No recalls matched this model.")
    st.write("")
    if not using_sample:
        mr = pd.DataFrame(maker_reports(d["manufacturer"]))
        peers = pd.DataFrame(makers_late(d["product_code"]))
        a, b = st.columns(2, gap="large")
        with a:
            st.markdown(f'<div class="ptitle">How fast {esc(maker)} reports to the FDA</div>', unsafe_allow_html=True)
            if not mr.empty:
                mr["days"] = mr["days_to_report"].clip(upper=180)
                hist = alt.Chart(mr).mark_bar(color=LIGHT, cornerRadiusTopLeft=2, cornerRadiusTopRight=2).encode(
                    x=alt.X("days:Q", bin=alt.Bin(step=5), title="Days to report (180+ grouped)"),
                    y=alt.Y("count():Q", title="Reports"))
                rule = alt.Chart(pd.DataFrame({"x": [30], "t": ["30-day legal deadline"]}))
                st.altair_chart(chart_cfg(hist + rule.mark_rule(color=RED, size=2).encode(x="x:Q")
                                          + rule.mark_text(align="left", dx=6, y=10, color=RED, fontWeight=600).encode(
                                              x="x:Q", text="t:N"), 260), width="stretch")
        with b:
            st.markdown('<div class="ptitle">Share filed late, compared with other makers</div>', unsafe_allow_html=True)
            if len(peers) > 1:
                peers["who"] = peers["manufacturer"].map(lambda x: "This maker" if x == d["manufacturer"] else "Others")
                peers["name"] = peers["manufacturer"].map(lambda x: " ".join(w for w in x.split() if not w.isdigit()).title()[:30])
                st.altair_chart(chart_cfg(alt.Chart(peers.head(10)).mark_bar(cornerRadiusEnd=3).encode(
                    x=alt.X("pct_late:Q", title="% of reports filed late"), y=alt.Y("name:N", sort="-x", title=None),
                    color=alt.Color("who:N", legend=None, scale=alt.Scale(domain=["This maker", "Others"], range=[BLUE, LIGHT])),
                    tooltip=["name", "n", "pct_late"]), 260), width="stretch")

# ---------------------------------------------------------------- Why trust this
with tab_trust:
    if not using_sample:
        p = provenance()
        steps = [(f"{p['reports']:,}", "FDA reports downloaded"),
                 ("2,122", "labelled by a large AI model"),
                 ("1 small model", "learns from them, reads every report"),
                 (f"{explain.get('meta', {}).get('flagged', '–')}", "reports flagged, each with reasons"),
                 (f"{gold.get('gold_reports_used', '–')}", "checked blind by a person")]
        st.markdown('<div class="ptitle">How a report becomes a finding</div><div class="flow">' + "".join(
            f'<div class="step"><div class="v">{esc(v)}</div><div class="l">{esc(l)}</div></div>' for v, l in steps)
            + "</div>", unsafe_allow_html=True)
        st.write("")
        mk = gold_mistakes()
        if mk["false_pos"]:
            fp = mk["false_pos"][0]
            st.markdown(f"""<div class="miss"><div class="h">Where the model was wrong, shown openly</div>
              <div class="q">Of {len(mk["false_pos"]) + (clf.get("true_pos", 0) if clf else 0)} flags a person checked,
              this one was judged <b>not</b> a patient death. The text says the customer's husband died, but not that he
              was the patient:<br><i>"{marked((fp["excerpt"] or "")[:260])}…"</i></div>
              <div class="dotlbl">It also missed {mk["missed"]} deaths that a person found. We show fewer, surer findings
              rather than more, less certain ones. <a href="{esc(fp["fda_url"])}" target="_blank">Read this report ↗</a></div></div>""",
                        unsafe_allow_html=True)
            st.write("")
    a, b = st.columns(2, gap="large")
    with a:
        st.markdown('<div class="ptitle">Four ways to find hidden deaths, scored by a person</div>', unsafe_allow_html=True)
        if gold.get("methods"):
            names = {"death word": "Keyword search", "outcome field": "FDA outcome field", "classifier": "Our model",
                     "large model": "Large AI model"}
            rows = []
            for k, label in names.items():
                mm = gold["methods"].get(k)
                if mm and mm.get("precision") is not None:
                    rows += [{"method": label, "measure": "Right when it flags", "value": mm["precision"]},
                             {"method": label, "measure": "Share of deaths found", "value": mm["recall"] or 0}]
            st.altair_chart(chart_cfg(alt.Chart(pd.DataFrame(rows)).mark_bar(cornerRadiusEnd=3, height=12).encode(
                y=alt.Y("method:N", sort=list(names.values()), title=None, axis=alt.Axis(labelLimit=200)),
                yOffset=alt.YOffset("measure:N", sort=["Right when it flags", "Share of deaths found"]),
                x=alt.X("value:Q", scale=alt.Scale(domain=[0, 1]), axis=alt.Axis(format="%"), title=None),
                color=alt.Color("measure:N", title=None, sort=["Right when it flags", "Share of deaths found"],
                                scale=alt.Scale(domain=["Right when it flags", "Share of deaths found"], range=[BLUE, LIGHT]),
                                legend=alt.Legend(orient="bottom")),
                tooltip=["method", "measure", alt.Tooltip("value:Q", format=".0%")]), 250), width="stretch")
            if clf:
                st.markdown(f'<div class="trust">Our model was right <b>{clf["true_pos"]} of {clf["true_pos"] + clf["false_pos"]}</b> '
                            f'times it flagged a death; keyword search <b>{kw.get("true_pos", 0)} of '
                            f'{kw.get("true_pos", 0) + kw.get("false_pos", 0)}</b>. It finds about half the deaths, on purpose: '
                            f'fewer, surer findings.</div>', unsafe_allow_html=True)
    with b:
        st.markdown('<div class="ptitle">When the model is sure, is it right?</div>', unsafe_allow_html=True)
        if cal:
            cdf = pd.DataFrame([{"band": f"{c['from']:.2f}–{c['to']:.2f}", "rate": c["deaths"] / c["n"] if c["n"] else 0,
                                 "label": f"{c['deaths']} of {c['n']}", "flag": i == len(cal) - 1} for i, c in enumerate(cal)])
            base = alt.Chart(cdf).encode(x=alt.X("band:N", title="Model confidence", sort=None, axis=alt.Axis(labelAngle=0)),
                                         y=alt.Y("rate:Q", title="Really a death", scale=alt.Scale(domain=[0, 1.12]),
                                                 axis=alt.Axis(format="%", tickCount=3)))
            st.altair_chart(chart_cfg(base.mark_bar(width={"band": .55}, cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
                color=alt.condition("datum.flag", alt.value(BLUE), alt.value(LIGHT)))
                + base.mark_text(dy=-9, fontWeight=600, color=INK).encode(text="label:N"), 250), width="stretch")
            st.caption("Hand-checked reports in each confidence range. Only the blue range is flagged on this site.")
    st.markdown(f'<div class="note">Source: the FDA\'s public openFDA API; nothing edited. Device names are typed by filers, '
                f'so some reports may sit under another spelling. Rebuild everything with <code>make pull models</code>. '
                f'<a href="{METRICS}" target="_blank">Full results and limits ↗</a></div>', unsafe_allow_html=True)
    if not using_sample:
        st.download_button("Download every report behind this page (CSV)",
                           pd.DataFrame(reports(rec["device_key"], "all")).to_csv(index=False),
                           file_name=f"rapsheet-{rec['device_key']}.csv", mime="text/csv")
