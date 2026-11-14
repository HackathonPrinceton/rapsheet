"""Alerts: text people when a device they saved gets a new recall or a flagged spike in reports.

Run:  python -m bot.alerts --dry-run   show what would be sent, send nothing
      python -m bot.alerts             send through Photon (needs the Photon keys)
The live bot (python -m bot.photon_bot) also runs this check by itself every few minutes.

New recalls appear after a data pull (make pull). Spikes appear once pipeline/warning.py has
filled the device_month table. Nothing here invents an alert: each one is a real FDA record.
"""
import argparse
import hashlib

from dotenv import load_dotenv

from service import record

from . import replies, watch

load_dotenv()


def known_refs(rec: dict) -> list[str]:
    """Everything in the record a user can already see: its recalls and its current spike."""
    refs = [f"recall:{r['number']}" for r in rec.get("recalls", [])]
    if rec.get("warning", {}).get("spiking_now"):
        refs.append(f"spike:{rec['warning']['last_spike']}")
    return refs


def due() -> list[dict]:
    """Alerts that should go out now, one per new recall or new spike."""
    if not record.has_data():
        return []
    out, cache = [], {}
    for w in watch.everyone():
        rec = cache.get(w["device_key"]) or cache.setdefault(w["device_key"], record.build(w["device_key"]))
        if not rec:
            continue
        sent = watch.already_sent(w["contact"], w["device_key"])
        for r in rec.get("recalls", []):
            if f"recall:{r['number']}" not in sent:
                out.append(dict(w, ref=f"recall:{r['number']}", text=replies.recall_alert(w["label"], rec, r)))
        warn = rec.get("warning", {})
        if warn.get("spiking_now") and f"spike:{warn['last_spike']}" not in sent:
            out.append(dict(w, ref=f"spike:{warn['last_spike']}", text=replies.spike_alert(w["label"], rec)))
    return out


def check(send=None) -> int:
    """Send every due alert. `send(space_id, sender_id, text, key)` delivers one message;
    without it, alerts are only printed (dry run) and not marked as sent."""
    alerts = due()
    for a in alerts:
        space_id, _, sender_id = a["contact"].partition("|")
        if send is None or not sender_id:              # dry run, or a terminal-test contact
            print(f"[would send to {a['contact'][-6:]}] {a['text']}\n")
            continue
        key = "alert-" + hashlib.sha1(f"{a['contact']}|{a['device_key']}|{a['ref']}".encode()).hexdigest()
        send(space_id, sender_id, a["text"], key)
        watch.mark_sent(a["contact"], a["device_key"], a["ref"])
        print(f"alert sent: {a['label']} {a['ref']}")
    return len(alerts)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="print the alerts, send nothing")
    if ap.parse_args().dry_run:
        print(f"{check()} alert(s) due.")
    else:
        from .photon_bot import Bot
        print(f"{check(Bot().send_new)} alert(s) sent.")
