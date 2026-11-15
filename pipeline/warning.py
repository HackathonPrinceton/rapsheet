"""Early warning: flag months where a device's report count jumps, and backtest against past recalls.

Usage:  python -m pipeline.warning            # build device_month, flag spikes, run the backtest

A spike is not proof of a defect. Reports also rise after news coverage, lawsuits, or when a
manufacturer files old reports in bulk. The wording everywhere is "reports are rising".
"""
import json
import os
import random
from collections import defaultdict

import numpy as np
import pandas as pd

from .match import norm, recall_matches
from .paths import BACKTEST
from .store import connect

HISTORY = 12        # months of the device's own history used as the baseline
MIN_HISTORY = 6     # months needed before a device can be flagged
Z_FLAG = 3.0        # robust z-score at or above which a month is flagged
MIN_REPORTS = 5     # a flagged month needs at least this many reports
MIN_DEVICE_REPORTS = 30   # devices with fewer reports in total are not scored
WINDOW = 24         # backtest: a warning counts if it falls in the 24 months before the recall
METRICS = BACKTEST


def month_index(first: str, last: str) -> list[str]:
    return [p.strftime("%Y-%m") for p in pd.period_range(first, last, freq="M")]


def robust_z(counts: np.ndarray) -> np.ndarray:
    """For each month: how far the count sits above the median of the previous 12 months.

    The spread is the median absolute deviation, with a floor of sqrt(median) so that a quiet
    device going from 1 to 4 reports is not treated as an explosion.
    """
    z = np.full(len(counts), np.nan)
    for i in range(MIN_HISTORY, len(counts)):
        past = counts[max(0, i - HISTORY):i]
        med = np.median(past)
        mad = np.median(np.abs(past - med))
        scale = max(1.4826 * mad, np.sqrt(max(med, 1.0)))
        z[i] = (counts[i] - med) / scale
    return z


def build_device_month(con) -> pd.DataFrame:
    """Monthly counts per device, with zero-filled gaps, scores and flags. Writes device_month."""
    raw = pd.read_sql_query(
        "SELECT device_key, substr(date_received,1,7) month, COUNT(*) n_reports, "
        "SUM(event_type='Death') n_deaths_coded, SUM(COALESCE(hidden_death,0)) n_deaths_hidden "
        "FROM reports WHERE date_received IS NOT NULL AND brand != '' GROUP BY device_key, month", con)
    last_month = raw["month"].max()
    out = []
    for key, g in raw.groupby("device_key"):
        if g["n_reports"].sum() < MIN_DEVICE_REPORTS:
            continue
        idx = month_index(g["month"].min(), last_month)
        g = g.drop(columns="device_key").set_index("month").reindex(idx, fill_value=0)
        g["device_key"] = key
        g["spike_score"] = robust_z(g["n_reports"].to_numpy(dtype=float))
        g["spike_flag"] = ((g["spike_score"] >= Z_FLAG) & (g["n_reports"] >= MIN_REPORTS)).astype(int)
        out.append(g.reset_index(names="month"))
    dm = pd.concat(out, ignore_index=True)
    # The current month is incomplete, so it can never be a fair comparison.
    dm.loc[dm["month"] == last_month, ["spike_flag"]] = 0
    con.execute("DELETE FROM device_month")
    con.executemany(
        "INSERT INTO device_month VALUES (?,?,?,?,?,?,?)",
        [(r.device_key, r.month, int(r.n_reports), int(r.n_deaths_coded), int(r.n_deaths_hidden),
          int(r.spike_flag), None if np.isnan(r.spike_score) else round(float(r.spike_score), 2))
         for r in dm.itertuples()])
    con.commit()
    return dm


def recall_events(con, dm: pd.DataFrame) -> pd.DataFrame:
    """One row per (recall event, device): recalls matched to the scored devices they name."""
    devices = pd.read_sql_query(
        "SELECT device_key, product_code, MAX(brand) brand, MAX(manufacturer) manufacturer "
        "FROM reports WHERE brand != '' GROUP BY device_key", con)
    devices = devices[devices["device_key"].isin(set(dm["device_key"]))]
    recalls = pd.read_sql_query("SELECT * FROM recalls WHERE date_initiated IS NOT NULL", con)
    rows = set()
    for r in recalls.itertuples():
        text = norm(f"{r.firm} {r.description}")
        for d in devices[devices["product_code"] == r.product_code].itertuples():
            if recall_matches(text, d.manufacturer, d.brand):
                # one firm often files several recall numbers on one day for one problem
                rows.add((d.device_key, r.date_initiated[:7]))
    return pd.DataFrame(sorted(rows), columns=["device_key", "recall_month"])


def months_between(a: str, b: str) -> int:
    return (int(b[:4]) - int(a[:4])) * 12 + int(b[5:7]) - int(a[5:7])


def backtest(dm: pd.DataFrame, events: pd.DataFrame, seed: int = 0) -> dict:
    """Did a flag come in the 24 months before each recall, and how does that compare with chance?

    Chance = the same question asked of 24-month windows that do not end in a recall,
    taken from the same pool of scored devices.
    """
    flags = defaultdict(list)
    for r in dm[dm["spike_flag"] == 1].itertuples():
        flags[r.device_key].append(r.month)
    first_seen = dm.groupby("device_key")["month"].min().to_dict()
    last_month = dm["month"].max()
    recalls_by_device = events.groupby("device_key")["recall_month"].apply(list).to_dict()

    def warned(key, anchor):
        """Earliest flag 1..WINDOW months before the anchor month, as a lead time; None if no flag."""
        leads = [months_between(f, anchor) for f in flags.get(key, [])]
        leads = [x for x in leads if 1 <= x <= WINDOW]
        return max(leads) if leads else None

    # A recall is testable only if the device had enough history before it to be scored at all.
    testable = [(k, m) for k, m in events.itertuples(index=False)
                if months_between(first_seen[k], m) >= MIN_HISTORY + 1 and m <= last_month]
    leads = [warned(k, m) for k, m in testable]
    hit = [x for x in leads if x is not None]

    # Control windows: random anchor months with the same history rule, no recall in the window.
    rng = random.Random(seed)
    controls = []
    keys = sorted(first_seen)
    all_months = month_index(dm["month"].min(), last_month)
    for _ in range(20000):
        k, m = rng.choice(keys), rng.choice(all_months)
        if months_between(first_seen[k], m) < MIN_HISTORY + 1:
            continue
        if any(0 <= months_between(m, rm) <= WINDOW or 0 <= months_between(rm, m) <= WINDOW
               for rm in recalls_by_device.get(k, [])):
            continue
        controls.append(warned(k, m) is not None)

    # False alarms: flags with at least 24 months of follow-up and no recall of that device after them.
    followed = [(k, f) for k, fs in flags.items() for f in fs if months_between(f, last_month) >= WINDOW]
    no_recall = [1 for k, f in followed
                 if not any(1 <= months_between(f, rm) <= WINDOW for rm in recalls_by_device.get(k, []))]

    share = lambda a, b: round(100 * a / b, 1) if b else None
    return {
        "devices_scored": len(first_seen),
        "device_months": int(len(dm)),
        "months_flagged": int(dm["spike_flag"].sum()),
        "recall_events_matched_to_a_device": int(len(events)),
        "recall_events_testable": len(testable),
        "recalls_with_warning_in_prior_24_months": len(hit),
        "pct_recalls_with_warning": share(len(hit), len(testable)),
        "pct_control_windows_with_warning": share(sum(controls), len(controls)),
        "control_windows": len(controls),
        "median_lead_months": float(np.median(hit)) if hit else None,
        "flags_with_24_months_follow_up": len(followed),
        "pct_flags_followed_by_no_recall": share(len(no_recall), len(followed)),
        "settings": {"history_months": HISTORY, "z_flag": Z_FLAG, "min_reports": MIN_REPORTS,
                     "window_months": WINDOW, "min_device_reports": MIN_DEVICE_REPORTS},
    }


def main():
    con = connect()
    dm = build_device_month(con)
    events = recall_events(con, dm)
    metrics = backtest(dm, events)
    os.makedirs(os.path.dirname(METRICS), exist_ok=True)
    with open(METRICS, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
