"""The device page.  Run:  streamlit run page/app.py   (from the repo root)"""
import os
import sys

import altair as alt
import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from service import record  # noqa: E402

st.set_page_config(page_title="Rap Sheet", layout="centered")
st.title("Rap Sheet")
st.caption("The safety record of a medical device, from the FDA's public reports.")

using_sample = not record.has_data()
key = st.query_params.get("d")

q = st.text_input("Device name", placeholder="for example: HeartStart FRx")
if q and not using_sample:
    matches = record.search(q)
    if not matches:
        st.warning("No device found with that name.")
    else:
        pick = st.radio("Which one?", matches, horizontal=False,
                        format_func=lambda m: f"{m['brand']} ({m['manufacturer'].title()}, {m['n']} reports)")
        key = pick["device_key"]

rec = record.sample_record() if using_sample else (record.build(key) if key else None)
if using_sample:
    st.warning("Showing made-up example data. Run the pipeline to load real FDA reports.")
if not rec:
    st.info("Type a device name to see its record.")
    st.stop()

d, t, m = rec["device"], rec["totals"], rec["manufacturer"]
st.header(d["brand"])
st.write(f"Made by **{d['manufacturer'].title()}** · {t['reports']:,} reports "
         f"from {rec['period']['first']} to {rec['period']['last']}")

status = []
open_recalls = [r for r in rec["recalls"] if "terminated" not in (r["status"] or "").lower()]
if open_recalls:
    status.append(f"{len(open_recalls)} open recall{'s' if len(open_recalls) != 1 else ''}")
if rec["warning"]["spiking_now"]:
    status.append("reports rising")
if status:
    st.error(" · ".join(status).capitalize())

c1, c2, c3 = st.columns(3)
c1.metric("Deaths as coded by the FDA", t["deaths_coded"])
c2.metric("Deaths found in miscoded reports", t["deaths_hidden"] if t["hidden_death_model_ran"] else "not run yet")
c3.metric("Maker's reports filed late", f"{m['pct_late']:g}%" if m["pct_late"] is not None else "n/a",
          help="Share of this manufacturer's reports received after the 30-day legal deadline.")

st.subheader("Reports per month")
months = pd.DataFrame(rec["months"])
if not months.empty:
    months["kind"] = months["spike"].map({True: "Flagged spike", False: "Reports"})
    bars = alt.Chart(months).mark_bar().encode(
        x=alt.X("month:O", title=None),
        y=alt.Y("n_reports:Q", title="Reports"),
        color=alt.Color("kind:N", title=None,
                        scale=alt.Scale(domain=["Reports", "Flagged spike"], range=["#9aa5c4", "#c0392b"])),
        tooltip=["month", "n_reports", "n_deaths_coded", "n_deaths_hidden"])
    layers = [bars]
    recall_months = pd.DataFrame({"month": sorted({(r["date"] or "")[:7] for r in rec["recalls"]}
                                                   & set(months["month"]))})
    if not recall_months.empty:
        layers.append(alt.Chart(recall_months).mark_rule(color="#2f3e6b", strokeDash=[4, 3], size=2)
                      .encode(x="month:O", tooltip=alt.value("Recall")))
    st.altair_chart(alt.layer(*layers), use_container_width=True)
    st.caption("Dashed lines mark recalls. Red bars are months the early-warning model flagged.")

st.subheader("Reports that mention a death but are coded as something else")
if not rec["evidence"]:
    st.write("None found yet." if t["hidden_death_model_ran"] else "The classifier has not been run on this device yet.")
for e in rec["evidence"]:
    conf = f" · model confidence {e['death_prob']:.0%}" if e.get("death_prob") is not None else ""
    with st.expander(f"Report {e['report_number']} · coded \"{e['coded_as']}\" · {e['date']}{conf}"):
        st.write(e["excerpt"])
        st.markdown(f"[Open the original FDA report]({e['fda_url']})")

st.subheader("Recalls")
if rec["recalls"]:
    st.dataframe(pd.DataFrame(rec["recalls"])[["date", "status", "reason", "number"]], hide_index=True,
                 use_container_width=True)
else:
    st.write("No recalls matched this model.")

st.divider()
st.caption("How we know: every figure comes from openFDA device reports. A report is an allegation and does not "
           "prove the device caused harm. Do not stop using a device because of this page; check the recall "
           "notice and ask the manufacturer or your doctor.")
