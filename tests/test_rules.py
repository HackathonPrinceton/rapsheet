"""Plain rules: late reporting, name cleaning, recall matching, the keyword baseline."""
import datetime as dt

from pipeline.deathwords import STATES_DEATH, excerpt, has_death_word
from pipeline.match import core_phrase, norm, recall_matches
from pipeline.pull import late_class
from pipeline.store import clean_manufacturer, device_key

D = dt.date


def test_late_reporting_rule():
    m = "Manufacturer report"
    assert late_class(D(2024, 1, 1), D(2024, 1, 31), m) == (30, "on_time")      # day 30 is still on time
    assert late_class(D(2024, 1, 1), D(2024, 2, 1), m) == (31, "late")
    assert late_class(D(2024, 1, 1), D(2024, 7, 1), m) == (182, "very_late")
    assert late_class(None, D(2024, 1, 1), m) == (None, "unknown")
    assert late_class(D(2024, 2, 1), D(2024, 1, 1), m) == (None, "unknown")      # received before aware
    assert late_class(D(2024, 1, 1), D(2024, 9, 1), "Voluntary report")[1] == "not_manufacturer"


def test_manufacturer_names_and_device_keys():
    assert clean_manufacturer("PHILIPS GOLDWAY (SHENZHEN) INDUSTRIAL INC.") == "PHILIPS GOLDWAY"
    assert device_key("PHYSIO-CONTROL, INC.", "LIFEPAK(R) CR2 DEFIBRILLATOR") == "physio--lifepak-cr2-defibrillator"


def test_recall_matching_needs_maker_and_model():
    assert core_phrase("LIFEPAK(R) CR2 DEFIBRILLATOR") == "lifepak cr2"
    text = norm("Physio-Control LIFEPAK CR2 Defibrillator, model 99512")
    assert recall_matches(text, "PHYSIO CONTROL", "LIFEPAK CR2 DEFIBRILLATOR")
    assert not recall_matches(text, "PHYSIO CONTROL", "LIFEPAK 15 MONITOR/DEFIBRILLATOR")   # other model
    assert not recall_matches(text, "ZOLL MEDICAL", "LIFEPAK CR2 DEFIBRILLATOR")            # other maker


def test_keyword_baseline_is_broad_on_purpose():
    # These are why keyword search is wrong most of the time: none describe a patient dying.
    for text in ("THE BATTERY WAS DEAD.", "THE PADS WERE EXPIRED.", "NO DEATH OR SERIOUS INJURY WAS REPORTED."):
        assert has_death_word(text)
    assert not has_death_word("THE DEVICE DISPLAYED A SERVICE CODE.")


def test_states_death_skips_equipment_wording():
    assert STATES_DEATH.search("THE PATIENT DID NOT SURVIVE.")
    assert STATES_DEATH.search("THE PATIENT PASSED AWAY AT HOME.")
    assert not STATES_DEATH.search("THE BATTERY WAS DEAD AND THE PADS WERE REPLACED.")


def test_excerpt_centres_on_the_death_sentence():
    text = "A" * 400 + " THE PATIENT DID NOT SURVIVE. " + "B" * 400
    out = excerpt(text, width=120)
    assert "DID NOT SURVIVE" in out and out.startswith("...") and out.endswith("...")
