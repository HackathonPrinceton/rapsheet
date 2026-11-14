"""The watch list: which contact saved which device, and which alerts each contact has already had."""
from pipeline.store import connect

ALERTS_TABLE = """
CREATE TABLE IF NOT EXISTS alerts_sent (
  contact TEXT, device_key TEXT, ref TEXT, sent_at TEXT DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (contact, device_key, ref)
);
"""


def _con():
    con = connect()
    con.executescript(ALERTS_TABLE)
    return con


def add(contact: str, device_key: str, label: str, known: list[str] = ()) -> None:
    """Save a device. `known` lists the recalls and spikes the user has already been shown,
    so they are never sent again as alerts."""
    con = _con()
    con.execute("INSERT OR REPLACE INTO watchlist (contact, device_key, label) VALUES (?,?,?)",
                (contact, device_key, label))
    con.executemany("INSERT OR IGNORE INTO alerts_sent (contact, device_key, ref) VALUES (?,?,?)",
                    [(contact, device_key, ref) for ref in known])
    con.commit()


def remove_all(contact: str) -> int:
    con = _con()
    n = con.execute("DELETE FROM watchlist WHERE contact = ?", (contact,)).rowcount
    con.execute("DELETE FROM alerts_sent WHERE contact = ?", (contact,))
    con.commit()
    return n


def saved(contact: str) -> list[dict]:
    return [dict(r) for r in _con().execute(
        "SELECT device_key, label, added_at FROM watchlist WHERE contact = ? ORDER BY added_at", (contact,))]


def everyone() -> list[dict]:
    return [dict(r) for r in _con().execute("SELECT contact, device_key, label FROM watchlist")]


def already_sent(contact: str, device_key: str) -> set[str]:
    return {r["ref"] for r in _con().execute(
        "SELECT ref FROM alerts_sent WHERE contact = ? AND device_key = ?", (contact, device_key))}


def mark_sent(contact: str, device_key: str, ref: str) -> None:
    con = _con()
    con.execute("INSERT OR IGNORE INTO alerts_sent (contact, device_key, ref) VALUES (?,?,?)",
                (contact, device_key, ref))
    con.commit()
