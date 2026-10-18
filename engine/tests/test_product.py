from datetime import date, timedelta

import numpy as np
import pytest

from clarivance_engine.engine import run
from clarivance_engine.synthetic import generate
from clarivance_engine.tax import liability
from clarivance_engine.rules import load_rules

R = load_rules()


@pytest.fixture(scope="module")
def outputs():
    return {k: run(generate(k)) for k in ("dan", "marek", "steady")}


def test_reproducible():
    a, b = run(generate("dan")), run(generate("dan"))
    a["meta"].pop("seconds"); b["meta"].pop("seconds")
    assert a == b


def test_full_run_is_fast(outputs):
    for o in outputs.values():
        assert o["meta"]["seconds"] < 1.0


def test_marek_first_january_is_one_and_a_half_times_the_bill(outputs):
    o = outputs["marek"]
    jan = next(p for p in o["taxshield"]["payments"] if p["due"] == "2028-01-31")
    bill = o["taxshield"]["expected_bill"]
    assert jan["expected"] == pytest.approx(1.5 * bill, rel=0.03)


def test_dan_sits_near_the_threshold(outputs):
    t = outputs["dan"]["taxshield"]
    assert 0.2 < t["chance_over"]["50270"] < 0.9
    assert 260 < t["rate_on_next_1000"] < 420
    assert t["reserve_bill"] > t["expected_bill"] > t["single_forecast_bill"]


def test_steady_has_almost_no_uncertainty(outputs):
    t = outputs["steady"]["taxshield"]
    assert t["bill_range"]["p90"] - t["bill_range"]["p10"] < 100
    assert t["rate_on_next_1000"] == pytest.approx(260, abs=1)


def test_payments_on_account_follow_last_years_bill(outputs):
    b = generate("steady")
    poa = b.prev_year_liability / 2
    jan = next(p for p in outputs["steady"]["taxshield"]["payments"] if p["due"] == "2027-01-31")
    assert jan["expected"] == pytest.approx(poa + max(b.prev_balancing_outstanding, 0) + min(b.prev_balancing_outstanding, 0), abs=0.01)


def test_no_payments_on_account_below_1000():
    b = generate("marek")
    assert b.prev_year_liability < 1000
    o = run(b)
    assert not any("2nd payment on account 2026-27" in p["label"] for p in o["taxshield"]["payments"])


def test_safe_to_spend_today_is_cash_less_tax_held(outputs):
    for o in outputs.values():
        h = o["headline"]
        assert h["safe_to_spend_today"] == pytest.approx(h["cash_at_bank"] - h["tax_pot_should_hold"], abs=0.01)


def test_actions_are_templated_and_at_most_three(outputs):
    for o in outputs.values():
        assert len(o["actionflow"]) <= 3
        for a in o["actionflow"]:
            assert "£" in a["text"]


def test_curve_has_52_weeks_and_band_is_ordered(outputs):
    for o in outputs.values():
        c = o["curve"]
        assert len(c) == 52
        assert all(w["p10"] <= w["safe"] <= w["p50"] <= w["p90"] for w in c)


def test_curve_starts_close_to_safe_to_spend_today(outputs):
    for o in outputs.values():
        today, first = o["headline"]["safe_to_spend_today"], o["curve"][0]["safe"]
        assert abs(first - today) < 0.15 * max(abs(today), 2000) + 1500
