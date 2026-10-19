"""Safe-to-spend curve and HMRC payment schedule (plan 4.6.2 'The forward curve').

safe_to_spend(week) = projected cash at that week (after receipts, costs, drawings and any HMRC
payment falling due) minus tax built up but not yet paid. Computed per simulation, then summarised.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np

from .calendar import label, payment_dates, tax_year_start
from .forecast import Simulation
from .models import Business
from .rules import RuleSet
from .tax import liability


@dataclass
class Payment:
    due: date
    label: str
    amount: np.ndarray        # (n,) per simulation
    year: str


def hmrc_schedule(b: Business, sim: Simulation, r: RuleSet) -> list[Payment]:
    n = sim.n
    ys = tax_year_start(b.as_of)
    last = date(ys.year - 1, 4, 6)
    cur, prev_dates = payment_dates(ys), payment_dates(last)
    end = sim.weeks[-1]
    L_cur = liability(sim.year_end_profit, r)
    poa_cur = b.prev_year_liability * r.poa_share if b.prev_year_liability >= r.poa_minimum_bill else 0.0
    out: list[Payment] = []

    def add(due, lab, amount, year):
        if b.as_of < due <= end and np.any(np.abs(np.asarray(amount, float)) >= 0.005):
            out.append(Payment(due, lab, np.broadcast_to(np.asarray(amount, float), (n,)).copy(), year))

    add(prev_dates["balancing"], f"Balancing payment {label(last)}", b.prev_balancing_outstanding, label(last))
    add(cur["poa1"], f"1st payment on account {label(ys)}", poa_cur, label(ys))
    add(cur["poa2"], f"2nd payment on account {label(ys)}", poa_cur, label(ys))
    bal_cur = L_cur - 2 * poa_cur
    add(cur["balancing"], f"Balancing payment {label(ys)}", bal_cur, label(ys))
    nxt = date(ys.year + 1, 4, 6)
    poa_next = np.where(L_cur >= r.poa_minimum_bill, L_cur * r.poa_share, 0.0)
    add(payment_dates(nxt)["poa1"], f"1st payment on account {label(nxt)}", poa_next, label(nxt))
    # merge payments that share a date (HMRC takes them together on 31 January)
    merged: dict[date, Payment] = {}
    for p in out:
        if p.due in merged:
            m = merged[p.due]
            merged[p.due] = Payment(p.due, m.label + " + " + p.label, m.amount + p.amount, m.year)
        else:
            merged[p.due] = p
    return sorted(merged.values(), key=lambda p: p.due)


@dataclass
class Curve:
    weeks: list[date]
    p10: np.ndarray
    safe: np.ndarray            # (1 - confidence) quantile
    p50: np.ndarray
    p90: np.ndarray
    cash_p50: np.ndarray
    payments: list[Payment]
    per_sim: np.ndarray


def safe_to_spend_curve(b: Business, sim: Simulation, r: RuleSet, payments: list[Payment], confidence: float = 0.8) -> Curve:
    n, W = sim.n, len(sim.weeks)
    ys = tax_year_start(b.as_of)
    week_ends = np.array([(w - b.as_of).days for w in sim.weeks])
    paid = np.zeros((n, W))
    paid_cur = np.full((n, W), float(b.paid_towards_current_year))
    prev_owed = np.full((n, W), float(max(b.prev_balancing_outstanding, 0.0)))
    for p in payments:
        k = int(((p.due - b.as_of).days - 1) // 7)
        paid[:, k:] += p.amount[:, None]
        if p.year == label(ys):
            paid_cur[:, k:] += p.amount[:, None]
        if p.year == label(date(ys.year - 1, 4, 6)):
            prev_owed[:, k:] = 0.0
    net = sim.receipts - sim.expenses - sim.drawings[None, :]
    cash = b.cash + np.cumsum(net, axis=1) - paid

    P = sim.year_end_profit
    L = liability(P, r)
    # Tax built up by each week = tax attributable to the profit made so far, given where that
    # simulated year ends (same attribution idea as the reserve, so today's figure and the curve agree).
    Y = np.clip(sim.profit_to_week, 0, None)
    accrued_cur = L[:, None] - liability(P[:, None] - Y, r)
    avg_rate = np.divide(L, P, out=np.zeros_like(L), where=P > 0)
    accrued_next = np.maximum(sim.next_year_profit_to_week, 0) * avg_rate[:, None]
    owed = np.maximum(accrued_cur - paid_cur, 0) + prev_owed + accrued_next
    # payments on account for next year already made inside the horizon reduce what is still owed
    for p in payments:
        if p.year == label(date(ys.year + 1, 4, 6)):
            k = int(((p.due - b.as_of).days - 1) // 7)
            owed[:, k:] = np.maximum(owed[:, k:] - p.amount[:, None], 0)
    safe = cash - owed
    q = lambda x: np.quantile(safe, x, axis=0)
    # "safe" line: the amount that is safe with the chosen confidence (e.g. 80% of outcomes are at least this)
    return Curve(sim.weeks, q(0.1), q(1 - confidence), q(0.5), q(0.9), np.quantile(cash, 0.5, axis=0), payments, safe)
