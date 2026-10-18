"""One call that turns a business snapshot into everything the home screen needs (plan 4.1)."""
from __future__ import annotations

import time
from datetime import timedelta

import numpy as np

from . import __version__
from .actions import explain_change, weekly_actions
from .attribution import tax_position
from .calendar import label, tax_year_end, tax_year_start
from .curve import hmrc_schedule, safe_to_spend_curve
from .forecast import simulate
from .models import Business
from .rules import RuleSet, load_rules


def _position(b: Business, r: RuleSet, n: int, seed: int, confidence: float):
    sim = simulate(b, n=n, seed=seed)
    ys = tax_year_start(b.as_of)
    receipts = [(i.id, i.client, i.amount) for i in b.receipts(ys, b.as_of)]
    tax = tax_position(sim.ytd_profit, sim.year_end_profit, r, receipts, b.paid_towards_current_year, confidence)
    return sim, tax


def run(b: Business, r: RuleSet | None = None, n: int = 2000, seed: int = 7, confidence: float = 0.8,
        last_week: Business | None = None) -> dict:
    r = r or load_rules()
    t0 = time.perf_counter()
    sim, tax = _position(b, r, n, seed, confidence)
    payments = hmrc_schedule(b, sim, r)
    curve = safe_to_spend_curve(b, sim, r, payments, confidence)
    owed_prev = max(b.prev_balancing_outstanding, 0.0)
    safe_today = b.cash - tax.hold_now - owed_prev
    actions = weekly_actions(b, sim, tax, curve, safe_today)
    change = None
    if last_week is not None:
        _, prev_tax = _position(last_week, r, n, seed, confidence)
        change = explain_change(prev_tax, tax)
    elapsed = time.perf_counter() - t0

    P = sim.year_end_profit
    ys = tax_year_start(b.as_of)
    return {
        "business": {"key": b.key, "name": b.name, "trade": b.trade, "as_of": b.as_of.isoformat(),
                     "trading_since": b.trading_since.isoformat(), "notes": b.notes,
                     "history_months": round(sim.history_months, 1)},
        "headline": {
            "safe_to_spend_today": round(safe_today, 2),
            "cash_at_bank": round(b.cash, 2),
            "tax_pot_should_hold": round(tax.hold_now + owed_prev, 2),
            "reserve_change": change,
        },
        "cashradar": {
            "tax_year": label(ys),
            "year_end": tax_year_end(b.as_of).isoformat(),
            "profit_so_far": round(sim.ytd_profit, 2),
            "year_end_profit": {k: round(float(np.quantile(P, q)), 2) for k, q in (("p10", .1), ("p50", .5), ("p90", .9))},
            "outstanding_invoices": [
                {"id": i.id, "client": i.client, "amount": i.amount, "age_days": i.age(b.as_of),
                 "client_usually_pays_in": round(sim.patterns[i.client].median_delay),
                 "expected_by": (b.as_of + timedelta(days=int(np.median(sim.outstanding_arrival[i.id])))).isoformat()}
                for i in sorted(b.outstanding(), key=lambda i: i.issued)],
            "clients": [{"client": p.client, "usually_pays_in": round(p.median_delay), "invoices_seen": int(len(p.delays))}
                        for p in sim.patterns.values()],
        },
        "taxshield": {
            "expected_bill": tax.expected_liability,
            "reserve_bill": tax.reserve_liability,
            "confidence": tax.confidence,
            "bill_range": {"p10": tax.liability_p10, "p90": tax.liability_p90},
            "single_forecast_bill": tax.single_forecast_liability,
            "tax_on_income_so_far": tax.tax_on_income_so_far,
            "already_paid_for_year": tax.paid_towards_year,
            "hold_now": tax.hold_now,
            "last_year_balance_owed": round(owed_prev, 2),
            "rate_on_next_1000": tax.rate_on_next_1000,
            "chance_over": tax.p_over,
            "payments": [{"due": p.due.isoformat(), "label": p.label,
                          "expected": round(float(np.median(p.amount)), 2),
                          "at_confidence": round(float(np.quantile(p.amount, confidence)), 2)} for p in payments],
            "transactions": sorted(tax.reconciled, key=lambda x: x["id"])[-12:],
        },
        "curve": [{"week_ending": w.isoformat(), "safe": round(float(s_), 2), "p10": round(float(a), 2),
                   "p50": round(float(m), 2), "p90": round(float(c), 2), "cash_p50": round(float(d), 2)}
                  for w, s_, a, m, c, d in zip(curve.weeks, curve.safe, curve.p10, curve.p50, curve.p90, curve.cash_p50)],
        "actionflow": actions,
        "meta": {"engine": __version__, "rules": r.id, "rules_signed_off": bool(r.signed_off_by),
                 "forecast": sim.version, "simulations": n, "seconds": round(elapsed, 3),
                 "label": "Estimates on synthetic data. Not tax advice."},
    }
