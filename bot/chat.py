"""The conversation: one incoming message in, one reply out. No network code here.

handle() is used by the Photon bot and by the terminal test mode, so both behave the same.
It remembers, per contact, the device being discussed and any question it is waiting on.
"""
import os
from urllib.parse import quote

from service import matcher, record

from . import alerts, replies, watch

SESSIONS: dict[str, dict] = {}     # contact -> {"device_key": str | None, "pending": [matches]}

YES = {"YES", "Y", "YEP", "YEAH", "CORRECT", "RIGHT"}
NO = {"NO", "N", "NOPE", "WRONG"}
GREETINGS = {"HELP", "HI", "HELLO", "HEY", "START", "?"}
STOP = {"STOP", "UNSUBSCRIBE", "CANCEL", "QUIT"}


def page_url(device_key: str) -> str | None:
    """Link to the device page. Left out until the page is online (a localhost link is no use in a text)."""
    base = os.environ.get("PAGE_BASE_URL", "").rstrip("/")
    if not base or "localhost" in base or "127.0.0.1" in base:
        return None
    return f"{base}/?d={quote(device_key)}"


def get_record(device_key: str) -> dict | None:
    return record.build(device_key) if record.has_data() else record.sample_record()


def _show(session: dict, match: dict) -> str:
    session["device_key"], session["pending"] = match["device_key"], []
    rec = get_record(match["device_key"])
    if rec is None:
        return replies.not_found(match.get("brand", "that device"))
    text = replies.summary(rec, page_url(match["device_key"]))
    return text if record.has_data() else replies.SAMPLE_NOTE + "\n" + text


def _offer(session: dict, res: dict, always_confirm: bool) -> str:
    """Turn a matcher result into a reply: show it, confirm it, or ask the user to choose."""
    matches = res["matches"]
    if res["status"] == "none":
        return replies.not_found(res["query"])
    if res["status"] == "sure" and not always_confirm:
        return _show(session, matches[0])
    session["pending"] = matches[:1] if res["status"] == "sure" else matches
    return replies.confirm(matches[0]) if len(session["pending"]) == 1 else replies.choices(session["pending"])


def handle(contact: str, text: str = "", image: bytes | None = None) -> str:
    session = SESSIONS.setdefault(contact, {"device_key": None, "pending": []})
    text = (text or "").strip()
    word, _, rest = text.partition(" ")
    command = word.upper().strip(".!,")
    pending = session["pending"]

    if image is not None:
        try:
            res = matcher.match_photo(image)
        except Exception as e:                              # no key, bad image, network: fall back to typing
            print(f"  photo could not be read: {type(e).__name__}: {e}")
            return replies.PHOTO_FAILED
        if res["status"] == "unreadable":
            return replies.PHOTO_FAILED
        return _offer(session, res, always_confirm=True)    # a photo is never trusted without a YES

    if not text or (command in GREETINGS and not rest):
        return replies.HELP
    if command in STOP and not rest:
        watch.remove_all(contact)
        session["pending"] = []
        return replies.STOPPED

    if pending:
        if command in YES and not rest:
            return _show(session, pending[0])
        if command in NO and not rest:
            session["pending"] = []
            return replies.TRY_AGAIN
        if text.isdigit() and 1 <= int(text) <= len(pending):
            return _show(session, pending[int(text) - 1])

    if command == "MORE" and not rest:
        if not session["device_key"]:
            return replies.NO_DEVICE
        rec = get_record(session["device_key"])
        if rec and not rec.get("evidence") and record.has_data():
            rec = dict(rec, evidence=record.top_reports(session["device_key"]))
        return replies.more(rec)
    if command == "SAVE":
        if not session["device_key"]:
            return replies.NO_DEVICE
        rec = get_record(session["device_key"])
        label = rest.strip().strip('"')[:40] or rec["device"]["brand"]
        watch.add(contact, session["device_key"], label, known=alerts.known_refs(rec))
        return replies.saved(label)
    if command in YES | NO and not rest:                    # YES or NO with nothing to answer
        return replies.HELP

    return _offer(session, matcher.match_text(text), always_confirm=False)
