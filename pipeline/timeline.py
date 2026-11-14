"""Timeline builder: one dated list of events per device, merging reports, spikes and recalls.

Usage:
  from pipeline.timeline import timeline
  events = timeline(con, "philips--dreamstation")      # list of {date, kind, text, ...}

  python -m pipeline.timeline philips--dreamstation     # print it

Kinds: first_report, spike, recall, hidden_death.
Every recall says whether reports had been flagged as rising beforehand, and how many months before.
"""
import sys

from .match import norm, recall_matches
from .store import connect
from .warning import WINDOW, months_between


def device_recalls(con, device_key: str) -> list[dict]:
    """Recalls that name this device, one per firm and day."""
    head = con.execute("SELECT MAX(brand) brand, MAX(manufacturer) manufacturer, MAX(product_code) code "
                       "FROM reports WHERE device_key = ?", (device_key,)).fetchone()
    if not head or not head["brand"]:
        return []
    seen, out = set(), []
    for r in con.execute("SELECT * FROM recalls WHERE product_code = ? AND date_initiated IS NOT NULL "
                         "ORDER BY date_initiated", (head["code"],)):
        if not recall_matches(norm(f"{r['firm']} {r['description']}"), head["manufacturer"], head["brand"]):
            continue
        if r["date_initiated"] in seen:
            continue
        seen.add(r["date_initiated"])
        out.append({"date": r["date_initiated"], "number": r["recall_number"], "status": r["status"],
                    "reason": (r["reason"] or "").strip()})
    return out


def timeline(con, device_key: str, max_hidden: int = 20) -> list[dict]:
    events = []
    first = con.execute("SELECT MIN(date_received) d, COUNT(*) n FROM reports WHERE device_key = ?",
                        (device_key,)).fetchone()
    if not first or not first["n"]:
        return []
    events.append({"date": first["d"], "kind": "first_report",
                   "text": f"First report in our data. {first['n']:,} reports in total."})

    months = con.execute("SELECT month, n_reports, spike_flag, spike_score FROM device_month "
                         "WHERE device_key = ? ORDER BY month", (device_key,)).fetchall()
    counts = [m["n_reports"] for m in months]
    spikes = []
    for i, m in enumerate(months):
        if not m["spike_flag"]:
            continue
        past = sorted(counts[max(0, i - 12):i])
        usual = past[len(past) // 2] if past else 0
        spikes.append(m["month"])
        events.append({"date": f"{m['month']}-01", "kind": "spike", "score": m["spike_score"],
                       "text": f"Reports rising: {m['n_reports']} this month, against a usual {usual}."})

    for r in device_recalls(con, device_key):
        leads = [months_between(s, r["date"][:7]) for s in spikes]
        leads = [x for x in leads if 1 <= x <= WINDOW]
        warned = (f" Reports had been flagged as rising {max(leads)} months earlier." if leads else
                  " No rise in reports was flagged in the two years before.")
        events.append({"date": r["date"], "kind": "recall", "number": r["number"], "status": r["status"],
                       "lead_months": max(leads) if leads else None,
                       "text": f"Recall {r['number']}: {r['reason'][:220]}{warned}"})

    for r in con.execute("SELECT report_number, date_received, event_type, death_excerpt, death_prob "
                         "FROM reports WHERE device_key = ? AND hidden_death = 1 "
                         "ORDER BY death_prob DESC LIMIT ?", (device_key, max_hidden)):
        events.append({"date": r["date_received"], "kind": "hidden_death", "report_number": r["report_number"],
                       "death_prob": r["death_prob"],
                       "text": f"Report coded \"{r['event_type']}\" mentions a death: "
                               f"{(r['death_excerpt'] or '')[:220]}"})
    return sorted(events, key=lambda e: e["date"] or "")


if __name__ == "__main__":
    for e in timeline(connect(), sys.argv[1]):
        print(e["date"], e["kind"].upper().ljust(13), e["text"])
