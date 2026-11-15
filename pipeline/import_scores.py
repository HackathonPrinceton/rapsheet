"""Load classifier scores exported from another laptop, so a laptop without the model can show them.

Usage:  python -m pipeline.import_scores death_scores_mkj.csv death_scores_bzd.csv

Each CSV has: report_number, death_prob, hidden_death, death_excerpt, death_word.
"""
import csv
import sys

from .store import connect


def main(paths):
    con = connect()
    for path in paths:
        with open(path, encoding="utf-8") as f:
            rows = [(float(r["death_prob"]) if r["death_prob"] else None, int(r["hidden_death"] or 0),
                     r["death_excerpt"] or None, int(r["death_word"] or 0), r["report_number"])
                    for r in csv.DictReader(f)]
        con.executemany("UPDATE reports SET death_prob=?, hidden_death=?, death_excerpt=?, death_word=? "
                        "WHERE report_number=?", rows)
        con.commit()
        print(f"{path}: {len(rows):,} scores loaded")
    print("flagged:", con.execute("SELECT COUNT(*) FROM reports WHERE hidden_death=1").fetchone()[0])


if __name__ == "__main__":
    main(sys.argv[1:])
