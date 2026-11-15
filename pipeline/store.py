"""SQLite store. These tables are the contract between the pipeline and the service."""
import os
import re
import sqlite3

DB_PATH = os.environ.get("RAPSHEET_DB", os.path.join(os.path.dirname(__file__), "..", "data", "rapsheet.db"))
# A small copy of the database for the hosted page (python -m pipeline.make_demo_db). Used only when the
# full database is not there, so a laptop with real data is never affected.
DEMO_GZ = os.path.join(os.path.dirname(__file__), "..", "data", "rapsheet_demo.db.gz")


def _demo_db() -> str:
    """Unpack the demo database once into the temp folder and return its path."""
    import gzip
    import shutil
    import tempfile
    out = os.path.join(tempfile.gettempdir(), "rapsheet_demo.db")
    if not os.path.exists(out) or os.path.getmtime(out) < os.path.getmtime(DEMO_GZ):
        with gzip.open(DEMO_GZ, "rb") as f, open(out + ".part", "wb") as g:
            shutil.copyfileobj(f, g)
        os.replace(out + ".part", out)
    return out

SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (
  report_number TEXT PRIMARY KEY,
  product_code TEXT, device_key TEXT, brand TEXT, model TEXT, manufacturer TEXT,
  event_type TEXT, source TEXT,
  date_event TEXT, date_mfr_aware TEXT, date_received TEXT,
  narrative TEXT,
  days_to_report INTEGER, late_class TEXT,
  death_prob REAL, hidden_death INTEGER,
  mdr_report_key TEXT,
  outcomes TEXT, patient_problems TEXT, report_type TEXT, udi_di TEXT,
  death_excerpt TEXT, death_word INTEGER
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
    if path == DB_PATH and not os.path.exists(path) and os.path.exists(DEMO_GZ):
        path = _demo_db()
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    # Columns added after the first version. mdr_report_key is the FDA's internal report id: the FDA
    # web page for a report only opens with it. The rest are filled by the pull and the classifier.
    have = {r[1] for r in con.execute("PRAGMA table_info(reports)")}
    for col, kind in [("mdr_report_key", "TEXT"), ("outcomes", "TEXT"), ("patient_problems", "TEXT"),
                      ("report_type", "TEXT"), ("udi_di", "TEXT"), ("death_excerpt", "TEXT"),
                      ("death_word", "INTEGER")]:
        if col not in have:
            con.execute(f"ALTER TABLE reports ADD COLUMN {col} {kind}")
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
