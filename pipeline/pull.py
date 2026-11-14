"""Pull adverse event reports and recalls from openFDA into SQLite.

Usage:  python -m pipeline.pull --codes MKJ BZD --start 2019-01 --end 2026-11
"""
import argparse
import datetime as dt
import os
import time

import requests
from dotenv import load_dotenv

from .store import clean_manufacturer, connect, device_key

load_dotenv()
BASE = "https://api.fda.gov/device"
KEY = os.environ.get("OPENFDA_API_KEY", "")
PAGE = 1000 if KEY else 100   # without an API key openFDA rejects large pages (403)
MAX_SKIP = 25000     # openFDA maximum skip; we pull one month at a time to stay under it


def get(endpoint: str, search: str, skip: int = 0, limit: int = PAGE) -> dict:
    params = {"search": search, "limit": limit, "skip": skip}
    if KEY:
        params["api_key"] = KEY
    for attempt in range(5):
        r = requests.get(f"{BASE}/{endpoint}.json", params=params, timeout=60)
        if r.status_code == 404:            # openFDA returns 404 for "no matches"
            return {"results": []}
        if r.status_code == 200:
            return r.json()
        time.sleep(3 * (attempt + 1))       # 403/429 (rate limit) or 5xx: back off and retry
    r.raise_for_status()
    return {"results": []}


def parse_date(s):
    try:
        return dt.datetime.strptime(s, "%Y%m%d").date()
    except (TypeError, ValueError):
        return None


def late_class(aware, received, source: str):
    """30 days is the legal deadline for manufacturer reports (21 CFR 803)."""
    if "manufacturer" not in (source or "").lower():
        return None, "not_manufacturer"
    if not aware or not received or received < aware or aware.year < 1990:
        return None, "unknown"
    days = (received - aware).days
    if days <= 30:
        return days, "on_time"
    return days, ("late" if days <= 180 else "very_late")


def to_row(r: dict, code: str) -> tuple:
    dev = next((d for d in r.get("device", []) if d.get("device_report_product_code") == code),
               (r.get("device") or [{}])[0])
    brand = (dev.get("brand_name") or "").strip()
    maker = clean_manufacturer(dev.get("manufacturer_d_name") or r.get("manufacturer_name") or "")
    narrative = "\n".join(
        f"[{t.get('text_type_code', '')}] {t.get('text', '')}" for t in r.get("mdr_text", []))
    aware, received = parse_date(r.get("date_manufacturer_received")), parse_date(r.get("date_received"))
    source = r.get("report_source_code") or ""
    days, cls = late_class(aware, received, source)
    iso = lambda d: d.isoformat() if d else None
    patients = r.get("patient") or []
    # Outcome codes arrive as full words ("Death") or as stray single letters (" D"); keep the words.
    outcomes = sorted({o.strip() for p in patients for o in (p.get("sequence_number_outcome") or [])
                       if len(o.strip()) > 1})
    problems = sorted({o.strip() for p in patients for o in (p.get("patient_problems") or []) if o.strip()})
    return (r.get("report_number") or r.get("mdr_report_key"), code, device_key(maker, brand), brand,
            dev.get("model_number"), maker, r.get("event_type"), source,
            iso(parse_date(r.get("date_of_event"))), iso(aware), iso(received), narrative, days, cls,
            r.get("mdr_report_key"),
            "; ".join(outcomes), "; ".join(problems), "; ".join(r.get("type_of_report") or []),
            dev.get("udi_di"))


def months(start: str, end: str):
    y, m = map(int, start.split("-"))
    ey, em = map(int, end.split("-"))
    while (y, m) <= (ey, em):
        first = dt.date(y, m, 1)
        nxt = dt.date(y + (m == 12), m % 12 + 1, 1)
        yield first, nxt - dt.timedelta(days=1)
        y, m = nxt.year, nxt.month


def windows(code: str, first, last):
    """One month normally. A month with more reports than openFDA lets us page through is split by day."""
    search = (f"device.device_report_product_code:{code} AND "
              f"date_received:[{first:%Y%m%d} TO {last:%Y%m%d}]")
    n = get("event", search, 0, 1).get("meta", {}).get("results", {}).get("total", 0)
    if n <= MAX_SKIP + PAGE:
        return [(first, last)]
    return [(first + dt.timedelta(days=i),) * 2 for i in range((last - first).days + 1)]


def pull_events(con, code: str, start: str, end: str):
    total = 0
    for first, last in (w for m in months(start, end) for w in windows(code, *m)):
        search = (f"device.device_report_product_code:{code} AND "
                  f"date_received:[{first:%Y%m%d} TO {last:%Y%m%d}]")
        skip = 0
        while skip <= MAX_SKIP:
            results = get("event", search, skip).get("results", [])
            if not results:
                break
            con.executemany(
                "INSERT INTO reports (report_number, product_code, device_key, brand, model,"
                " manufacturer, event_type, source, date_event, date_mfr_aware, date_received, narrative,"
                " days_to_report, late_class, mdr_report_key, outcomes, patient_problems, report_type, udi_di)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
                # Update in place, so a re-pull never wipes the classifier's death_prob / hidden_death.
                " ON CONFLICT(report_number) DO UPDATE SET product_code=excluded.product_code,"
                " device_key=excluded.device_key, brand=excluded.brand, model=excluded.model,"
                " manufacturer=excluded.manufacturer, event_type=excluded.event_type, source=excluded.source,"
                " date_event=excluded.date_event, date_mfr_aware=excluded.date_mfr_aware,"
                " date_received=excluded.date_received, narrative=excluded.narrative,"
                " days_to_report=excluded.days_to_report, late_class=excluded.late_class,"
                " mdr_report_key=excluded.mdr_report_key, outcomes=excluded.outcomes,"
                " patient_problems=excluded.patient_problems, report_type=excluded.report_type,"
                " udi_di=excluded.udi_di",
                [to_row(r, code) for r in results])
            con.commit()
            total += len(results)
            skip += PAGE
            if len(results) < PAGE:
                break
        else:
            print(f"  WARNING {code} {first}: more than {MAX_SKIP + PAGE} reports in one window, some skipped")
        print(f"  {code} {first:%Y-%m-%d}: running total {total}", flush=True)
    return total


def pull_recalls(con, code: str):
    skip, total = 0, 0
    while skip <= MAX_SKIP:
        results = get("recall", f"product_code:{code}", skip).get("results", [])
        if not results:
            break
        con.executemany(
            "INSERT OR REPLACE INTO recalls VALUES (?,?,?,?,?,?,?)",
            [(r.get("product_res_number") or r.get("cfres_id"), code, r.get("recalling_firm"),
              r.get("event_date_initiated"), r.get("reason_for_recall"),
              r.get("product_description"), r.get("recall_status")) for r in results])
        con.commit()
        total += len(results)
        skip += PAGE
        if len(results) < PAGE:
            break
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--codes", nargs="+", default=["MKJ"], help="FDA product codes, e.g. MKJ (AED) BZD (CPAP)")
    ap.add_argument("--start", default="2019-01")
    ap.add_argument("--end", default=dt.date.today().strftime("%Y-%m"))
    args = ap.parse_args()
    con = connect()
    for code in args.codes:
        print(f"{code}: recalls -> {pull_recalls(con, code)}")
        print(f"{code}: reports -> {pull_events(con, code, args.start, args.end)}")


if __name__ == "__main__":
    main()
