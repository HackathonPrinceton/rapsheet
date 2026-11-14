"""The device page.  Run:  streamlit run page/app.py   (from the repo root)

Built so that every number can be checked: each one opens the exact FDA reports behind it,
with links to the FDA's own page and raw data, and the rule or model that produced it.
"""
import os
import re
import sys

import altair as alt
import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from service import record  # noqa: E402

ACCENT, MUTED, INK = "#c0392b", "#9aa5c4", "#2f3e6b"
METRICS = "https://github.com/HackathonPrinceton/rapsheet/blob/main/eval/metrics.md"
EVENT_COLORS = {"Death": ACCENT, "Injury": "#e39b4a", "Malfunction": MUTED, "Other": "#c9ced9",
                "Not given": "#e4e6ec"}
LINKS = {"fda_url": st.column_config.LinkColumn("FDA page", display_text="open"),
         "fda_api_url": st.column_config.LinkColumn("Raw data", display_text="json")}

st.set_page_config(page_title="Rap Sheet", layout="centered")
st.title("Rap Sheet")
st.caption("The safety record of a medical device, from the FDA's public reports. Every number below opens the "
           "reports it was counted from.")

using_sample = not record.has_data()
key = st.query_params.get("d")

q = st.text_input("Device name", placeholder="for example: HeartStart FRx")
if q and not using_sample:
    matches = record.search(q)
    if not matches:
        st.warning("No device found with that name.")
    else:
        pick = st.radio("Which one?", matches,
                        format_func=lambda m: f"{m['brand']} ({m['manufacturer'].title()}, {m['n']} reports, "
                                              f"match score {m['score']:.2f})")
        key = pick["device_key"]

rec = record.sample_record() if using_sample else (record.build(key) if key else None)
if using_sample:
    st.warning("Showing made-up example data. Run the pipeline to load real FDA reports.")
if not rec:
    st.info("Type a device name to see its record.")
    st.stop()

d, t, m = rec["device"], rec["totals"], rec["manufacturer"]
maker = " ".join(w for w in d["manufacturer"].split() if not w.isdigit()).title()


def report_table(rows: list[dict], cols: list[str], height: int = 260):
    if not rows:
        st.write("No reports.")
        return
    st.dataframe(pd.DataFrame(rows)[cols + ["fda_url", "fda_api_url"]], hide_index=True,
                 width="stretch", height=min(height, 40 + 35 * len(rows)), column_config=LINKS)


def highlight(text: str, words: list[str]) -> str:
    for w in sorted(set(words), key=len, reverse=True):
        text = re.sub(f"({re.escape(w)})", r"**\1**", text, flags=re.I)
    return text


# ---------------------------------------------------------------- header
st.header(d["brand"])
st.write(f"Made by **{maker}** · FDA product code {d['product_code']} · {t['reports']:,} reports received "
         f"from {rec['period']['first']} to {rec['period']['last']}")
status = []
open_recalls = [r for r in rec["recalls"] if "terminated" not in (r["status"] or "").lower()]
if open_recalls:
    status.append(f"{len(open_recalls)} open recall{'s' if len(open_recalls) != 1 else ''}")
if rec["warning"]["spiking_now"]:
    status.append("reports rising")
if status:
    st.error(" · ".join(status).capitalize())

if not using_sample:
    p = record.provenance()
    st.caption(f"Scope: these numbers count only what is in our copy of the FDA data: {p['reports']:,} reports "
               f"received {p['first']} to {p['last']} and {p['recalls']:,} recall records, product codes "
               f"{', '.join(p['codes'])}, downloaded from the openFDA API.")

# ---------------------------------------------------------------- three numbers
c1, c2, c3 = st.columns(3)
c1.metric("Deaths as coded by the FDA", t["deaths_coded"],
          help="Reports where the filer chose the event type 'Death'. Counted directly; no model.")
outcome = t.get("deaths_outcome_field")
c2.metric("Coded as malfunction, outcome says death", outcome if outcome is not None else "n/a",
          help="Reports filed as a malfunction or injury, while the same report's patient-outcome field says "
               "Death. Both fields are the FDA's own; no model.")
c3.metric("Maker's reports filed late", f"{m['pct_late']:g}%" if m["pct_late"] is not None else "n/a",
          help="Share of this maker's reports (with both dates known) received more than 30 days after the maker "
               "learned of the event. 30 days is the legal deadline (21 CFR 803.50).")

if using_sample:
    st.info("Check-the-number views appear when real FDA data is loaded.")
else:
    st.subheader("Check each number")
    with st.expander(f"Deaths as coded: the {t['deaths_coded']} reports"):
        st.caption("Rule: event_type = 'Death' in the FDA record. Open any row to read the original.")
        report_table(record.reports(rec["device_key"], "deaths_coded"),
                     ["report_number", "date_received", "event_type", "excerpt"])

    with st.expander(f"Coded as malfunction, outcome says death: the {outcome or 0} reports"):
        st.caption("Rule: event_type is not 'Death', but the patient outcome field contains 'Death'. Two fields of "
                   "the same FDA record disagree. Open any row to read it.")
        report_table(record.reports(rec["device_key"], "deaths_outcome_field"),
                     ["report_number", "date_received", "event_type", "outcomes", "excerpt"])

    with st.expander("Text classifier (provisional): "
                     f"{t['deaths_hidden'] if t['hidden_death_model_ran'] else 'not run on this device yet'}"):
        st.warning("Provisional: this classifier was measured on only a few confirmed death reports, and its "
                   f"labels are not yet hand-checked. [Measured results and limits]({METRICS})")
        if not t["hidden_death_model_ran"]:
            st.write("The hidden-death classifier has not scored this device yet. When it has, every report it "
                     "flags is listed here with the model's confidence.")
        else:
            st.caption("Model: a sentence-embedding model plus logistic regression reads each report's text and "
                       "gives the probability that it says the patient died. Each row shows that probability.")
            report_table(record.reports(rec["device_key"], "deaths_hidden"),
                         ["report_number", "date_received", "event_type", "death_prob", "excerpt"])

    with st.expander(f"Late filing: how {m['pct_late']:g}% was worked out" if m["pct_late"] is not None
                     else "Late filing: not enough data"):
        mr = pd.DataFrame(record.maker_reports(d["manufacturer"]))
        if mr.empty:
            st.write("No manufacturer reports with both dates.")
        else:
            st.caption(f"Rule: days from the date {maker} learned of the event to the date the FDA received the "
                       f"report. More than 30 days is late. Based on {len(mr):,} reports with both dates; "
                       f"{m['pct_unknown']:g}% of this maker's reports are missing a date and are left out.")
            mr["days"] = mr["days_to_report"].clip(upper=180)
            hist = alt.Chart(mr).mark_bar(color=MUTED).encode(
                x=alt.X("days:Q", bin=alt.Bin(step=5), title="Days to report (180+ grouped at 180)"),
                y=alt.Y("count():Q", title="Reports"))
            line = alt.Chart(pd.DataFrame({"x": [30]})).mark_rule(color=ACCENT, size=2).encode(x="x:Q")
            label = alt.Chart(pd.DataFrame({"x": [30], "t": ["30-day legal deadline"]})).mark_text(
                align="left", dx=4, dy=-110, color=ACCENT).encode(x="x:Q", text="t:N")
            st.altair_chart(hist + line + label, width="stretch")

            peers = pd.DataFrame(record.makers_late(d["product_code"]))
            if len(peers) > 1:
                peers["who"] = peers["manufacturer"].map(lambda x: "This maker" if x == d["manufacturer"] else "Others")
                peers["name"] = peers["manufacturer"].map(
                    lambda x: " ".join(w for w in x.split() if not w.isdigit()).title())
                st.caption("Compared with every maker of this device type with at least 20 reports:")
                st.altair_chart(alt.Chart(peers).mark_bar().encode(
                    x=alt.X("pct_late:Q", title="% of reports filed late"),
                    y=alt.Y("name:N", sort="-x", title=None),
                    color=alt.Color("who:N", legend=None,
                                    scale=alt.Scale(domain=["This maker", "Others"], range=[ACCENT, MUTED])),
                    tooltip=["name", "n", "pct_late"]), width="stretch")
            st.caption("The latest reports, slowest first:")
            report_table(mr[mr["late_class"] != "on_time"].to_dict("records"),
                         ["report_number", "date_mfr_aware", "date_received", "days_to_report"])

# ---------------------------------------------------------------- timeline
st.subheader("Reports per month")
if using_sample:
    months = pd.DataFrame(rec["months"]).rename(columns={"n_reports": "n"}).assign(event_type="All reports")
else:
    months = pd.DataFrame(record.months_by_type(rec["device_key"]))
    months["event_type"] = months["event_type"].where(months["event_type"].isin(EVENT_COLORS), "Other")
if not months.empty:
    domain = [k for k in EVENT_COLORS if k in set(months["event_type"])] or ["All reports"]
    layers = [alt.Chart(months).mark_bar().encode(
        x=alt.X("month:O", title=None), y=alt.Y("sum(n):Q", title="Reports"),
        color=alt.Color("event_type:N", title="Coded as", scale=alt.Scale(
            domain=domain, range=[EVENT_COLORS.get(k, MUTED) for k in domain])),
        order=alt.Order("event_type:N"), tooltip=["month", "event_type", "n"])]
    month_set = set(months["month"])
    recall_months = pd.DataFrame({"month": sorted({(r["date"] or "")[:7] for r in rec["recalls"]} & month_set)})
    if not recall_months.empty:
        layers.append(alt.Chart(recall_months).mark_rule(color=INK, strokeDash=[4, 3], size=2)
                      .encode(x="month:O", tooltip=alt.value("Recall started")))
    spikes = pd.DataFrame({"month": [x["month"] for x in rec["months"] if x.get("spike")]})
    if not spikes.empty:
        layers.append(alt.Chart(spikes).mark_point(shape="triangle-down", color=ACCENT, size=120, filled=True, yOffset=-8)
                      .encode(x="month:O", y=alt.value(0), tooltip=alt.value("Flagged spike")))
    st.altair_chart(alt.layer(*layers), width="stretch")
    st.caption("Bars are reports by the month the FDA received them, coloured by how they were coded. Dashed lines "
               "are recalls that started in the period shown. Triangles mark months where reports rose far above this device's usual level.")

# ---------------------------------------------------------------- timeline of events
KIND = {"first_report": "First report", "spike": "Reports rising", "recall": "Recall"}
events = [e for e in rec.get("timeline", []) if e["kind"] in KIND]
if events:
    st.subheader("What happened, in order")
    st.caption("'Reports rising' marks a month whose reports were far above the device's usual level. It is not "
               "a prediction of a recall. Each recall says whether reports had been rising beforehand.")
    for e in events:
        st.markdown(f"**{e['date']}** · {KIND[e['kind']]}  \n{e['text']}")

# ---------------------------------------------------------------- hidden-death evidence
st.subheader("Reports that mention a death but are coded as something else (provisional)")
if not rec["evidence"]:
    st.write("None found yet." if t["hidden_death_model_ran"] else "The classifier has not been run on this device yet.")
for e in rec["evidence"]:
    conf = f" · model confidence {e['death_prob']:.0%}" if e.get("death_prob") is not None else ""
    with st.expander(f"Report {e['report_number']} · coded \"{e['coded_as']}\" · {e['date']}{conf}"):
        st.markdown(highlight(e["excerpt"], record.DEATH_WORDS.findall(e["excerpt"])))
        st.markdown(f"[Open the original FDA report]({e['fda_url']}) · [raw data]({e.get('fda_api_url', e['fda_url'])})")

# ---------------------------------------------------------------- recalls
st.subheader("Recalls")
match = rec.get("recall_match")
if match:
    st.caption(f"How we matched: the FDA lists recalls by device type, not by model, so we read all "
               f"{match['recalls_checked']:,} recall records for code {d['product_code']} and kept those whose "
               f"description names the maker (\"{match['maker_word']}\") and the model's name "
               f"(\"{match.get('phrase') or 'none'}\"). Generic words like 'defibrillator' are ignored, and one "
               f"recall is kept per day. Check each one below.")
if rec["recalls"]:
    for r in rec["recalls"]:
        with st.expander(f"{r['date']} · {r['number']} · {r['status']}"):
            st.markdown(f"**Reason:** {r['reason']}")
            if r.get("description"):
                words = ([match["maker_word"]] + match["brand_words"]) if match else []
                st.markdown(f"**Product as listed by the FDA:** {highlight(r['description'], words)}")
                st.caption("Bold words are the ones that matched this recall to the device.")
else:
    st.write("No recalls matched this model.")

# ---------------------------------------------------------------- how we know
st.divider()
st.subheader("How we know")
st.markdown(
    "- **Source.** Every report and recall comes from the FDA's public openFDA API (device adverse events and "
    "device recalls). Nothing is made up or edited; each row above links to the FDA's own copy.\n"
    "- **Deaths as coded** is a plain count of the FDA's event type. **Late filing** is a date rule: more than "
    "30 days between the maker learning of the event and the FDA receiving the report (21 CFR 803.50).\n"
    "- **Coded as malfunction, outcome says death** is also a plain count: two fields of the same FDA report "
    "disagree. No model is involved.\n"
    "- **The text classifier is provisional.** It reads report text for deaths filed under the wrong category. "
    f"Its measured precision and recall, and why they are not final yet, are in [eval/metrics.md]({METRICS}).\n"
    "- **Device matching** depends on the brand name each filer typed, which varies, so some reports for this "
    "device may sit under a different spelling.\n"
    "- **A report is an allegation.** It does not prove the device caused harm. Do not stop using a device because "
    "of this page; check the recall notice and ask the manufacturer or your doctor.\n"
    "- **Reproduce it.** `python -m pipeline.pull --codes MKJ` downloads the same data again from the FDA.")

if not using_sample:
    all_reports = pd.DataFrame(record.reports(rec["device_key"]))
    st.download_button("Download every report behind this page (CSV)", all_reports.to_csv(index=False),
                       file_name=f"rapsheet-{rec['device_key']}.csv", mime="text/csv")
