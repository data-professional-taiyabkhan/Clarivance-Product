"""Seeded synthetic businesses based on the plan's personas (section 6.3).

Everything here is invented. No real person's or client's data is used (plan 19.7).
The generator simulates the business from its start date up to the as-of date,
including HMRC payments, so the bank balance and last year's bill are consistent.
For years before 2026-27 the 2026-27 rules are used as a stand-in (thresholds were frozen).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np

from .calendar import payment_dates, tax_year_end, tax_year_start
from .models import Business, Invoice, Outflow
from .rules import RuleSet, load_rules
from .tax import liability

GENERATOR_VERSION = "synthetic-v0"


@dataclass(frozen=True)
class Client:
    name: str
    monthly_jobs: float          # mean invoices per month
    job_median: float            # median invoice value (£)
    job_sigma: float             # log-normal spread of invoice values
    delay_mean: float            # mean days to pay
    delay_sd: float


@dataclass(frozen=True)
class Persona:
    key: str
    name: str
    trade: str
    start: date
    default_as_of: date
    opening_cash: float
    clients: tuple[Client, ...]
    expense_share: float         # allowable costs as a share of invoiced work
    fixed_costs: float           # monthly allowable fixed costs
    drawings: float              # monthly personal drawings
    seasonality: tuple[float, ...]   # Jan..Dec multipliers on job volume
    liability_before_start: float    # bill for the year before the first simulated year
    description: str
    seed: int


FLAT = (1.0,) * 12
TRADES = (0.6, 0.7, 1.0, 1.1, 1.15, 1.15, 1.1, 1.05, 1.1, 1.1, 1.0, 0.65)

PERSONAS: dict[str, Persona] = {
    "dan": Persona(
        key="dan", name="Dan", trade="Self-employed electrician",
        start=date(2024, 4, 6), default_as_of=date(2026, 10, 18), opening_cash=6000,
        clients=(
            Client("Hartley Builders", 0.7, 2600, 0.35, 62, 9),
            Client("Kemp Construction", 0.6, 2400, 0.35, 58, 11),
            Client("Domestic jobs", 1.9, 1100, 0.55, 9, 5),
        ),
        expense_share=0.18, fixed_costs=420, drawings=3300, seasonality=TRADES,
        liability_before_start=9000,
        description="Profit between about £45,000 and £60,000 depending on the year. Two builders pay at about 60 days.",
        seed=20261018,
    ),
    "marek": Persona(
        key="marek", name="Marek", trade="First-year consultant",
        start=date(2026, 4, 6), default_as_of=date(2027, 2, 15), opening_cash=15000,
        clients=(
            Client("Northbank Advisory", 1.0, 4600, 0.30, 30, 7),
            Client("Calder Group", 1.0, 3300, 0.40, 45, 14),
        ),
        expense_share=0.04, fixed_costs=300, drawings=3600, seasonality=FLAT,
        liability_before_start=0,
        description="Left employment for his first self-employed year. Has never paid a payment on account.",
        seed=20270215,
    ),
    "steady": Persona(
        key="steady", name="Steady", trade="Retained bookkeeper (control case)",
        start=date(2024, 4, 6), default_as_of=date(2026, 10, 18), opening_cash=4000,
        clients=(Client("Single retained client", 1.0, 3000, 0.0, 14, 0.5),),
        expense_share=0.0, fixed_costs=200, drawings=2300, seasonality=FLAT,
        liability_before_start=3400,
        description="One client paying the same fee every month. Almost nothing is uncertain.",
        seed=1,
    ),
}


def _month_starts(start: date, end: date):
    d = date(start.year, start.month, 1)
    while d <= end:
        yield d
        d = date(d.year + (d.month == 12), d.month % 12 + 1, 1)


def generate(key: str, as_of: date | None = None, rules: RuleSet | None = None) -> Business:
    p = PERSONAS[key]
    rules = rules or load_rules()
    as_of = as_of or p.default_as_of
    rng = np.random.default_rng(p.seed)
    horizon_end = as_of + timedelta(days=800)   # simulate past as_of so outstanding invoices have true dates; we hide them

    invoices: list[Invoice] = []
    outflows: list[Outflow] = []
    n = 0
    for m in _month_starts(p.start, as_of):
        season = p.seasonality[m.month - 1]
        for c in p.clients:
            jobs = rng.poisson(c.monthly_jobs * season) if c.job_sigma > 0 else 1
            for _ in range(jobs):
                day = m + timedelta(days=int(rng.integers(0, 28)))
                if day < p.start or day > as_of:
                    continue
                amt = round(float(c.job_median * np.exp(rng.normal(0, c.job_sigma))), 2) if c.job_sigma > 0 else c.job_median
                delay = max(1, int(round(rng.normal(c.delay_mean, c.delay_sd))))
                n += 1
                paid = day + timedelta(days=delay)
                invoices.append(Invoice(f"{n:03d}", c.name, day, amt, paid))
                if p.expense_share:
                    outflows.append(Outflow(day + timedelta(days=3), round(amt * p.expense_share, 2), "expense", "Materials and subcontract"))
        for day, amt, kind, lab in ((m + timedelta(days=6), p.fixed_costs, "expense", "Van, insurance, phone"),
                                    (m + timedelta(days=27), p.drawings, "drawings", "Transfer to personal account")):
            if p.start <= day <= as_of:
                outflows.append(Outflow(day, amt, kind, lab))

    # Tax history: compute each completed or running year's bill on the cash basis and pay HMRC on the real dates.
    def profit_for(ys: date) -> float:
        ye = date(ys.year + 1, 4, 5)
        rec = sum(i.amount for i in invoices if i.paid and ys <= i.paid <= ye)
        exp = sum(o.amount for o in outflows if o.kind == "expense" and ys <= o.day <= ye)
        return rec - exp

    years = []
    ys = tax_year_start(p.start)
    while ys <= tax_year_start(as_of):
        years.append(ys)
        ys = date(ys.year + 1, 4, 6)
    bills = {}
    prev_bill = p.liability_before_start
    for ys in years:
        bills[ys] = float(liability(profit_for(ys), rules)) if tax_year_end(ys) < as_of or ys < tax_year_start(as_of) else None
    hmrc: list[Outflow] = []
    prev = p.liability_before_start
    poa_paid_for: dict[date, float] = {}
    for ys in years:
        dates = payment_dates(ys)
        poa = prev * rules.poa_share if prev >= rules.poa_minimum_bill else 0.0
        poa_paid_for[ys] = 0.0
        for k in ("poa1", "poa2"):
            if poa and dates[k] <= as_of:
                hmrc.append(Outflow(dates[k], round(poa, 2), "hmrc", f"HMRC payment on account ({k[-1]}) {ys.year}-{str(ys.year+1)[2:]}"))
                poa_paid_for[ys] += poa
        bill = bills[ys]
        if bill is not None and dates["balancing"] <= as_of:
            bal = bill - (2 * poa)
            if bal > 0:
                hmrc.append(Outflow(dates["balancing"], round(bal, 2), "hmrc", f"HMRC balancing payment {ys.year}-{str(ys.year+1)[2:]}"))
        if bill is not None:
            prev = bill
    outflows += hmrc

    # Hide what the bank feed could not know yet: payments after as_of.
    visible = []
    for i in invoices:
        visible.append(Invoice(i.id, i.client, i.issued, i.amount, i.paid if i.paid <= as_of else None))
    flows = [o for o in outflows if o.day <= as_of]
    cash = p.opening_cash + sum(i.amount for i in visible if i.paid) - sum(o.amount for o in flows)

    cur = tax_year_start(as_of)
    last = date(cur.year - 1, 4, 6)
    prev_bill = bills.get(last) if last in bills and bills.get(last) is not None else p.liability_before_start
    prev_poa = 0.0
    if last in poa_paid_for:
        prev_poa = poa_paid_for[last]
        # payments on account for the previous year that fall after as_of are not possible (they precede its balancing date)
    prev_bal = 0.0
    if last in bills and bills[last] is not None and payment_dates(last)["balancing"] > as_of:
        before_last = date(last.year - 1, 4, 6)
        basis = bills.get(before_last) if bills.get(before_last) is not None else p.liability_before_start
        last_poa_total = 2 * (basis * rules.poa_share if basis >= rules.poa_minimum_bill else 0.0)
        prev_bal = bills[last] - last_poa_total   # negative = overpaid, credited against the next payment

    return Business(
        key=p.key, name=p.name, trade=p.trade, as_of=as_of, cash=round(cash, 2),
        invoices=visible, outflows=flows, trading_since=p.start,
        prev_year_liability=round(prev_bill, 2),
        prev_balancing_outstanding=round(prev_bal, 2),
        paid_towards_current_year=round(poa_paid_for.get(cur, 0.0), 2),
        notes=[p.description, f"Synthetic data ({GENERATOR_VERSION}, seed {p.seed})."],
    )
