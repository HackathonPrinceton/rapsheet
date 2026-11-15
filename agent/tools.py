"""Read-only tools the Investigator uses. Each one wraps data or code the rest of Rap Sheet already uses,
so the agent sees exactly what the page and the bot show, and every answer carries FDA report numbers.

Every tool returns JSON text, kept short so a whole investigation fits comfortably in the model's context.
"""
import json
import os
import re

from pipeline.deathwords import STATES_DEATH
from pipeline.paths import EXPLANATIONS, FINAL_RESULTS
from pipeline.store import connect
from service import record

CODES = {"MKJ": "automated external defibrillators (AEDs)", "BZD": "CPAP / BiPAP machines"}


def _json(x) -> str:
    return json.dumps(x, ensure_ascii=False, default=str)


def _load(path):
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _clip(text, n):
    text = re.sub(r"\s+", " ", text or "").strip()
    return text if len(text) <= n else text[:n] + "…"


def search_devices(query: str) -> str:
    """Find device families by brand or maker name (for example "LIFEPAK CR2" or "DreamStation").

    Returns up to 5 matches: device_key (use it with the other tools), brand, maker and report count.
    """
    return _json([{"device_key": m["device_key"], "brand": m["brand"], "maker": m["manufacturer"],
                   "reports": m["n"]} for m in record.search(query)])


def rank_devices(product_code: str, by: str = "hidden_deaths", limit: int = 10) -> str:
    """Rank device families of one type. product_code: "MKJ" (AEDs) or "BZD" (CPAP/BiPAP machines).

    by: "hidden_deaths" (reports whose text says the patient died but were filed as a malfunction or injury,
    found by our classifier), "coded_deaths" (filed as deaths), or "reports" (all reports).
    Only device families with at least 30 reports are ranked.
    """
    order = {"hidden_deaths": "hidden", "coded_deaths": "coded", "reports": "n"}.get(by, "hidden")
    rows = connect().execute(
        f"SELECT device_key, MAX(brand) brand, MAX(manufacturer) maker, COUNT(*) n, "
        f"SUM(event_type='Death') coded, SUM(COALESCE(hidden_death,0)) hidden FROM reports "
        f"WHERE product_code=? AND brand != '' AND device_key NOT LIKE '%--unknown%' "
        f"GROUP BY device_key HAVING n >= 30 ORDER BY {order} DESC LIMIT ?",
        (product_code.upper(), max(1, min(int(limit), 25)))).fetchall()
    return _json({"device_type": CODES.get(product_code.upper(), product_code), "ranked_by": by,
                  "devices": [{"device_key": r["device_key"], "brand": r["brand"], "maker": r["maker"],
                               "reports": r["n"], "coded_deaths": r["coded"], "hidden_deaths": r["hidden"]}
                              for r in rows]})


def device_summary(device_key: str) -> str:
    """The safety record of one device family: report counts, deaths filed as deaths, deaths filed as
    something else (classifier), the maker's late-filing share, recalls, and whether reports are rising."""
    rec = record.build(device_key)
    if not rec:
        return _json({"error": f"no reports for device_key {device_key!r}; use search_devices first"})
    t, m = rec["totals"], rec["manufacturer"]
    return _json({
        "device_key": device_key, "brand": rec["device"]["brand"], "maker": rec["device"]["manufacturer"],
        "device_type": CODES.get(rec["device"]["product_code"]),
        "period": rec["period"], "reports": t["reports"],
        "deaths_filed_as_deaths": t["deaths_coded"],
        "deaths_filed_as_something_else": t["deaths_hidden"] if t["hidden_death_model_ran"] else None,
        "outcome_field_disagrees": t.get("deaths_outcome_field"),
        "maker_pct_reports_late": m.get("pct_late"), "maker_reports_with_dates": m.get("reports_with_deadline"),
        "recalls": [{"number": r["number"], "date": r["date"], "status": r["status"],
                     "reason": _clip(r["reason"], 160)} for r in rec["recalls"]],
        "reports_rising_now": rec["warning"]["spiking_now"], "last_jump_in_reports": rec["warning"]["last_spike"],
    })


def hidden_death_reports(device_key: str, limit: int = 5) -> str:
    """Reports for one device whose text says the patient died but which were filed as a malfunction or
    injury, highest model confidence first. Each comes with the passage the model read and the phrases that
    drove its score."""
    expl = _load(EXPLANATIONS).get("reports", {})
    rows = connect().execute(
        "SELECT report_number, date_received, event_type, death_prob, death_excerpt FROM reports "
        "WHERE device_key=? AND hidden_death=1 ORDER BY death_prob DESC LIMIT ?",
        (device_key, max(1, min(int(limit), 15)))).fetchall()
    out = []
    for r in rows:
        x = expl.get(r["report_number"], {})
        out.append({"report_number": r["report_number"], "date": r["date_received"], "filed_as": r["event_type"],
                    "model_confidence": round(r["death_prob"] or 0, 3),
                    "passage": _clip(x.get("passage") or r["death_excerpt"], 320),
                    "phrases_for": [w["term"] for w in x.get("words_up", [])[:4]]})
    return _json(out or {"note": "no flagged reports for this device"})


def read_report(report_number: str) -> str:
    """The full FDA report: how it was filed, the patient outcome field, dates, device, the narrative text,
    and a link to the FDA's own copy. Use it to check any claim before citing the report."""
    r = connect().execute(
        "SELECT report_number, mdr_report_key, event_type, outcomes, date_received, date_mfr_aware, brand, "
        "manufacturer, narrative, hidden_death FROM reports WHERE report_number=?", (report_number,)).fetchone()
    if not r:
        return _json({"error": f"no report {report_number!r}"})
    return _json({"report_number": r["report_number"], "filed_as": r["event_type"],
                  "outcome_field": r["outcomes"] or "", "date_received": r["date_received"],
                  "maker_aware": r["date_mfr_aware"], "device": r["brand"], "maker": r["manufacturer"],
                  "flagged_by_model": bool(r["hidden_death"]),
                  "narrative": _clip(re.sub(r"\[[^\]]*\]", "", r["narrative"] or ""), 2500),
                  "fda_url": record.links(r)["fda_url"]})


def rank_makers_late(product_code: str) -> str:
    """Share of each maker's reports filed after the FDA's 30-day deadline, for one device type
    (product_code "MKJ" or "BZD"). Makers with at least 20 reports with both dates known."""
    return _json([{"maker": r["manufacturer"], "reports": r["n"], "pct_late": r["pct_late"]}
                  for r in record.makers_late(product_code.upper())][:15])


def method_accuracy() -> str:
    """How reliable the numbers are: the hidden-death classifier and other methods, scored against reports
    two people labelled by hand without seeing any model's answer. Quote this when stating limits."""
    g = _load(FINAL_RESULTS)
    keep = ("death word", "outcome field", "classifier", "large model")
    return _json({"hand_checked_reports": g.get("gold_reports_used"),
                  "checker_agreement": g.get("two_checkers"),
                  "methods": {k: {"precision": v["precision"], "recall": v["recall"]}
                              for k, v in g.get("methods", {}).items() if k in keep}})


def states_death(text: str) -> bool:
    """Used by the citation check: does this text state that a patient died."""
    return bool(STATES_DEATH.search(text or ""))


TOOLS = [search_devices, rank_devices, device_summary, hidden_death_reports, read_report, rank_makers_late,
         method_accuracy]
