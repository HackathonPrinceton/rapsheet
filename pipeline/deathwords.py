"""The death-related wording used across the project, defined once.

ANY_DEATH_WORD   broad, on purpose: any word a keyword search would catch, including "the battery was
                 dead" and "pads expired". It is the keyword baseline the classifier is compared with,
                 and it picks the reports a labeller should look at.
STATES_DEATH     phrases that state a death ("did not survive", "passed away"). Used to pick the sentence
                 to quote, and to highlight it on the page.
"""
import re

ANY_DEATH_WORD = re.compile(
    r"\b(died|dies|dead|death|deceased|expired?|expir\w+|passed away|fatal\w*|demise|did not survive|"
    r"not survive|not be revived|unable to revive|could not be resuscitated|resuscitation (was |efforts? )?"
    r"(were |was )?(unsuccessful|ceased|stopped|terminated)|pronounced|autopsy|succumbed|mortality)\b", re.I)

STATES_DEATH = re.compile(
    r"did not survive|not survive|died|passed away|deceased|expired(?! battery| pads)|"
    r"not (?:be )?resuscitated|pronounced|cause of death|patient death|death of|fatal|demise|succumbed", re.I)


def has_death_word(text: str) -> bool:
    """The keyword baseline: does the text contain any death-related word at all."""
    return bool(ANY_DEATH_WORD.search(text or ""))


def excerpt(text: str, width: int = 260) -> str:
    """The part of a narrative around the first phrase that states a death (or any death word)."""
    text = re.sub(r"\s+", " ", text or "")
    hit = STATES_DEATH.search(text) or ANY_DEATH_WORD.search(text)
    if not hit:
        return text[:width]
    start = max(0, hit.start() - width // 2)
    return ("..." if start else "") + text[start:start + width] + ("..." if start + width < len(text) else "")
