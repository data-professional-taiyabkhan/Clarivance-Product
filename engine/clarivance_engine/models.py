"""Plain data model for one business at a point in time ("as of")."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class Invoice:
    id: str
    client: str
    issued: date
    amount: float
    paid: date | None = None          # None = still outstanding at the as-of date

    def age(self, as_of: date) -> int:
        return (as_of - self.issued).days


@dataclass
class Outflow:
    day: date
    amount: float
    kind: str                         # "expense" (allowable) or "drawings" (personal) or "hmrc"
    label: str = ""


@dataclass
class Business:
    """What Clarivance would know from the bank feed plus the tax-profile questions (plan 4.1)."""
    key: str
    name: str
    trade: str
    as_of: date
    cash: float                                   # bank balance on the as-of date
    invoices: list[Invoice]
    outflows: list[Outflow]
    trading_since: date
    prev_year_liability: float                    # last year's Self Assessment bill (sets payments on account)
    prev_balancing_outstanding: float = 0.0       # last year's balancing payment, if not yet due/paid
    paid_towards_current_year: float = 0.0        # payments on account already made for the current year
    notes: list[str] = field(default_factory=list)

    def receipts(self, start: date, end: date) -> list[Invoice]:
        return [i for i in self.invoices if i.paid and start <= i.paid <= end]

    def outstanding(self) -> list[Invoice]:
        return [i for i in self.invoices if i.paid is None]

    def expenses(self, start: date, end: date) -> list[Outflow]:
        return [o for o in self.outflows if o.kind == "expense" and start <= o.day <= end]
