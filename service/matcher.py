"""Match what a user sent (typed text or a photo of a label) to a device in the database.

Both paths end in the same place: a list of candidate devices plus a status.
  "sure"  one clear match
  "ask"   several possible matches, the user must pick
  "none"  nothing found
"""
import base64
import io
import json
import os

from . import record

MODEL = os.environ.get("RAPSHEET_VISION_MODEL", "claude-opus-5-5")

LABEL_PROMPT = (
    "This is a photo of a medical device or its label. Read only what is printed. "
    "Give the brand or product name (for example 'HeartStart FRx'), the model or reference number, "
    "and the manufacturer. Use an empty string for anything you cannot read. "
    "Set readable to false if this is not a device label or the text cannot be read. Do not guess."
)
LABEL_SCHEMA = {
    "type": "object",
    "properties": {
        "readable": {"type": "boolean"},
        "brand": {"type": "string"},
        "model": {"type": "string"},
        "manufacturer": {"type": "string"},
    },
    "required": ["readable", "brand", "model", "manufacturer"],
    "additionalProperties": False,
}


def _to_jpeg(image: bytes) -> bytes:
    """Phones send large photos, often as HEIC. Shrink and convert so the model can read them."""
    from PIL import Image
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
    except ImportError:
        pass
    img = Image.open(io.BytesIO(image)).convert("RGB")
    img.thumbnail((1568, 1568))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=85)
    return out.getvalue()


def read_label(image: bytes) -> dict:
    """Photo bytes -> {"readable", "brand", "model", "manufacturer"}."""
    import anthropic
    client = anthropic.Anthropic()
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=4000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": LABEL_SCHEMA}},
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                         "data": base64.standard_b64encode(_to_jpeg(image)).decode()}},
            {"type": "text", "text": LABEL_PROMPT},
        ]}],
    )
    unreadable = {"readable": False, "brand": "", "model": "", "manufacturer": ""}
    if response.stop_reason in ("refusal", "max_tokens"):
        return unreadable
    text = next((b.text for b in response.content if b.type == "text"), "")
    try:
        return json.loads(text)
    except ValueError:
        return unreadable


def _result(query: str, matches: list[dict]) -> dict:
    if not matches:
        return {"status": "none", "query": query, "matches": []}
    top = matches[0]["score"]
    clear = top >= 0.75 and (len(matches) == 1 or top - matches[1]["score"] >= 0.1)
    return {"status": "sure" if clear else "ask", "query": query, "matches": matches}


def match_text(q: str) -> dict:
    q = (q or "").strip()
    if not record.has_data():                      # no database yet: the made-up sample device
        s = record.sample_record()
        return _result(q, [{"device_key": s["device_key"], **s["device"], "score": 1.0}])
    return _result(q, record.search(q))


def match_photo(image: bytes) -> dict:
    """Read the label, then look the text up the same way as a typed name."""
    label = read_label(image)
    if not label.get("readable") or not (label["brand"] or label["model"] or label["manufacturer"]):
        return {"status": "unreadable", "query": "", "matches": [], "label": label}
    # The database is keyed on brand and maker; model numbers on labels rarely match, so try them last.
    tries = [f"{label['brand']} {label['manufacturer']}", label["brand"],
             f"{label['manufacturer']} {label['model']}"]
    best = {"status": "none", "query": tries[0].strip(), "matches": []}
    for q in tries:
        if not q.strip():
            continue
        res = match_text(q)
        if res["matches"] and (not best["matches"] or res["matches"][0]["score"] > best["matches"][0]["score"]):
            best = res
    best["label"] = label
    return best
