"""Build one device's safety record from the database (plan section 8)."""
import json
import os
import re
from difflib import SequenceMatcher

from pipeline.store import connect

SAMPLE = os.path.join(os.path.dirname(__file__), "..", "data", "sample_record.json")
FDA_PAGE = "https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfmaude/detail.cfm?mdrfoi__id={}"
FDA_API = "https://api.fda.gov/device/event.json?search=report_number:%22{}%22"


def links(row) -> dict:
    """Two ways to check a report yourself: the FDA's web page (needs the internal key) and the raw API record."""
    key = row["mdr_report_key"] if "mdr_report_key" in row.keys() else None
    api = FDA_API.format(row["report_number"])
    return {"fda_url": FDA_PAGE.format(key) if key else api, "fda_api_url": api}


def sample_record() -> dict:
    with open(SAMPLE, encoding="utf-8") as f:
        return json.load(f)


def has_data() -> bool:
    try:
        return connect().execute("SELECT 1 FROM reports LIMIT 1").fetchone() is not None
    except Exception:
        return False


def search(q: str, limit: int = 5) -> list[dict]:
    """Find device families whose brand or maker matches the text a user typed."""
    words = [w for w in re.findall(r"[a-z0-9]+", q.lower()) if len(w) > 1]
    if not words:
        return []
    con = connect()
    rows = con.execute(
        "SELECT device_key, brand, manufacturer, COUNT(*) n FROM reports "
        "WHERE brand != '' GROUP BY device_key HAVING n >= 3").fetchall()
    scored = []
    for r in rows:
        hay = f"{r['brand']} {r['manufacturer']}".lower()
        hits = sum(w in hay for w in words) / len(words)
        fuzzy = SequenceMatcher(None, q.lower(), hay).ratio()
        score = hits * 0.7 + fuzzy * 0.3
        if hits > 0 or fuzzy > 0.6:
            scored.append((score, r["n"], dict(r)))
    scored.sort(key=lambda t: (round(t[0], 2), t[1]), reverse=True)
    return [dict(d, score=round(s, 2)) for s, _, d in scored[:limit]]


# Words that describe the kind of device, not the model. They must not decide which recalls match.
GENERIC_WORDS = {"defibrillator", "defibrillators", "defib", "aed", "aeds", "automated", "automatic", "external",
                 "monitor", "system", "device", "unit", "the", "and", "with", "for", "series", "model",
                 "cpap", "machine", "pump", "kit", "semi", "fully", "ems", "biphasic"}


def build(device_key: str) -> dict | None:
    con = connect()
    head = con.execute(
        "SELECT brand, manufacturer, product_code, COUNT(*) n, MIN(date_received) first, MAX(date_received) last "
        "FROM reports WHERE device_key = ?", (device_key,)).fetchone()
    if not head or not head["n"]:
        return None
    one = lambda sql, *a: con.execute(sql, a).fetchone()[0] or 0
    coded = one("SELECT COUNT(*) FROM reports WHERE device_key=? AND event_type='Death'", device_key)
    hidden = one("SELECT COUNT(*) FROM reports WHERE device_key=? AND hidden_death=1", device_key)
    scored = one("SELECT COUNT(*) FROM reports WHERE device_key=? AND death_prob IS NOT NULL", device_key)

    m = con.execute(
        "SELECT SUM(late_class='on_time') ok, SUM(late_class='late') late, SUM(late_class='very_late') very, "
        "SUM(late_class='unknown') unk, SUM(late_class!='not_manufacturer') n "
        "FROM reports WHERE manufacturer = ?", (head["manufacturer"],)).fetchone()
    # Shares are of reports whose delay is known (both dates present); missing dates are counted separately.
    known = (m["ok"] or 0) + (m["late"] or 0) + (m["very"] or 0)
    pct = lambda x: round(100 * (x or 0) / known, 1) if known else None

    brand_words = [w for w in re.findall(r"[a-z0-9]+", head["brand"].lower())
                   if len(w) > 2 and w not in GENERIC_WORDS]
    maker_first = (head["manufacturer"].split() or [""])[0].lower()
    recalls = []
    for r in con.execute("SELECT * FROM recalls WHERE product_code = ? ORDER BY date_initiated DESC",
                         (head["product_code"],)):
        text = f"{r['description']} {r['firm']}".lower()
        if maker_first and maker_first in text and brand_words and all(w in text for w in brand_words):
            recalls.append({"number": r["recall_number"], "date": r["date_initiated"], "status": r["status"],
                            "reason": (r["reason"] or "")[:300], "firm": r["firm"],
                            "description": (r["description"] or "")[:300]})

    months = [dict(r) for r in con.execute(
        "SELECT substr(date_received,1,7) month, COUNT(*) n_reports, SUM(event_type='Death') n_deaths_coded, "
        "SUM(COALESCE(hidden_death,0)) n_deaths_hidden FROM reports WHERE device_key=? "
        "GROUP BY month ORDER BY month", (device_key,))]
    spikes = {r["month"]: r["spike_score"] for r in con.execute(
        "SELECT month, spike_score FROM device_month WHERE device_key=? AND spike_flag=1", (device_key,))}
    for mo in months:
        mo["spike"] = mo["month"] in spikes

    evidence = [{
        "report_number": r["report_number"], "coded_as": r["event_type"], "date": r["date_received"],
        "death_prob": r["death_prob"], "excerpt": excerpt(r["narrative"]),
        **links(r),
    } for r in con.execute(
        "SELECT * FROM reports WHERE device_key=? AND hidden_death=1 ORDER BY death_prob DESC LIMIT 25",
        (device_key,))]

    last_spike = max(spikes) if spikes else None
    return {
        "device_key": device_key,
        "device": {"brand": head["brand"], "manufacturer": head["manufacturer"],
                   "product_code": head["product_code"]},
        "period": {"first": head["first"], "last": head["last"]},
        "totals": {"reports": head["n"], "deaths_coded": coded, "deaths_hidden": hidden,
                   "hidden_death_model_ran": bool(scored)},
        "manufacturer": {"name": head["manufacturer"], "reports_with_deadline": known,
                         "pct_on_time": pct(m["ok"]), "pct_late": pct((m["late"] or 0) + (m["very"] or 0)),
                         "pct_very_late": pct(m["very"]),
                         "pct_unknown": round(100 * (m["unk"] or 0) / m["n"], 1) if m["n"] else None},
        "recalls": recalls,
        # How recalls were matched, shown on the page so anyone can judge the rule.
        "recall_match": {"maker_word": maker_first, "brand_words": brand_words,
                         "recalls_checked": one("SELECT COUNT(*) FROM recalls WHERE product_code=?",
                                                head["product_code"])},
        # "now" = a flagged spike in one of the three most recent months that have reports
        "warning": {"spiking_now": last_spike in [x["month"] for x in months][-3:],
                    "last_spike": last_spike},
        "months": months,
        "evidence": evidence,
    }


def top_reports(device_key: str, n: int = 3) -> list[dict]:
    """The reports most worth reading: miscoded deaths first, then coded deaths, then the newest."""
    rows = connect().execute(
        "SELECT * FROM reports WHERE device_key=? AND narrative != '' "
        "ORDER BY COALESCE(hidden_death,0) DESC, (event_type='Death') DESC, date_received DESC LIMIT ?",
        (device_key, n)).fetchall()
    return [{"report_number": r["report_number"], "coded_as": r["event_type"], "date": r["date_received"],
             "excerpt": excerpt(r["narrative"]), **links(r)} for r in rows]


DEATH_WORDS = re.compile(
    r"(died|death|deceased|expired|passed away|fatal|did not survive|not be revived|pronounced)", re.I)


def excerpt(narrative: str, width: int = 260) -> str:
    """The part of the narrative around the first death-related phrase."""
    text = re.sub(r"\s+", " ", narrative or "")
    hit = DEATH_WORDS.search(text)
    if not hit:
        return text[:width]
    start = max(0, hit.start() - width // 2)
    return ("..." if start else "") + text[start:start + width] + ("..." if start + width < len(text) else "")


# ---------------------------------------------------------------- audit helpers (used by the page)
REPORT_COLS = ("report_number, mdr_report_key, date_received, event_type, source, date_mfr_aware, "
               "days_to_report, late_class, death_prob, hidden_death, brand, model, manufacturer, narrative")


def reports(device_key: str, which: str = "all") -> list[dict]:
    """The exact reports behind a number on the page, newest first."""
    where = {"all": "", "deaths_coded": " AND event_type='Death'", "deaths_hidden": " AND hidden_death=1"}[which]
    rows = connect().execute(f"SELECT {REPORT_COLS} FROM reports WHERE device_key=?{where} "
                             "ORDER BY date_received DESC", (device_key,)).fetchall()
    return [dict({k: r[k] for k in r.keys() if k != "narrative"}, excerpt=excerpt(r["narrative"]), **links(r))
            for r in rows]


def maker_reports(manufacturer: str) -> list[dict]:
    """Every manufacturer report from this maker with a known delay: the basis of the late-filing number."""
    rows = connect().execute(
        f"SELECT {REPORT_COLS} FROM reports WHERE manufacturer=? AND late_class IN ('on_time','late','very_late') "
        "ORDER BY days_to_report DESC", (manufacturer,)).fetchall()
    return [dict({k: r[k] for k in r.keys() if k != "narrative"}, **links(r)) for r in rows]


def makers_late(product_code: str, min_reports: int = 20) -> list[dict]:
    """Late-filing share for every maker of this device type, so one maker's number has context."""
    return [dict(r) for r in connect().execute(
        "SELECT manufacturer, COUNT(*) n, ROUND(100.0 * SUM(late_class IN ('late','very_late')) / COUNT(*), 1) pct_late "
        "FROM reports WHERE product_code=? AND late_class IN ('on_time','late','very_late') "
        "GROUP BY manufacturer HAVING n >= ? ORDER BY pct_late DESC", (product_code, min_reports))]


def months_by_type(device_key: str) -> list[dict]:
    return [dict(r) for r in connect().execute(
        "SELECT substr(date_received,1,7) month, COALESCE(NULLIF(event_type,''),'Not given') event_type, COUNT(*) n "
        "FROM reports WHERE device_key=? GROUP BY month, event_type ORDER BY month", (device_key,))]


def provenance() -> dict:
    """What is in the database right now: the scope every number on the page is limited to."""
    con = connect()
    r = con.execute("SELECT COUNT(*) n, MIN(date_received) first, MAX(date_received) last, "
                    "COUNT(DISTINCT product_code) codes FROM reports").fetchone()
    return {"reports": r["n"], "first": r["first"], "last": r["last"],
            "recalls": con.execute("SELECT COUNT(*) FROM recalls").fetchone()[0],
            "codes": [x[0] for x in con.execute("SELECT DISTINCT product_code FROM reports")]}
