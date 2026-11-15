"""Turn a device record into text messages. No network code here, so it is easy to test.

Wording rules (plan section 11): a report is an allegation, so we say "reports mention a death",
and we never tell anyone to stop using a device.
"""

import re

DISCLAIMER = "A report is an allegation, not proof the device caused harm."

# The words that make a sentence say a patient died; used to quote the reason behind a claim.
_DEATH = re.compile(r"(died|death|deceased|expired|passed away|did not survive|not survive|not resuscitated|"
                    r"could not be resuscitated|pronounced)", re.I)


def death_quote(excerpt: str, limit: int = 110) -> str | None:
    """The shortest sentence in an excerpt that says the patient died, in plain case: the reason for a claim."""
    sentences = [x.strip(" .\\\"'") for x in re.split(r"(?<=[.;])\s+|\\+", excerpt or "")]
    hits = sorted((x for x in sentences if _DEATH.search(x) and len(x) > 12), key=len)
    if not hits:
        return None
    q = re.sub(r"\s+", " ", hits[0]).lower()
    return q if len(q) <= limit else q[:limit].rsplit(" ", 1)[0] + "..."


HELP = ("This is Rap Sheet: the FDA safety record of a medical device. "
        "Send a photo of a device label or type its name (for example: HeartStart FRx).")
READING_PHOTO = "Got your photo. Reading the label, this takes a few seconds..."
PHOTO_FAILED = "I couldn't read a device label in that photo. Please type the brand and model printed on it."
TRY_AGAIN = "OK. Please type the brand and model printed on the label."
NO_DEVICE = "First tell me which device. Send a photo of its label or type its name."
STOPPED = "Done. Your saved devices are removed and I won't send alerts. Text a device name any time to look it up."
SAMPLE_NOTE = "[EXAMPLE DATA, not a real device]"
ERROR = "Something went wrong on my side. Please try again in a moment."


def maker(name: str) -> str:
    """'PHYSIO CONTROL 3015876' -> 'Physio Control' (FDA names sometimes carry a registration number)."""
    return " ".join(w for w in (name or "").split() if not w.isdigit()).title()


def confirm(match: dict) -> str:
    return (f"That looks like {match['brand']} by {maker(match['manufacturer'])}. "
            "Is that right? Reply YES, or type the name.")


def choices(matches: list[dict]) -> str:
    lines = [f"{i}. {m['brand']} ({maker(m['manufacturer'])})" for i, m in enumerate(matches, 1)]
    return "I found a few possible matches. Reply with a number:\n" + "\n".join(lines)


def not_found(q: str) -> str:
    return f"I couldn't find \"{q}\" in the FDA reports I have. Try the brand and model printed on the label."


def summary(rec: dict, page_url: str | None = None) -> str:
    d, t, m = rec["device"], rec["totals"], rec["manufacturer"]
    since = (rec.get("period", {}).get("first") or "")[:4]
    parts = [f"{d['brand']} ({maker(d['manufacturer'])})"]
    deaths = t["deaths_coded"]
    coded = f"{deaths} {'is' if deaths == 1 else 'are'} coded as {'a death' if deaths == 1 else 'deaths'}."

    recalls = rec.get("recalls", [])
    if recalls:
        latest = recalls[0]
        parts.append(f"{len(recalls)} recall{'s' if len(recalls) != 1 else ''} on record, "
                     f"latest {latest['date']} ({latest['status']}).")
    else:
        parts.append("No recalls found for this model.")

    parts.append(f"{t['reports']:,} reports to the FDA{' since ' + since if since else ''}.")
    parts.append(coded)
    # The text classifier's count goes in the text: on hand-checked reports it was right 15 times in 16
    # (eval/metrics.md). The outcome-field count does not: only about half of those reports describe a death.
    hidden = t.get("deaths_hidden") if t.get("hidden_death_model_ran") else 0
    if hidden:
        line = (f"{hidden} more {'report describes' if hidden == 1 else 'reports describe'} a patient death "
                "but were filed as a malfunction or injury")
        # The reason, quoted from the strongest report, so the claim can be checked (Arlequin: explainability).
        ev = next((e for e in rec.get("evidence", []) if death_quote(e.get("excerpt"))), None)
        if ev:
            line += f", e.g. report {ev['report_number']}: \"{death_quote(ev['excerpt'])}\""
        parts.append(line + ".")

    if m.get("pct_late") is not None and m.get("reports_with_deadline", 0) >= 20:
        parts.append(f"This maker filed {m['pct_late']:g}% of its reports after the 30-day legal deadline.")
    if rec.get("warning", {}).get("spiking_now"):
        parts.append("Reports are rising in recent months.")
    if page_url:
        parts.append(f"Full record: {page_url}")
    parts.append(DISCLAIMER)
    if d.get("product_code") == "MKJ":
        parts.append("Keep an AED in service unless the manufacturer says otherwise.")
    parts.append("Reply MORE, SAVE or STOP.")
    return "\n".join(parts)


def more(rec: dict, n: int = 3) -> str:
    ev = rec.get("evidence", [])[:n]
    if not ev:
        return "No report excerpts to show for this device yet."
    head = ("Reports that describe a patient death but were filed as something else (flagged by our "
            "hand-checked classifier; read each one):")
    lines = [f"Report {e['report_number']} (filed as \"{e['coded_as']}\", {e['date']}): {e['excerpt']}" for e in ev]
    return head + "\n\n" + "\n\n".join(lines) + "\n\n" + DISCLAIMER


def _name(label: str, rec: dict) -> str:
    brand = rec["device"]["brand"]
    return f"\"{label}\"" if label == brand else f"\"{label}\" ({brand})"


def recall_alert(label: str, rec: dict, recall: dict) -> str:
    reason = (recall.get("reason") or "").strip()
    reason = reason[:200] + ("..." if len(reason) > 200 else "")
    parts = [f"Recall alert for {_name(label, rec)}: the FDA lists recall {recall['number']}, "
             f"started {recall['date']} ({recall['status']}).",
             f"Reason given: {reason}" if reason else "",
             "Check the recall notice and ask the manufacturer what to do."]
    if rec["device"].get("product_code") == "MKJ":
        parts.append("Keep an AED in service unless the manufacturer says otherwise.")
    parts.append("Reply STOP to stop alerts.")
    return "\n".join(p for p in parts if p)


def spike_alert(label: str, rec: dict) -> str:
    return (f"Heads up about {_name(label, rec)}: reports to the FDA about this device rose sharply in "
            f"{rec['warning']['last_spike']}. That is not a recall, and a report is not proof of a fault. "
            "Reply MORE to read recent reports. Reply STOP to stop alerts.")


def saved(label: str) -> str:
    return (f"Saved as \"{label}\". I'll text you if it is recalled or reports spike. "
            "Reply STOP at any time to remove it.")
