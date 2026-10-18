import csv
from pathlib import Path

import numpy as np
import pytest

from clarivance_engine.rules import load_rules
from clarivance_engine.tax import class4, income_tax, liability, marginal_rate

R = load_rules()
SUITE = list(csv.DictReader(open(Path(__file__).parents[1] / "scenarios" / "suite-v0.csv")))


@pytest.mark.parametrize("row", SUITE, ids=[r["id"] for r in SUITE])
def test_scenario_suite(row):
    p = float(row["trading_profit"])
    assert float(income_tax(p, R)) == pytest.approx(float(row["expected_income_tax"]), abs=0.005)
    assert float(class4(p, R)) == pytest.approx(float(row["expected_class4"]), abs=0.005)
    assert float(liability(p, R)) == pytest.approx(float(row["expected_total"]), abs=0.005)


@pytest.mark.parametrize("profit,rate", [(30000, 0.26), (70000, 0.42), (110000, 0.62), (140000, 0.47)])
def test_marginal_rates(profit, rate):
    assert marginal_rate(profit, R) == pytest.approx(rate, abs=1e-9)


def test_vectorised_matches_scalar():
    xs = np.linspace(-1000, 200000, 501)
    assert np.allclose(liability(xs, R), [float(liability(x, R)) for x in xs])


def test_single_forecast_gap_from_plan_4_6_2():
    avg_bill = float(liability(np.array([40000.0, 70000.0]), R).mean())
    assert avg_bill == pytest.approx(12610.20, abs=0.005)
    assert avg_bill - float(liability(55000.0, R)) == pytest.approx(821.60, abs=0.005)
