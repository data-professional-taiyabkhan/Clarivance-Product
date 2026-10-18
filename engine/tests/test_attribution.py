import time

import numpy as np
import pytest

from clarivance_engine.attribution import attribute, tax_position
from clarivance_engine.rules import load_rules
from clarivance_engine.tax import liability

R = load_rules()


def two_point(p_over: float, n: int = 2000):
    k = round(n * p_over)
    # other income 45,000 or 55,000; the £1,000 invoice is already inside each year-end
    return np.array([46000.0] * (n - k) + [56000.0] * k)


@pytest.mark.parametrize("p_over,expected", [(0.35, 316.00), (0.60, 356.00)])
def test_plan_attribution_examples(p_over, expected):
    assert attribute(1000.0, two_point(p_over), R) == pytest.approx(expected, abs=0.005)


def test_invoice_straddling_threshold():
    assert attribute(1000.0, np.array([50770.0]), R) == pytest.approx(340.00, abs=0.005)


def test_certain_year_equals_plain_calculation():
    P = np.full(2000, 33600.0)
    assert attribute(1000.0, P, R) == pytest.approx(260.0, abs=1e-6)


def test_reconciliation_adds_up_to_reserve_held():
    rng = np.random.default_rng(3)
    P = rng.normal(52000, 7000, 2000)
    receipts = [(f"{i:03d}", "client", float(a)) for i, a in enumerate(rng.uniform(500, 3000, 25))]
    ytd = sum(a for *_, a in receipts) - 4000
    tp = tax_position(ytd, P, R, receipts)
    assert sum(x["reconciled"] for x in tp.reconciled) == pytest.approx(tp.tax_on_income_so_far, abs=1.0)
    assert tp.reserve_liability >= tp.expected_liability


def test_reserve_covers_80_percent_of_outcomes():
    P = np.random.default_rng(5).normal(52000, 9000, 20000)
    tp = tax_position(30000, P, R, [])
    covered = (liability(P, R) <= tp.reserve_liability).mean()
    assert 0.79 <= covered <= 0.81


def test_speed_2000_year_ends_under_one_second():
    P = np.random.default_rng(1).normal(55000, 12000, 2000)
    t = time.perf_counter()
    liability(P, R)
    attribute(1000.0, P, R)
    assert time.perf_counter() - t < 1.0
