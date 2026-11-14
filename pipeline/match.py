"""Link a recall to the device families it covers.

Recalls name a firm and describe the product in free text. Reports carry a brand name.
A recall matches a device when the maker's first word and the brand's core phrase both
appear in the recall text.
"""
import re

# Words that describe the kind of device, not which one it is.
GENERIC = {
    "defibrillator", "defibrillators", "monitor", "aed", "series", "kit", "semi", "automatic", "auto",
    "automated", "external", "system", "systems", "device", "with", "and", "the", "for", "cpap", "bipap",
    "bilevel", "ventilator", "unit", "model", "fully", "trainer", "pads", "electrode", "electrodes",
    "battery", "defib", "humidifier", "heated", "machine", "continuous", "positive", "airway", "pressure",
}


def norm(text: str) -> str:
    text = re.sub(r"\((r|tm|c)\)|®|™", "", text or "", flags=re.I)
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def core_phrase(brand: str) -> str:
    """'LIFEPAK(R) CR2 DEFIBRILLATOR' -> 'lifepak cr2'.  Empty when nothing distinctive is left."""
    words = norm(brand).split()
    kept = [w for w in words if w not in GENERIC]
    if len("".join(kept)) < 3:          # 'X SERIES' -> keep the full phrase rather than 'x'
        kept = words
    phrase = " ".join(kept)
    return phrase if len(phrase.replace(" ", "")) >= 3 else ""


def recall_matches(recall_text: str, maker: str, brand: str) -> bool:
    """recall_text must already be passed through norm()."""
    first = (norm(maker).split() or [""])[0]
    phrase = core_phrase(brand)
    if not first or not phrase:
        return False
    padded = f" {recall_text} "
    return f" {first}" in padded and f" {phrase} " in padded
