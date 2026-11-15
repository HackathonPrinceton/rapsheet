"""The classifier's text handling, the agreement measure and the reports-rising detector."""
import numpy as np

from pipeline.deaths import passages
from pipeline.evaluate import kappa
from pipeline.warning import months_between, robust_z


def test_passages_put_the_event_description_first_and_cap_length():
    narrative = ("[Additional Manufacturer Narrative] THE DEVICE WAS EVALUATED. " * 30
                 + "\n[Description of Event or Problem] THE PATIENT DID NOT SURVIVE.")
    ps = passages(narrative)
    assert ps[0] == "THE PATIENT DID NOT SURVIVE."
    assert all(len(p) <= 500 for p in ps)
    assert len(ps) <= 10


def test_kappa():
    assert kappa([("1", "1"), ("0", "0"), ("1", "1"), ("0", "0")]) == 1.0
    assert kappa([]) is None
    # 27 of 30 agreeing gives substantial, not perfect, agreement
    pairs = [("1", "1")] * 12 + [("0", "0")] * 15 + [("1", "0"), ("0", "?"), ("0", "?")]
    assert 0.6 < kappa(pairs) < 0.9


def test_reports_rising_flags_a_jump_not_a_steady_device():
    steady = np.array([10.0] * 20)
    assert np.nanmax(robust_z(steady)) < 3
    jump = np.array([10.0] * 19 + [60.0])
    assert robust_z(jump)[-1] >= 3
    assert np.isnan(robust_z(jump)[:6]).all()          # no score before 6 months of history


def test_months_between():
    assert months_between("2024-11", "2025-02") == 3
