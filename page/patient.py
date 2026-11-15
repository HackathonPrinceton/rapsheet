"""The patient page.  Run:  streamlit run page/patient.py   (from the repo root)

What a patient, or the person in charge of an AED, sees after texting a photo of their device. It answers
three questions in plain words: is it OK to use, what is wrong, and what have others reported. Phone first,
three tabs, no jargon. Same data and same look as the device page for investigators (page/app.py).

INVESTIGATOR_URL (env) is where "Read the reports" points; it defaults to the same host's root.
"""
import difflib
import html
import os
import re
import sys

import streamlit as st

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)
from pipeline.store import connect  # noqa: E402
from service import record  # noqa: E402

import style  # noqa: E402

style.page_config("Rap Sheet · Your device", layout="centered")
style.inject()
st.markdown(style.patient_css(), unsafe_allow_html=True)

INVESTIGATOR = os.environ.get("INVESTIGATOR_URL", "/").rstrip("/") + "/"
KIND = {"MKJ": ("defibrillator (AED)", "AED"), "BZD": ("CPAP / BiPAP breathing machine", "machine")}
MONTHS = "January February March April May June July August September October November December".split()


@st.cache_data(show_spinner=False)
def build(key):
    return record.build(key)


@st.cache_data(show_spinner=False)
def all_devices() -> list[dict]:
    """Every device family people can pick, biggest first. The picker filters as you type, ignoring capitals."""
    rows = connect().execute(
        "SELECT device_key, MAX(brand) brand, MAX(manufacturer) maker, COUNT(*) n FROM reports "
        "WHERE brand != '' AND device_key NOT LIKE '%--unknown%' AND device_key NOT LIKE 'unknown--%' "
        "GROUP BY device_key HAVING n >= 30 ORDER BY n DESC").fetchall()
    return [dict(r) for r in rows]


def esc(x) -> str:
    return html.escape(str(x if x is not None else ""))


def tidy_maker(name: str) -> str:
    return " ".join(w for w in (name or "").split() if not w.isdigit()).title()


def month(iso: str) -> str:
    try:
        return f"{MONTHS[int(iso[5:7]) - 1]} {iso[:4]}"
    except (ValueError, IndexError, TypeError):
        return esc(iso)


def clean_name(brand: str) -> str:
    """'LIFEPAK(R) CR2 DEFIBRILLATOR' -> 'LIFEPAK CR2 DEFIBRILLATOR'."""
    return re.sub(r"\s+", " ", re.sub(r"\((r|tm|c)\)|[®™©]|=", "", brand or "", flags=re.I)).strip()


def label(dev: dict) -> str:
    return f"{clean_name(dev['brand'])}  ·  {tidy_maker(dev.get('maker') or dev.get('manufacturer'))}"


@st.cache_data(show_spinner=False)
def vocabulary() -> list[str]:
    """Every word that appears in a device or maker name, for spelling correction."""
    words = set()
    for dev in all_devices():
        words.update(re.findall(r"[a-z0-9]+", f"{dev['brand']} {dev['maker']}".lower()))
    return sorted(w for w in words if len(w) > 1)


def find(q: str) -> tuple[list[dict], str]:
    """Search as typed; if nothing matches, correct each word to the closest known word and try again.
    Returns the matches and the corrected text (empty when no correction was needed)."""
    found = record.search(q)
    if found:
        return found, ""
    vocab = vocabulary()
    fixed = []
    for w in re.findall(r"[a-z0-9]+", q.lower()):
        close = difflib.get_close_matches(w, vocab, n=1, cutoff=0.7)
        fixed.append(close[0] if close else w)
    corrected = " ".join(fixed)
    return (record.search(corrected), corrected) if corrected != q.lower().strip() else ([], "")


# ---------------------------------------------------------------- which device
st.markdown(f'<div class="brand"><img src="{style.LOGO}" alt="">Rap Sheet</div>', unsafe_allow_html=True)
devices = all_devices()
by_key = {d["device_key"]: d for d in devices}
key = st.query_params.get("d")
if key not in by_key and not (key and build(key)):
    key = None

if not key:
    start = st.container(key="home")
    start.markdown('<div class="p-k" style="margin-top:0">FIND YOUR DEVICE</div>'
                   '<div class="p-small" style="margin-top:0">Type the name printed on the front of your device. '
                   'Capitals and small typos are fine.</div>', unsafe_allow_html=True)
    q = start.text_input("Your device", placeholder="For example: LIFEPAK CR2, DreamStation, AED Plus",
                         label_visibility="collapsed")
    if q.strip():
        matches, corrected = find(q)
        if corrected:
            start.markdown(f'<div class="p-small">Showing results for <b>{esc(corrected)}</b></div>',
                           unsafe_allow_html=True)
        if not matches:
            start.markdown('<div class="p-notfound">We couldn\'t find that device. Try the brand or model name '
                           'printed on the front. We cover defibrillators (AEDs) and CPAP machines so far.</div>',
                           unsafe_allow_html=True)
        for i, m in enumerate(matches):
            if start.button(label(m), key=f"pick{i}", use_container_width=True):
                st.query_params["d"] = m["device_key"]
                st.rerun()
    else:
        start.markdown('<div class="p-small">We cover defibrillators (AEDs) and CPAP machines so far.</div>',
                       unsafe_allow_html=True)
    st.stop()

rec = build(key)
d, t = rec["device"], rec["totals"]
maker = tidy_maker(d["manufacturer"])
kind, thing = KIND.get(d["product_code"], ("medical device", "device"))
is_aed = d["product_code"] == "MKJ"
open_recalls = [r for r in rec["recalls"] if "terminated" not in (r["status"] or "").lower()]
numbers = [r["number"] for r in open_recalls]

paper = st.container(key="paper")
paper.markdown(f"""<div class="rec-eyebrow"><span>Your device</span><span>{esc(maker)}</span></div>
  <div class="rec-title">{esc(clean_name(d['brand']))}</div>
  <div class="rec-note">A {esc(kind)} · <a href="?" target="_self">Pick another device</a></div>""",
               unsafe_allow_html=True)

tab_ok, tab_wrong, tab_safe = paper.tabs(["Is it OK to use?", "What's wrong?", "Stay safe"])

# ---------------------------------------------------------------- is it OK to use?
with tab_ok:
    if open_recalls:
        n = len(open_recalls)
        head = ("The maker has found a problem with some of these devices." if n == 1
                else f"The maker has found {n} problems with some of these devices.")
        quote = " or ".join(numbers)
        ask = f'"Is my device affected by recall {esc(quote)}?"'
        html_out = f"""
<div class="p-action"><div class="k">CHECK YOUR DEVICE</div><div class="t">{head}</div></div>
<div class="p-explain">This is called a <span class="p-term">recall</span>: the maker found a problem with some
units and is fixing it. It usually affects only some devices, so check if yours is one of them.</div>
<div class="p-explain"><b>Should I stop using it?</b> {"Keep it in service" if is_aed else "Keep using it"} unless
the maker{"" if is_aed else " or your doctor"} tells you otherwise.</div>
<div class="p-k">WHAT TO DO</div>
<div class="p-step"><span class="n">1</span><span>Find the <b>serial number</b> on the back or bottom of your {thing}.</span></div>
<div class="p-step"><span class="n">2</span><span>Call <b>{esc(maker)}</b> and ask: {ask}</span></div>
<div class="p-step"><span class="n">3</span><span>Text <b>SAVE</b> to us to get a message if anything changes.</span></div>"""
    else:
        past = len(rec["recalls"])
        sub = (f"There {'was' if past == 1 else 'were'} {past} earlier <span class=\"p-term\">recall"
               f"{'' if past == 1 else 's'}</span> (a fix the maker made to some units), and "
               f"{'it is' if past == 1 else 'all are'} finished." if past else "The maker has not reported a problem that needs fixing.")
        html_out = f"""
<div class="p-action calm"><div class="k">NO OPEN PROBLEMS</div><div class="t">No open recalls for this {thing}.</div></div>
<div class="p-explain">{sub}</div>
<div class="p-k">WHAT TO DO</div>
<div class="p-step"><span class="n">1</span><span>{"Check the readiness light, and that the pads and battery are within their dates." if is_aed else "Keep using it as your doctor prescribed."}</span></div>
<div class="p-step"><span class="n">2</span><span>Text <b>SAVE</b> to us to get a message if anything changes.</span></div>"""
    st.markdown(html_out, unsafe_allow_html=True)

# ---------------------------------------------------------------- what's wrong?
with tab_wrong:
    if not rec["recalls"]:
        st.markdown(f'<div class="p-explain">No <span class="p-term">recalls</span> name this {thing}.</div>',
                    unsafe_allow_html=True)
    cards = ""
    for r in rec["recalls"]:
        is_open = r in open_recalls
        reason = (r["reason"] or "").strip()
        reason = reason[:240] + ("…" if len(reason) > 240 else "")
        cards += (f'<div class="p-recall"><div class="top"><span>Started {esc(month(r["date"]))}</span>'
                  f'<span class="open">{"● Still open" if is_open else "Finished"}</span></div>'
                  f'<div class="lbl">The problem, in the FDA\'s words</div><div class="r">{esc(reason)}</div>'
                  f'<div class="num">Recall number to quote: <b>{esc(r["number"])}</b></div></div>')
    if rec["recalls"]:
        cards = ('<div class="p-explain">A <span class="p-term">recall</span> means the maker found a problem with '
                 'some units and is fixing it. Here is each one.</div>') + cards
    st.markdown(cards, unsafe_allow_html=True)

# ---------------------------------------------------------------- what others reported
with tab_safe:
    # Practical precautions only: no death counts here, which belong on the investigator page.
    if is_aed:
        checks = [("Look at the readiness light", "Check it every week or so. If it shows a warning or beeps, "
                                                  f"contact {maker}."),
                  ("Keep the pads in date", "Pads are sealed and have an expiry date. Replace them before it, "
                                            "and always after the AED has been used."),
                  ("Keep the battery in date", "The battery has its own date. Replace it before it runs out."),
                  ("Keep it easy to reach", "Everyone nearby should know where it is. Don't lock it away."),
                  ("Register it with the maker", f"Registering your AED with {maker} means they can tell you "
                                                 "directly about recalls.")]
    else:
        checks = [("Follow the cleaning instructions", "Clean the mask, tubing and water chamber as the maker's "
                                                       "guide says."),
                  ("Watch for anything unusual", f"Particles in the tubing, odd smells or unusual noises: stop "
                                                 f"and contact {maker} or your equipment supplier."),
                  ("Don't stop treatment on your own", "If you are worried about your machine, talk to your doctor "
                                                       "before you stop using it."),
                  ("Register it with the maker", f"Registering your machine with {maker} means they can tell you "
                                                 "directly about recalls.")]
    out = '<div class="p-k" style="margin-top:.4rem">SIMPLE CHECKS</div>' + "".join(
        f'<div class="p-step"><span class="n">✓</span><span><b>{esc(h)}</b><br>{esc(b)}</span></div>' for h, b in checks)
    out += ('<div class="p-k">IF SOMETHING GOES WRONG</div>'
            f'<div class="p-step"><span class="n">1</span><span>Contact <b>{esc(maker)}</b> and describe what '
            f'happened.</span></div>'
            '<div class="p-step"><span class="n">2</span><span>Tell the FDA. Anyone can report a problem with a '
            'medical device through <a href="https://www.fda.gov/safety/medwatch-fda-safety-information-and-'
            'adverse-event-reporting-program" target="_blank">MedWatch</a>. It helps others.</span></div>'
            '<div class="p-step"><span class="n">3</span><span>Text <b>SAVE</b> to us to get a message if anything '
            'changes for your device.</span></div>')
    out += (f'<div class="p-small" style="margin-top:1rem">Want the details? <a href="{INVESTIGATOR}?d='
            f'{esc(rec["device_key"])}" target="_blank">See the full FDA record for this device</a></div>')
    st.markdown(out, unsafe_allow_html=True)
