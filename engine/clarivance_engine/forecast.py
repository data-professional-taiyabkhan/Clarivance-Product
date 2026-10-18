"""CashRadar v0: Monte Carlo of the rest of the year from the business's own history.

The forecasting components are deliberately simple and are not the innovation (plan 4.6.3).
What matters is that the output is a full distribution of outcomes, which the tax engine
then evaluates in one pass. A thin history widens the range automatically (cold start, 4.6.2).
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np

from .calendar import tax_year_end, tax_year_start
from .models import Business

FORECAST_VERSION = "cashradar-v0"
WEEKS = 52


@dataclass
class ClientPattern:
    client: str
    delays: np.ndarray            # observed days-to-pay
    monthly_totals: np.ndarray    # invoiced per month since the client first appeared (zeros included)
    month_of_year: np.ndarray     # calendar month (1-12) of each monthly total
    this_month_so_far: float = 0.0

    def sample(self, rng, month: int, size: int) -> np.ndarray:
        same = self.monthly_totals[self.month_of_year == month]
        pool = same if len(same) >= 2 else self.monthly_totals
        return rng.choice(pool, size=size)

    @property
    def median_delay(self) -> float:
        return float(np.median(self.delays)) if len(self.delays) else 30.0


@dataclass
class Simulation:
    as_of: date
    n: int
    weeks: list[date]                     # week-ending dates
    receipts: np.ndarray                  # (n, WEEKS) business receipts per week
    expenses: np.ndarray                  # (n, WEEKS) allowable costs per week
    drawings: np.ndarray                  # (WEEKS,) known personal transfers
    ytd_profit: float                     # current tax year, to the as-of date
    year_end_profit: np.ndarray           # (n,) current tax year
    profit_to_week: np.ndarray            # (n, WEEKS) cumulative current-year profit at each week end
    next_year_profit_to_week: np.ndarray  # (n, WEEKS) profit after 5 April within the horizon
    outstanding_arrival: dict[str, np.ndarray]  # invoice id -> (n,) day offset when paid
    patterns: dict[str, ClientPattern]
    history_months: float
    version: str = FORECAST_VERSION


def learn_patterns(b: Business) -> dict[str, ClientPattern]:
    by_client = defaultdict(list)
    for inv in b.invoices:
        by_client[inv.client].append(inv)
    out = {}
    for client, invs in by_client.items():
        delays = np.array([(i.paid - i.issued).days for i in invs if i.paid], dtype=float)
        first = min(i.issued for i in invs)
        months, moy = [], []
        d = date(first.year, first.month, 1)
        current = date(b.as_of.year, b.as_of.month, 1)
        while d < current:
            nxt = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
            months.append(sum(i.amount for i in invs if d <= i.issued < nxt))
            moy.append(d.month)
            d = nxt
        so_far = sum(i.amount for i in invs if i.issued >= current)
        out[client] = ClientPattern(client, delays, np.array(months, dtype=float), np.array(moy), so_far)
    return out


def _monthly_expense_history(b: Business) -> np.ndarray:
    tot = defaultdict(float)
    for o in b.outflows:
        if o.kind == "expense":
            tot[(o.day.year, o.day.month)] += o.amount
    keys = sorted(tot)[:-1] or sorted(tot)
    return np.array([tot[k] for k in keys], dtype=float) if keys else np.array([0.0])


def simulate(b: Business, n: int = 2000, seed: int = 7) -> Simulation:
    rng = np.random.default_rng(seed)
    as_of = b.as_of
    ys, ye = tax_year_start(as_of), tax_year_end(as_of)
    weeks = [as_of + timedelta(days=7 * (k + 1)) for k in range(WEEKS)]
    horizon = WEEKS * 7
    patterns = learn_patterns(b)
    history_months = max(1.0, (as_of - b.trading_since).days / 30.44)

    # Level uncertainty: how much we don't know about the true run-rate. It grows with the
    # month-to-month variability of the business and shrinks with the length of history (cold start).
    all_months = [p.monthly_totals for p in patterns.values() if len(p.monthly_totals)]
    if all_months:
        L = min(len(m) for m in all_months)
        combined = np.sum([m[-L:] for m in all_months], axis=0)
        cv = float(combined.std() / combined.mean()) if combined.mean() > 0 else 0.5
    else:
        cv = 0.5
    level_sd = min(0.35, 2.0 * cv / np.sqrt(history_months) + 0.25 * np.exp(-history_months / 6.0))
    level = np.exp(rng.normal(0, level_sd, size=n))

    receipts = np.zeros((n, WEEKS))
    days_to_year_end = (ye - as_of).days
    year_receipts = np.zeros(n)
    next_receipts_by_day = []   # (offset array, amount array)
    outstanding_arrival = {}

    def add(offset: np.ndarray, amount):
        amount = np.broadcast_to(np.asarray(amount, dtype=float), offset.shape)
        idx = (offset - 1) // 7
        ok = (offset >= 1) & (idx < WEEKS)
        rows = np.nonzero(ok)[0]
        np.add.at(receipts, (rows, idx[ok].astype(int)), amount[ok])
        nonlocal year_receipts
        year_receipts = year_receipts + np.where(offset <= days_to_year_end, amount, 0.0)
        next_receipts_by_day.append((offset, amount))

    def draw_delay(p: ClientPattern, size: int, older_than: int = 0) -> np.ndarray:
        base = p.delays if len(p.delays) >= 3 else np.array([14.0, 30.0, 45.0, 60.0])
        d = rng.choice(base, size=size) + rng.normal(0, max(2.0, base.std() * 0.25), size=size)
        if older_than:
            late = d <= older_than
            # already older than this draw: it will arrive after a further short wait
            d[late] = older_than + rng.gamma(2.0, max(4.0, base.std()), size=late.sum())
        return np.maximum(1, np.round(d))

    # 1. Invoices already issued but unpaid.
    for inv in b.outstanding():
        p = patterns[inv.client]
        age = inv.age(as_of)
        total = draw_delay(p, n, older_than=age)
        offset = (total - age).astype(int)
        outstanding_arrival[inv.id] = offset
        add(offset, inv.amount)

    # 2. Work not yet invoiced: monthly totals resampled from each client's own history.
    month = date(as_of.year, as_of.month, 1)
    months_ahead = []
    while (month - as_of).days < horizon:
        months_ahead.append(month)
        month = date(month.year + (month.month == 12), month.month % 12 + 1, 1)
    for p in patterns.values():
        if not len(p.monthly_totals):
            continue
        for m in months_ahead:
            issue = max(as_of + timedelta(days=1), m + timedelta(days=14))
            amt = p.sample(rng, m.month, n) * level
            if (m.year, m.month) == (as_of.year, as_of.month):
                amt = np.maximum(0.0, amt - p.this_month_so_far)   # part of this month is already invoiced
            offset = (issue - as_of).days + draw_delay(p, n).astype(int)
            add(offset, amt)

    # 3. Allowable costs and personal drawings.
    exp_hist = _monthly_expense_history(b)
    expenses = np.zeros((n, WEEKS))
    for m in months_ahead:
        k = ((m + timedelta(days=14)) - as_of).days
        k = max(k, 1)
        if (k - 1) // 7 < WEEKS:
            expenses[:, (k - 1) // 7] += rng.choice(exp_hist, size=n) * np.sqrt(level)
    draw_hist = [o.amount for o in b.outflows if o.kind == "drawings"][-6:]
    drawings = np.zeros(WEEKS)
    if draw_hist:
        monthly = float(np.mean(draw_hist))
        for m in months_ahead:
            k = max(((m + timedelta(days=27)) - as_of).days, 1)
            if (k - 1) // 7 < WEEKS:
                drawings[(k - 1) // 7] += monthly

    # Profit on the cash basis for the current tax year.
    ytd_profit = sum(i.amount for i in b.receipts(ys, as_of)) - sum(o.amount for o in b.expenses(ys, as_of))
    week_end_offsets = np.array([7 * (k + 1) for k in range(WEEKS)])
    in_year_week = week_end_offsets <= days_to_year_end
    # weeks straddling 5 April are assigned by their end date (one-week rounding, acceptable for v0)
    cum_rec = np.cumsum(receipts, axis=1)
    cum_exp = np.cumsum(expenses, axis=1)
    last_in_year = int(in_year_week.sum())
    year_exp = cum_exp[:, last_in_year - 1] if last_in_year else np.zeros(n)
    year_end_profit = ytd_profit + year_receipts - year_exp
    profit_to_week = ytd_profit + np.where(in_year_week, cum_rec - cum_exp, year_receipts[:, None] - year_exp[:, None])
    next_to_week = np.where(in_year_week, 0.0, (cum_rec - cum_exp) - (year_receipts[:, None] - year_exp[:, None]))

    return Simulation(as_of, n, weeks, receipts, expenses, drawings, float(ytd_profit), year_end_profit,
                      profit_to_week, next_to_week, outstanding_arrival, patterns, history_months)
