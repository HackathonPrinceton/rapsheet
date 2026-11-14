"""The device page.  Run:  streamlit run page/app.py   (from the repo root)

Laid out as a case file: the counts against the device, the evidence behind each count, and why each
piece of evidence can be trusted. Built phone-first, because most people arrive from a text message.

Every number opens the exact FDA reports behind it. Every model flag says why it was raised: the
sentence it read, the words that moved the score, similar confirmed cases, and how often a score that
high has been right.
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

ACCENT, INK, MUTED, PAPER, LINE = "#b3261e", "#1d2433", "#8a8f9c", "#faf8f3", "#e3ddd0"
EVENT_COLORS = {"Death": ACCENT, "Injury": "#d9893d", "Malfunction": "#b9bdc7", "Other": "#d7d9de",
                "Not given": "#e7e8eb"}
METRICS = "https://github.com/HackathonPrinceton/rapsheet/blob/main/eval/metrics.md"
LINKS = {"fda_url": st.column_config.LinkColumn("FDA page", display_text="open"),
         "fda_api_url": st.column_config.LinkColumn("Raw data", display_text="json")}
DEATH_PHRASES = re.compile(
    r"did not survive|not survive|died|passed away|deceased|expired|not (?:be )?resuscitated|"
    r"pronounced|death|fatal|demise|succumbed", re.I)

st.set_page_config(page_title="Rap Sheet", page_icon="📋", layout="centered")

# ---------------------------------------------------------------- style
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=Inter:wght@400;500;650;800&display=swap');
html, body, [class*="css"], .stMarkdown, p, li {{ font-family: 'Inter', sans-serif; }}
#MainMenu, footer, header [data-testid="stToolbar"] {{ visibility: hidden; }}
.block-container {{ padding-top: 1.2rem; padding-bottom: 3rem; max-width: 760px; }}
.mono {{ font-family: 'IBM Plex Mono', monospace; letter-spacing: .04em; }}
.kicker {{ font-family: 'IBM Plex Mono', monospace; font-size: .72rem; letter-spacing: .14em;
          text-transform: uppercase; color: {MUTED}; }}
.brand {{ font-family: 'IBM Plex Mono', monospace; font-weight: 600; letter-spacing: .3em; font-size: .8rem;
         color: {INK}; border-bottom: 2px solid {INK}; display: inline-block; padding-bottom: 2px; }}
.title {{ font-size: 2.1rem; font-weight: 800; line-height: 1.1; margin: .5rem 0 .25rem; color: {INK}; }}
.sub {{ color: #4a5163; font-size: .95rem; }}
.stamps {{ margin: .8rem 0 .2rem; display: flex; flex-wrap: wrap; gap: .45rem; }}
.stamp {{ font-family: 'IBM Plex Mono', monospace; font-weight: 600; font-size: .78rem; letter-spacing: .08em;
         text-transform: uppercase; padding: .28rem .6rem; border: 2px solid {ACCENT}; color: {ACCENT};
         border-radius: 3px; transform: rotate(-1.5deg); background: rgba(179,38,30,.04); }}
.stamp.calm {{ border-color: {MUTED}; color: #5d6372; background: transparent; transform: none; }}
.section {{ margin: 2.2rem 0 .6rem; padding-top: .6rem; border-top: 2px solid {INK}; }}
.section h2 {{ font-size: 1.25rem; font-weight: 800; margin: .3rem 0 .2rem; color: {INK}; }}
.section p {{ color: #4a5163; font-size: .9rem; margin: 0; }}
.counts {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: .7rem; margin-top: .8rem; }}
.count {{ background: white; border: 1px solid {LINE}; border-left: 5px solid {INK}; border-radius: 6px;
         padding: .85rem 1rem .8rem; }}
.count.hot {{ border-left-color: {ACCENT}; }}
.count .n {{ font-size: 2.2rem; font-weight: 800; line-height: 1; color: {INK}; margin: .35rem 0 .3rem; }}
.count.hot .n {{ color: {ACCENT}; }}
.count .what {{ font-size: .88rem; color: {INK}; line-height: 1.35; }}
.count .how {{ font-size: .78rem; color: {MUTED}; margin-top: .45rem; line-height: 1.35; }}
.count a {{ font-size: .82rem; font-weight: 600; color: {ACCENT}; text-decoration: none; display: inline-block;
           margin-top: .5rem; }}
.card {{ background: white; border: 1px solid {LINE}; border-radius: 8px; padding: 1rem 1.05rem; margin: .8rem 0; }}
.card .head {{ display: flex; justify-content: space-between; flex-wrap: wrap; gap: .3rem; align-items: baseline; }}
.tag {{ font-family: 'IBM Plex Mono', monospace; font-size: .72rem; padding: .12rem .45rem; border-radius: 3px;
       background: #eef0f3; color: #4a5163; }}
.tag.red {{ background: rgba(179,38,30,.1); color: {ACCENT}; font-weight: 600; }}
.quote {{ font-family: 'IBM Plex Mono', monospace; font-size: .8rem; line-height: 1.55; color: #2b3242;
         background: #fbfaf7; border-left: 3px solid {LINE}; padding: .6rem .75rem; margin: .7rem 0; }}
.quote mark {{ background: rgba(179,38,30,.16); color: {ACCENT}; font-weight: 600; padding: 0 .1rem; }}
.witnesses {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: .4rem; margin: .6rem 0; }}
.w {{ border: 1px solid {LINE}; border-radius: 6px; padding: .45rem .5rem; font-size: .74rem; line-height: 1.3; }}
.w b {{ display: block; font-size: .82rem; margin-top: .15rem; }}
.w.yes b {{ color: {ACCENT}; }} .w.no b {{ color: #5d6372; }}
.why {{ font-size: .8rem; color: #4a5163; margin-top: .5rem; }}
.bar {{ display: flex; align-items: center; gap: .45rem; margin: .18rem 0; font-size: .78rem; }}
.bar .t {{ flex: 0 0 38%; text-align: right; font-family: 'IBM Plex Mono', monospace; overflow: hidden;
          white-space: nowrap; text-overflow: ellipsis; }}
.bar .b {{ height: .55rem; border-radius: 2px; }}
.trust {{ background: #f4f1ea; border-radius: 6px; padding: .55rem .7rem; font-size: .82rem; margin-top: .6rem; }}
.small {{ font-size: .78rem; color: {MUTED}; }}
a.fda {{ font-size: .82rem; font-weight: 600; color: {ACCENT}; text-decoration: none; }}
.funnel {{ display: grid; gap: .3rem; margin: .6rem 0; }}
.funnel div {{ background: {INK}; color: white; border-radius: 4px; padding: .35rem .6rem; font-size: .82rem; }}
@media (max-width: 640px) {{
  .title {{ font-size: 1.7rem; }}
  .count .n {{ font-size: 2rem; }}
  .w {{ font-size: .68rem; padding: .4rem .4rem; }} .w b {{ font-size: .74rem; }}
  .bar .t {{ flex-basis: 48%; }}
}}
</style>
""", unsafe_allow_html=True)


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


def esc(text) -> str:
    return html.escape(str(text or ""))


def marked(text: str, extra: list[str] = ()) -> str:
    """Escape a passage and highlight the phrases that state a death (and any extra terms)."""
    out = esc(text)
    terms = sorted({t for t in extra if len(t) > 3}, key=len, reverse=True)
    pattern = DEATH_PHRASES.pattern + ("|" + "|".join(re.escape(esc(t)) for t in terms) if terms else "")
    return re.sub(f"({pattern})", r"<mark>\1</mark>", out, flags=re.I)


def section(anchor: str, title: str, blurb: str = ""):
    st.markdown(f'<div class="section" id="{anchor}"><div class="kicker">{anchor.replace("-", " ")}</div>'
                f'<h2>{title}</h2>{"<p>" + blurb + "</p>" if blurb else ""}</div>', unsafe_allow_html=True)


def report_table(rows: list[dict], cols: list[str], height: int = 300):
    if not rows:
        st.write("No reports.")
        return
    st.dataframe(pd.DataFrame(rows)[cols + ["fda_url", "fda_api_url"]], hide_index=True,
                 width="stretch", height=min(height, 40 + 35 * len(rows)), column_config=LINKS)


# ---------------------------------------------------------------- which device
using_sample = not has_data()
key = st.query_params.get("d")
st.markdown('<span class="brand">RAP SHEET</span>', unsafe_allow_html=True)

if not key or using_sample:
    st.caption("The safety record of a medical device, from the FDA's public reports. "
               "Every number opens the reports it was counted from.")
    q = st.text_input("Device name", placeholder="for example: LIFEPAK CR2, HeartStart FRx, DreamStation")
    if q and not using_sample:
        matches = search(q)
        if not matches:
            st.warning("No device found with that name. Try the model name printed on the label.")
        else:
            pick = st.radio("Which one?", matches,
                            format_func=lambda m: f"{m['brand']} · {m['manufacturer'].title()} · {m['n']:,} reports")
            key = pick["device_key"]

rec = record.sample_record() if using_sample else (build(key) if key else None)
if using_sample:
    st.warning("Showing made-up example data. Run the pipeline to load real FDA reports.")
if not rec:
    st.stop()

d, t, m = rec["device"], rec["totals"], rec["manufacturer"]
maker = " ".join(w for w in d["manufacturer"].split() if not w.isdigit()).title()
explain = load_json("explanations.json")
gold = load_json("gold_results.json")
cal = explain.get("meta", {}).get("calibration", {}).get("hand_checked", [])
top_band = cal[-1] if cal else None
clf = gold.get("methods", {}).get("classifier", {})
kw = gold.get("methods", {}).get("death word", {})

# ---------------------------------------------------------------- header
kind = {"MKJ": "Automated external defibrillator", "BZD": "CPAP / BiPAP machine"}.get(d["product_code"], "Medical device")
st.markdown(
    f'<div class="kicker" style="margin-top:.9rem">FDA device record · {esc(kind)} · code {esc(d["product_code"])}</div>'
    f'<div class="title">{esc(d["brand"])}</div>'
    f'<div class="sub">Made by <b>{esc(maker)}</b> · {t["reports"]:,} reports to the FDA, '
    f'{esc(rec["period"]["first"][:7])} to {esc(rec["period"]["last"][:7])}</div>', unsafe_allow_html=True)

stamps = []
open_recalls = [r for r in rec["recalls"] if "terminated" not in (r["status"] or "").lower()]
if open_recalls:
    stamps.append(f'<span class="stamp">{len(open_recalls)} open recall{"s" if len(open_recalls) != 1 else ""}</span>')
elif rec["recalls"]:
    stamps.append(f'<span class="stamp calm">{len(rec["recalls"])} past recall{"s" if len(rec["recalls"]) != 1 else ""}</span>')
else:
    stamps.append('<span class="stamp calm">No recalls matched</span>')
if t.get("hidden_death_model_ran") and t["deaths_hidden"]:
    stamps.append(f'<span class="stamp">{t["deaths_hidden"]} deaths filed as something else</span>')
stamps.append('<span class="stamp">Reports rising</span>' if rec["warning"]["spiking_now"]
              else '<span class="stamp calm">Reports steady</span>')
st.markdown(f'<div class="stamps">{"".join(stamps)}</div>', unsafe_allow_html=True)
st.caption("A report is an allegation, not proof the device caused harm. Do not stop using a device because "
           "of this page" + ("; keep an AED in service unless the manufacturer says otherwise." if d["product_code"] == "MKJ" else "."))

# ---------------------------------------------------------------- the counts
hidden_n = t["deaths_hidden"] if t.get("hidden_death_model_ran") else None
trust_line = (f"Found by reading each report. Checked by hand: right {clf.get('true_pos', 15)} times in "
              f"{clf.get('true_pos', 15) + clf.get('false_pos', 1)}." if clf else "Found by reading each report's text.")
late = f"{m['pct_late']:g}%" if m.get("pct_late") is not None else "n/a"
st.markdown(f"""
<div class="counts">
  <div class="count">
    <div class="kicker">Count 1</div><div class="n">{t['deaths_coded']:,}</div>
    <div class="what">reports filed as a <b>death</b>.</div>
    <div class="how">Counted straight from the FDA's event type. No model.</div>
    <a href="#evidence">Check the reports ↓</a>
  </div>
  <div class="count hot">
    <div class="kicker">Count 2</div><div class="n">{hidden_n if hidden_n is not None else "–"}</div>
    <div class="what">more say the patient died, but were filed as a <b>malfunction or injury</b>.</div>
    <div class="how">{esc(trust_line)}</div>
    <a href="#evidence">See the evidence ↓</a>
  </div>
  <div class="count">
    <div class="kicker">Count 3</div><div class="n">{late}</div>
    <div class="what">of {esc(maker)}'s reports reached the FDA <b>after the 30-day legal deadline</b>.</div>
    <div class="how">Date rule: maker learned of it → FDA received it.</div>
    <a href="#late-filing">How this was worked out ↓</a>
  </div>
</div>""", unsafe_allow_html=True)

# ---------------------------------------------------------------- timeline
section("timeline", "Reports over time",
        "Each bar is a month of reports, coloured by how they were filed. Recalls and months where reports "
        "jumped are labelled on the chart.")
if using_sample:
    months = pd.DataFrame(rec["months"]).rename(columns={"n_reports": "n"}).assign(event_type="All reports")
else:
    months = pd.DataFrame(months_by_type(rec["device_key"]))
    months["event_type"] = months["event_type"].where(months["event_type"].isin(EVENT_COLORS), "Other")
if not months.empty:
    months["date"] = pd.to_datetime(months["month"] + "-01")
    domain = [k for k in EVENT_COLORS if k in set(months["event_type"])] or ["All reports"]
    top = months.groupby("date")["n"].sum().max()
    bars = alt.Chart(months).mark_bar(width=2.2).encode(
        x=alt.X("date:T", title=None, axis=alt.Axis(format="%Y", tickCount="year", grid=False)),
        y=alt.Y("sum(n):Q", title=None, axis=alt.Axis(grid=True, gridColor="#ece7dc", tickCount=4, minExtent=34)),
        color=alt.Color("event_type:N", title=None, scale=alt.Scale(domain=domain,
                        range=[EVENT_COLORS.get(k, MUTED) for k in domain]),
                        legend=alt.Legend(orient="bottom", direction="horizontal", symbolType="square")),
        order=alt.Order("event_type:N"),
        tooltip=[alt.Tooltip("date:T", title="Month", format="%b %Y"), alt.Tooltip("event_type:N", title="Filed as"),
                 alt.Tooltip("n:Q", title="Reports")])
    layers = [bars]
    first = months["date"].min()
    recalls = pd.DataFrame([{"date": pd.to_datetime(r["date"]), "label": f"Recall {r['number']}",
                             "reason": (r["reason"] or "")[:120]}
                            for r in rec["recalls"] if r.get("date") and pd.to_datetime(r["date"]) >= first])
    if not recalls.empty:
        layers += [
            alt.Chart(recalls).mark_rule(color=INK, strokeDash=[5, 3], size=1.6).encode(
                x="date:T", tooltip=["label:N", "reason:N"]),
            alt.Chart(recalls).mark_text(angle=270, align="right", baseline="bottom", dx=-2, dy=-3, fontSize=10,
                                         color=INK, font="IBM Plex Mono").encode(
                x="date:T", y=alt.value(0), text="label:N")]
    spikes = pd.DataFrame([{"date": pd.to_datetime(x["month"] + "-01")} for x in rec["months"] if x.get("spike")])
    if not spikes.empty:
        totals = months.groupby("date")["n"].sum().rename("n").reset_index()
        spikes = spikes.merge(totals, on="date", how="left").fillna(0)
        biggest = spikes.sort_values("n").tail(1).assign(
            t="reports rising now" if rec["warning"]["spiking_now"] else "jump in reports")
        layers += [
            alt.Chart(spikes).mark_point(shape="triangle-down", filled=True, size=45, color=ACCENT, yOffset=-7)
            .encode(x="date:T", y="n:Q", tooltip=alt.value("Reports far above this device's usual level")),
            alt.Chart(biggest).mark_text(align="right", dx=-7, dy=-7, fontSize=10, color=ACCENT,
                                         font="IBM Plex Mono", fontWeight="bold").encode(
                x="date:T", y="n:Q", text="t:N")]
    lo, hi = months["date"].min(), months["date"].max() + pd.offsets.MonthEnd(0)
    xscale = alt.Scale(domain=[lo.isoformat(), hi.isoformat()])
    axis_cfg = dict(labelFont="IBM Plex Mono", labelColor=MUTED, domainColor=LINE)
    st.altair_chart(alt.layer(*layers).resolve_scale(color="independent").encode(x=alt.X(scale=xscale))
                    .properties(height=230).configure_view(stroke=None).configure_axis(**axis_cfg)
                    .configure_axisY(minExtent=34).configure_legend(labelFont="Inter", labelFontSize=11),
                    width="stretch")

    # A strip under the bars: months with a death, filed as a death (ink) or found in the text (red).
    dm = pd.DataFrame(rec["months"])
    if not dm.empty and {"n_deaths_coded", "n_deaths_hidden"} <= set(dm.columns):
        dm["date"] = pd.to_datetime(dm["month"] + "-01")
        long = pd.concat([dm[["date"]].assign(row="filed as death", n=dm["n_deaths_coded"]),
                          dm[["date"]].assign(row="text says died", n=dm["n_deaths_hidden"])])
        long = long[long["n"] > 0]
        if not long.empty:
            st.markdown(f'<div class="small" style="margin:-.3rem 0 -.4rem 2.4rem">Deaths: '
                        f'<span style="color:{INK}">● filed as a death</span> &nbsp; '
                        f'<span style="color:{ACCENT}">● filed as malfunction, text says died</span></div>',
                        unsafe_allow_html=True)
            strip = alt.Chart(long).mark_circle(opacity=.85).encode(
                x=alt.X("date:T", title=None, scale=xscale,
                        axis=alt.Axis(format="%Y", tickCount="year", grid=False, domain=False)),
                y=alt.Y("row:N", title=None, sort=["filed as death", "text says died"],
                        axis=alt.Axis(labels=False, ticks=False, domain=False, minExtent=34)),
                size=alt.Size("n:Q", legend=None, scale=alt.Scale(range=[16, 110])),
                color=alt.Color("row:N", legend=None, scale=alt.Scale(
                    domain=["filed as death", "text says died"], range=[INK, ACCENT])),
                tooltip=[alt.Tooltip("date:T", title="Month", format="%b %Y"), alt.Tooltip("row:N", title="Deaths"),
                         alt.Tooltip("n:Q", title="Reports")])
            st.altair_chart(strip.properties(height=66).configure_view(stroke=None).configure_axis(**axis_cfg),
                            width="stretch")
    st.caption("▼ marks a month whose reports were far "
               "above this device's usual level. That is not a prediction of a recall: across 88 past recalls, such a "
               "jump came first 49% of the time, against 36% by chance.")

# ---------------------------------------------------------------- the evidence
section("evidence", "The evidence",
        "Reports whose text says the patient died, although they were filed as a malfunction or injury. "
        "Each one shows what the model read, why it decided, and how often it is right.")
reps = explain.get("reports", {})
evidence = rec.get("evidence", [])


def witness(label: str, value: str, yes: bool) -> str:
    return f'<div class="w {"yes" if yes else "no"}">{label}<b>{value}</b></div>'


def evidence_card(e: dict) -> str:
    x = reps.get(e["report_number"], {})
    passage = x.get("passage") or e.get("excerpt") or ""
    up = x.get("words_up", [])
    down = x.get("words_down", [])
    scale = max([abs(w["weight"]) for w in up + down] + [0.01])
    bars = "".join(
        f'<div class="bar"><span class="t">{esc(w["term"])}</span>'
        f'<span class="b" style="width:{max(4, 55 * abs(w["weight"]) / scale):.0f}%;'
        f'background:{ACCENT if w["weight"] > 0 else MUTED}"></span>'
        f'<span class="small">{"+" if w["weight"] > 0 else ""}{w["weight"]:.2f}</span></div>'
        for w in up[:4] + down[:2])
    wit = x.get("witnesses", {})
    witnesses = (witness("Filed as", esc(e.get("coded_as") or "?"), False)
                 + witness("Outcome field", "Death" if wit.get("outcome_field_says_death") else "Not death",
                           bool(wit.get("outcome_field_says_death")))
                 + witness("Report text", "Says the patient died", True))
    near = x.get("similar_confirmed", [])
    near_html = (f'<div class="why"><b>Reads like a confirmed case</b> ({esc(near[0]["source"])}): '
                 f'<span class="mono" style="font-size:.74rem">"{esc(near[0]["text"][:160])}"</span></div>') if near else ""
    prob = e.get("death_prob") or x.get("prob")
    trust = (f'Model confidence {min(prob, 0.999):.1%}. Of reports scored this high and checked by a person, '
             f'<b>{top_band["deaths"]} of {top_band["n"]}</b> really described a death.'
             if prob is not None and top_band else "")
    return f"""
<div class="card">
  <div class="head"><span class="mono" style="font-size:.8rem">Report {esc(e['report_number'])} · {esc(e.get('date'))}</span>
    <span class="tag red">filed as {esc(e.get('coded_as'))}</span></div>
  <div class="quote">{marked(passage[:520])}{'…' if len(passage) > 520 else ''}</div>
  <div class="kicker">Three witnesses</div>
  <div class="witnesses">{witnesses}</div>
  {('<div class="kicker" style="margin-top:.5rem">Why the model flagged it</div>' + bars +
    f'<div class="small" style="margin-top:.2rem">Red phrases push the model towards "the patient died", '
    f'grey ones push away. The meaning of the passage as a whole pointed the same way.</div>') if up else ''}
  {near_html}
  <div class="trust">{trust}</div>
  <div style="margin-top:.6rem"><a class="fda" href="{esc(e.get('fda_url'))}" target="_blank">Read the original FDA report ↗</a></div>
</div>"""


if not t.get("hidden_death_model_ran"):
    st.info("The text model has not scored this device yet.")
elif not evidence:
    st.write("The model found no reports like this for this device.")
else:
    st.markdown("".join(evidence_card(e) for e in evidence[:3]), unsafe_allow_html=True)
    if not using_sample:
        with st.expander(f"All {t['deaths_hidden']} flagged reports, with the model's score"):
            report_table(reports(rec["device_key"], "deaths_hidden"),
                         ["report_number", "date_received", "event_type", "death_prob", "excerpt"])
if not using_sample:
    with st.expander(f"All {t['deaths_coded']:,} reports filed as a death"):
        report_table(reports(rec["device_key"], "deaths_coded"), ["report_number", "date_received", "event_type", "excerpt"])
    outcome = t.get("deaths_outcome_field") or 0
    with st.expander(f"Where the FDA's two death fields disagree: {outcome} reports"):
        st.caption("Filed as a malfunction or injury, but the patient-outcome field says Death. A data-quality "
                   "signal, not a death count: checked by hand, only about 1 in 3 of these describe a death.")
        report_table(reports(rec["device_key"], "deaths_outcome_field"),
                     ["report_number", "date_received", "event_type", "outcomes", "excerpt"])

# ---------------------------------------------------------------- recalls
section("recalls", "Recalls", f"{len(rec['recalls'])} recall{'s' if len(rec['recalls']) != 1 else ''} name this model.")
match = rec.get("recall_match")
for r in rec["recalls"]:
    lead = next((e.get("lead_months") for e in rec.get("timeline", [])
                 if e["kind"] == "recall" and e.get("number") == r["number"]), None)
    before = (f"Reports had been rising {lead} months before." if lead else "No rise in reports was flagged in the two years before.")
    st.markdown(f"""<div class="card"><div class="head"><span class="mono" style="font-size:.8rem">{esc(r['date'])} · {esc(r['number'])}</span>
      <span class="tag {'red' if 'terminated' not in (r['status'] or '').lower() else ''}">{esc(r['status'])}</span></div>
      <div style="margin-top:.45rem;font-size:.9rem">{esc(r['reason'])}</div>
      <div class="small" style="margin-top:.4rem">{before}</div></div>""", unsafe_allow_html=True)
if match and rec["recalls"]:
    st.caption(f"How recalls were matched: the FDA lists recalls by device type, not model. We read all "
               f"{match['recalls_checked']:,} recall records for code {d['product_code']} and kept those naming both "
               f"the maker (\"{match['maker_word']}\") and the model (\"{match.get('phrase') or 'none'}\").")

# ---------------------------------------------------------------- late filing
section("late-filing", "Late filing", f"How the {late} was worked out, and how {esc(maker)} compares.")
if not using_sample:
    mr = pd.DataFrame(maker_reports(d["manufacturer"]))
    if mr.empty:
        st.write("No manufacturer reports with both dates.")
    else:
        mr["days"] = mr["days_to_report"].clip(upper=180)
        hist = alt.Chart(mr).mark_bar(color="#b9bdc7").encode(
            x=alt.X("days:Q", bin=alt.Bin(step=5), title="Days from maker learning of it to the FDA receiving it (180+ grouped)"),
            y=alt.Y("count():Q", title=None))
        rule = alt.Chart(pd.DataFrame({"x": [30]})).mark_rule(color=ACCENT, size=2).encode(x="x:Q")
        lab = alt.Chart(pd.DataFrame({"x": [30], "t": ["30-day deadline"]})).mark_text(
            align="left", dx=5, dy=-95, color=ACCENT, font="IBM Plex Mono", fontSize=11).encode(x="x:Q", text="t:N")
        st.altair_chart((hist + rule + lab).properties(height=200).configure_view(stroke=None), width="stretch")
        peers = pd.DataFrame(makers_late(d["product_code"]))
        if len(peers) > 1:
            peers["who"] = peers["manufacturer"].map(lambda x: "This maker" if x == d["manufacturer"] else "Others")
            peers["name"] = peers["manufacturer"].map(lambda x: " ".join(w for w in x.split() if not w.isdigit()).title()[:28])
            st.altair_chart(alt.Chart(peers.head(10)).mark_bar().encode(
                x=alt.X("pct_late:Q", title="% filed late"), y=alt.Y("name:N", sort="-x", title=None),
                color=alt.Color("who:N", legend=None, scale=alt.Scale(domain=["This maker", "Others"], range=[ACCENT, "#b9bdc7"])),
                tooltip=["name", "n", "pct_late"]).properties(height=alt.Step(22)).configure_view(stroke=None),
                width="stretch")
        with st.expander("The reports filed late, slowest first"):
            report_table(mr[mr["late_class"] != "on_time"].to_dict("records"),
                         ["report_number", "date_mfr_aware", "date_received", "days_to_report"])

# ---------------------------------------------------------------- why trust this
section("why-trust-this", "Why trust these numbers",
        "We checked our own model against reports read by a person who never saw its answer.")
if gold.get("methods"):
    rows = []
    names = {"death word": "Keyword search", "outcome field": "FDA outcome field", "classifier": "Our model",
             "large model": "Large AI model, every report"}
    for k, label in names.items():
        mm = gold["methods"].get(k)
        if mm and mm.get("precision") is not None:
            rows.append({"method": label, "measure": "Right when it flags", "value": mm["precision"]})
            rows.append({"method": label, "measure": "Deaths it finds", "value": mm["recall"] or 0})
    df = pd.DataFrame(rows)
    chart = alt.Chart(df).mark_bar(height=11).encode(
        y=alt.Y("method:N", sort=list(names.values()), title=None, axis=alt.Axis(labelLimit=190)),
        yOffset="measure:N",
        x=alt.X("value:Q", scale=alt.Scale(domain=[0, 1]), axis=alt.Axis(format="%", tickCount=5), title=None),
        color=alt.Color("measure:N", title=None, sort=["Right when it flags", "Deaths it finds"],
                        scale=alt.Scale(domain=["Right when it flags", "Deaths it finds"], range=[ACCENT, "#b9bdc7"]),
                        legend=alt.Legend(orient="bottom", direction="vertical", labelFont="Inter", labelFontSize=11)),
        tooltip=["method", "measure", alt.Tooltip("value:Q", format=".0%")])
    st.altair_chart(chart.properties(height=alt.Step(13)).configure_view(stroke=None), width="stretch")
    st.markdown(
        f'<div class="trust">On <b>{gold["gold_reports_used"]}</b> reports read by a person, our model was right '
        f'<b>{clf["true_pos"]} times out of {clf["true_pos"] + clf["false_pos"]}</b> when it flagged a death. '
        f'A keyword search was right <b>{kw.get("true_pos", 0)} times out of {kw.get("true_pos", 0) + kw.get("false_pos", 0)}</b>. '
        f'Our model misses about {100 - round(100 * (clf.get("recall") or 0))}% of deaths: we chose to show fewer, surer '
        f'findings. A large AI model reading every report finds more, but costs a paid call per report; ours runs free '
        f'over all {provenance()["reports"]:,} reports.</div>' if clf and not using_sample else "",
        unsafe_allow_html=True)

if cal:
    st.markdown('<div class="kicker" style="margin-top:1.2rem">When the model says it is sure, is it?</div>',
                unsafe_allow_html=True)
    cdf = pd.DataFrame([{"band": f"{b['from']:.2f}–{b['to']:.2f}", "rate": b["deaths"] / b["n"] if b["n"] else 0,
                         "label": f"{b['deaths']} of {b['n']}"} for b in cal])
    base = alt.Chart(cdf).encode(x=alt.X("band:N", title="Model score", sort=None, axis=alt.Axis(labelAngle=0)),
                                 y=alt.Y("rate:Q", title=None, scale=alt.Scale(domain=[0, 1.1]),
                                         axis=alt.Axis(format="%", tickCount=3)))
    st.altair_chart((base.mark_bar(color=INK, width={"band": 0.6})
                     + base.mark_text(dy=-8, font="IBM Plex Mono", fontSize=11, color=INK).encode(text="label:N"))
                    .properties(height=190).configure_view(stroke=None), width="stretch")
    st.caption("Share of hand-checked reports in each score range that really described a death. Only the top range "
               "is flagged on this page.")

st.markdown('<div class="kicker" style="margin-top:1.2rem">How a report becomes a finding</div>', unsafe_allow_html=True)
if not using_sample:
    p = provenance()
    steps = [f"{p['reports']:,} FDA reports downloaded (AEDs and CPAP machines, {p['first'][:4]}–{p['last'][:4]})",
             "Every report not filed as a death is split into passages and read by the model",
             "A large AI model labelled 2,122 reports; a small model learned from them",
             f"{explain.get('meta', {}).get('flagged', '?')} reports flagged, each with its reasons",
             f"{gold.get('gold_reports_used', '?')} reports checked by a person who never saw the model's answer"]
    st.markdown('<div class="funnel">' + "".join(
        f'<div style="width:{100 - 9 * i}%">{esc(s)}</div>' for i, s in enumerate(steps)) + "</div>",
        unsafe_allow_html=True)
st.markdown(
    f"- **Source.** Every report and recall is from the FDA's public openFDA API. Nothing is edited; each row links to "
    f"the FDA's own copy.\n"
    f"- **Limits.** Device names are typed by each filer, so some reports may sit under another spelling. Recalls are "
    f"matched by wording. A report is an allegation, not proof.\n"
    f"- **Reproduce it.** `make pull models` rebuilds every number from the FDA. Full results: [eval/metrics.md]({METRICS}).")

if not using_sample:
    st.download_button("Download every report behind this page (CSV)",
                       pd.DataFrame(reports(rec["device_key"], "all")).to_csv(index=False),
                       file_name=f"rapsheet-{rec['device_key']}.csv", mime="text/csv")
if key and not using_sample:
    st.markdown('<div style="margin-top:1rem"><a class="fda" href="?" target="_self">← Look up another device</a></div>',
                unsafe_allow_html=True)
