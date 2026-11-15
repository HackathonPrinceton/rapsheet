"""End to end on the real data: search, a device record, the bot reply, and the page."""
from conftest import needs_data

from bot import replies
from service import record

DEMO = "physio--lifepak-cr2-defibrillator"


@needs_data
def test_search_finds_the_right_device():
    assert record.search("lifepak cr2")[0]["device_key"] == DEMO
    assert record.search("lifepak 15")[0]["device_key"].startswith("physio--lifepak-15")
    assert record.search("xyz unknown thing") == []


@needs_data
def test_record_and_reply_agree():
    rec = record.build(DEMO)
    assert rec["totals"]["deaths_coded"] > 0 and rec["recalls"]
    text = replies.summary(rec, "https://example.org/page")
    assert f"{rec['totals']['deaths_coded']} are coded as deaths" in text
    assert "not proof" in text                                  # the disclaimer is always there


@needs_data
def test_page_renders_every_tab():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file("../page/app.py", default_timeout=240)
    at.query_params["d"] = DEMO
    at.run()
    assert not at.exception
    assert len(at.tabs) == 5


def test_ask_page_off_by_default_shows_saved_investigations(monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv("ENABLE_ASK", "0")
    at = AppTest.from_file("../page/ask.py", default_timeout=120)
    at.run()
    assert not at.exception
    assert not at.button                                   # no way to start a paid run


@needs_data
def test_patient_page_has_three_tabs_and_plain_answers():
    from streamlit.testing.v1 import AppTest
    for key, expect in ((DEMO, "recalls are open"), ("respironics--dreamstation-auto-cpap", "less reliable for CPAP")):
        at = AppTest.from_file("../page/patient.py", default_timeout=240)
        at.query_params["d"] = key
        at.run()
        assert not at.exception
        assert len(at.tabs) == 3
        assert any(expect in m.value for m in at.markdown)
