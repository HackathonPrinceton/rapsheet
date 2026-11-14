"""Turn a device record into text messages. No network code here, so it is easy to test.

Wording rules (plan section 11): a report is an allegation, so we say "reports mention a death",
and we never tell anyone to stop using a device.
"""

DISCLAIMER = "A report is an allegation, not proof the device caused harm."
HELP = "Send a photo of a device label or type its name (for example: HeartStart FRx)."


def confirm(match: dict) -> str:
    return (f"That looks like {match['brand']} by {match['manufacturer'].title()}. "
            "Is that right? Reply YES, or type the name.")


def choices(matches: list[dict]) -> str:
    lines = [f"{i}. {m['brand']} ({m['manufacturer'].title()})" for i, m in enumerate(matches, 1)]
    return "I found a few possible matches. Reply with a number:\n" + "\n".join(lines)


def not_found(q: str) -> str:
    return f"I couldn't find \"{q}\" in the FDA reports I have. Try the brand and model printed on the label."


def summary(rec: dict, page_url: str | None = None) -> str:
    d, t, m = rec["device"], rec["totals"], rec["manufacturer"]
    since = (rec.get("period", {}).get("first") or "")[:4]
    parts = [f"{d['brand']} ({d['manufacturer'].title()})"]

    recalls = rec.get("recalls", [])
    if recalls:
        latest = recalls[0]
        parts.append(f"{len(recalls)} recall{'s' if len(recalls) != 1 else ''} on record, "
                     f"latest {latest['date']} ({latest['status']}).")
    else:
        parts.append("No recalls found for this model.")

    parts.append(f"{t['reports']:,} reports to the FDA{' since ' + since if since else ''}.")
    if t.get("hidden_death_model_ran"):
        if t["deaths_hidden"]:
            parts.append(f"{t['deaths_coded']} are coded as deaths. {t['deaths_hidden']} more mention a "
                         "patient death but are coded as something else.")
        else:
            parts.append(f"{t['deaths_coded']} are coded as deaths. I found no miscoded ones.")
    else:
        parts.append(f"{t['deaths_coded']} are coded as deaths.")

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
    lines = [f"Report {e['report_number']} (coded \"{e['coded_as']}\", {e['date']}): {e['excerpt']}" for e in ev]
    return "\n\n".join(lines) + "\n\n" + DISCLAIMER


def saved(label: str) -> str:
    return (f"Saved as \"{label}\". I'll text you if it is recalled or reports spike. "
            "Reply STOP at any time to remove it.")
