"""Build the small database that the hosted page uses.

Usage:  python -m pipeline.make_demo_db        # writes data/rapsheet_demo.db.gz (about 11 MB)

The full database is too large for GitHub. The page only quotes the text of reports that describe a
death (filed as deaths, flagged by the classifier, or with a Death outcome), so those keep their full
text and every other narrative is shortened. Counts, dates, recalls and monthly figures are untouched.
The watch list and alert history are removed: they hold users' contact handles and never leave the laptop.
"""
import gzip
import os
import shutil
import sqlite3
import tempfile

from .store import DB_PATH, DEMO_GZ

KEEP_CHARS = 300


def main():
    tmp = os.path.join(tempfile.gettempdir(), "rapsheet_demo_build.db")
    shutil.copy(DB_PATH, tmp)
    con = sqlite3.connect(tmp)
    con.execute("UPDATE reports SET narrative = substr(narrative, 1, ?) "
                "WHERE COALESCE(hidden_death,0)=0 AND event_type!='Death' "
                "AND COALESCE(outcomes,'') NOT LIKE '%Death%'", (KEEP_CHARS,))
    for table in ("watchlist", "alerts_sent"):
        if con.execute("SELECT 1 FROM sqlite_master WHERE name=?", (table,)).fetchone():
            con.execute(f"DELETE FROM {table}")
    con.commit()
    con.execute("VACUUM")
    n = con.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
    con.close()
    with open(tmp, "rb") as f, gzip.open(DEMO_GZ, "wb", compresslevel=6) as g:
        shutil.copyfileobj(f, g)
    os.remove(tmp)
    print(f"wrote {DEMO_GZ}: {n:,} reports, {os.path.getsize(DEMO_GZ) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
