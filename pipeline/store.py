"""SQLite store. These tables are the contract between the pipeline and the service."""
import os
import re
import sqlite3

DB_PATH = os.environ.get("RAPSHEET_DB", os.path.join(os.path.dirname(__file__), "..", "data", "rapsheet.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (
  report_number TEXT PRIMARY KEY,
  product_code TEXT, device_key TEXT, brand TEXT, model TEXT, manufacturer TEXT,
  event_type TEXT, source TEXT,
  date_event TEXT, date_mfr_aware TEXT, date_received TEXT,
  narrative TEXT,
  days_to_report INTEGER, late_class TEXT,
  death_prob REAL, hidden_death INTEGER
);
CREATE INDEX IF NOT EXISTS idx_reports_device ON reports(device_key);
CREATE INDEX IF NOT EXISTS idx_reports_mfr ON reports(manufacturer);
CREATE TABLE IF NOT EXISTS recalls (
  recall_number TEXT PRIMARY KEY,
  product_code TEXT, firm TEXT, date_initiated TEXT, reason TEXT,
  description TEXT, status TEXT
);
CREATE TABLE IF NOT EXISTS device_month (
  device_key TEXT, month TEXT, n_reports INTEGER, n_deaths_coded INTEGER,
  n_deaths_hidden INTEGER, spike_flag INTEGER, spike_score REAL,
  PRIMARY KEY (device_key, month)
);
CREATE TABLE IF NOT EXISTS watchlist (
  contact TEXT, device_key TEXT, label TEXT, pads_expiry TEXT, battery_expiry TEXT,
  added_at TEXT DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (contact, device_key)
);
"""


def connect(path: str = DB_PATH) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


_SUFFIXES = re.compile(
    r"\b(inc|incorporated|corp|corporation|co|company|ltd|limited|llc|gmbh|ag|sa|nv|bv|plc|"
    r"medical|systems?|healthcare|industrial|technologies|technology)\b\.?", re.I)


def clean_manufacturer(name: str) -> str:
    """'PHILIPS GOLDWAY (SHENZHEN) INDUSTRIAL INC.' -> 'PHILIPS GOLDWAY'."""
    name = re.sub(r"\([^)]*\)", " ", name or "")
    name = _SUFFIXES.sub(" ", name)
    words = re.sub(r"[^A-Za-z0-9 ]+", " ", name).upper().split()
    while len(words) > 1 and len(words[-1]) == 1:      # leftovers such as "L L C"
        words.pop()
    return " ".join(words)


def device_key(manufacturer: str, brand: str) -> str:
    """Stable id for one device family: first word of the maker + cleaned brand name."""
    maker = clean_manufacturer(manufacturer).split()
    brand = re.sub(r"\((r|tm|c)\)|®|™", "", brand or "", flags=re.I)
    brand = re.sub(r"[^a-z0-9]+", "-", brand.lower()).strip("-")
    return f"{(maker[0].lower() if maker else 'unknown')}--{brand or 'unknown'}"
