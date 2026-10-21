"""ActionFlow: up to three plain-English actions a week, from templates only (plan 4.5: no LLMs)."""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from .attribution import TaxPosition
from .curve import Curve
from .forecast import Simulation
from .models import Business


def _fmt(x: float) -> str:
    return f"£{x:,.0f}"


def _d(d: date) -> str:
    return f"{d.day} {d.strftime('%B')}"


def weekly_actions(b: Business, sim: Simulation, tax: TaxPosition, curve: Curve, safe_today: float) -> list[dict]:
    out: list[dict] = []

    # 1. Invoices from slow payers: what happens if this one arrives as late as usual.
    first_negative = next((w for w, v in zip(curve.weeks, curve.safe) if v < 0), None)
    candidates = []
    for inv in b.outstanding():
        pat = sim.patterns[inv.client]
        age = inv.age(b.as_of)
        typical = pat.median_delay
        if inv.amount >= 500 and (typical >= 21 or age > 30):
            arrival = sim.outstanding_arrival[inv.id]
            expected = b.as_of + timedelta(days=int(np.median(arrival)))
            candidates.append((inv.amount, inv, age, typical, expected))
    for amount, inv, age, typical, expected in sorted(candidates, key=lambda c: (-c[0], c[1].id))[:1]:
        ref = f"Invoice {inv.id.replace('open-', '#')}" if not inv.id.startswith("open-") else f"Your invoice to {inv.client}"
        if typical >= 21:
            text = (f"{ref} ({_fmt(inv.amount)}) is {age} days old, and {inv.client} usually takes {typical:.0f} days to pay.")
        else:
            text = f"{ref} ({_fmt(inv.amount)}) was sent {age} days ago and hasn't been paid."
        if first_negative and first_negative < expected + timedelta(days=7):
            text += f" If it arrives that late, your cash after tax goes below zero in the week of {_d(first_negative)}. Chase it this week."
        elif age > max(typical, 30):
            text += " Chase it this week." if typical < 21 else " It is now later than usual. Chase it this week."
        else:
            continue
        out.append({"kind": "chase", "module": "CashRadar", "text": text})

    # 2. The next HMRC payment: amount, what is set aside, any shortfall.
    upcoming = [p for p in curve.payments if (p.due - b.as_of).days <= 120]
    if upcoming:
        p = upcoming[0]
        amt = float(np.quantile(p.amount, 0.8))
        weeks_left = (p.due - b.as_of).days // 7
        text = f"{_fmt(amt)} is due to HMRC on {_d(p.due)} {p.due.year} ({p.label.lower()}), in {weeks_left} weeks."
        if safe_today < 0:
            text += f" Your cash after tax is already {_fmt(-safe_today)} short. Look at Time to Pay with HMRC early rather than late."
        else:
            text += f" Keep at least {_fmt(tax.hold_now + max(b.prev_balancing_outstanding, 0))} in your tax pot from now on."
        out.append({"kind": "payment", "module": "TaxShield", "text": text})

    # 2b. A first-year customer's first January: this year's bill plus half again (plan 6.3, Marek).
    if b.prev_year_liability < 1000:
        for p in curve.payments:
            if "payment on account" in p.label and "Balancing" in p.label and p not in upcoming[:1]:
                amt = float(np.median(p.amount))
                out.append({"kind": "first_january", "module": "TaxShield", "text":
                            f"On {_d(p.due)} {p.due.year} HMRC will ask for about {_fmt(amt)}: this year's whole bill plus half of it "
                            f"again as an advance on next year. That is one and a half times what most people expect, so it is "
                            f"already built into your safe-to-spend figure."})
                break

    # 2c. Cash after tax dipping below zero in the next six months.
    if first_negative and (first_negative - b.as_of).days <= 182 and not any(a["kind"] == "chase" for a in out):
        k = curve.weeks.index(first_negative)
        low = float(min(curve.safe[k:k + 8]))
        out.append({"kind": "dip", "module": "CashRadar", "text":
                    f"On current patterns your cash after tax could fall below zero in the week of {_d(first_negative)}, "
                    f"by up to {_fmt(-low)}. Keeping drawings a little lower until then, or bringing invoices forward, avoids it."})

    # 3. Near a threshold: the real cost of the next invoice.
    p50 = tax.p_over["50270"]
    p100 = tax.p_over["100000"]
    if 0.15 <= p100 <= 0.85:
        out.append({"kind": "threshold", "module": "TaxShield", "text":
                    f"There is a {p100:.0%} chance your profit ends above £100,000, where you start losing your personal allowance. "
                    f"Each extra £1,000 you receive before 5 April is costing about {_fmt(tax.rate_on_next_1000)} in tax."})
    elif 0.15 <= p50 <= 0.85:
        out.append({"kind": "threshold", "module": "TaxShield", "text":
                    f"There is a {p50:.0%} chance your profit ends above £50,270, where the rate rises from 26% to 42%. "
                    f"Each extra £1,000 you receive before 5 April is set aside at about {_fmt(tax.rate_on_next_1000)}."})
    return out[:3]


def explain_change(prev: TaxPosition, cur: TaxPosition) -> str | None:
    """Why the reserve moved since last week, in one sentence (plan 4.6.2: 'The customer sees the reserve move and sees why')."""
    delta = cur.hold_now - prev.hold_now
    if abs(delta) < 1:
        return None
    direction = "up" if delta > 0 else "down"
    a, c = prev.p_over["50270"], cur.p_over["50270"]
    if abs(c - a) >= 0.05:
        why = f"the chance of finishing above £50,270 moved from {a:.0%} to {c:.0%}"
    elif cur.tax_on_income_so_far != prev.tax_on_income_so_far:
        why = "money you received this week added to this year's tax"
    else:
        why = "the forecast for the rest of the year changed"
    return f"Reserve {direction} {_fmt(abs(delta))}: {why}."
