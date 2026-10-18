"""TaxShield: Predictive Marginal Tax Attribution and the reserve (plan 4.6.2).

attribution(a)  = mean over simulations of [ liability(P_s) - liability(P_s - a) ]
reserve         = chosen percentile (default 80th) of liability(P_s)
reconciliation  = per-transaction figures scaled so they add up to the reserve held for
                  income already received (v0 rule: proportional; alternatives are R&D, plan 5.7.4)
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .rules import RuleSet
from .tax import liability


def attribute(amount: float, year_end_profit: np.ndarray, r: RuleSet) -> float:
    """Expected tax caused by including `amount` in a year whose outcome is uncertain."""
    p = np.asarray(year_end_profit, dtype=float)
    return float(np.mean(liability(p, r) - liability(p - amount, r)))


def attribute_many(amounts, year_end_profit: np.ndarray, r: RuleSet) -> np.ndarray:
    a = np.asarray(amounts, dtype=float)[:, None]
    p = np.asarray(year_end_profit, dtype=float)[None, :]
    return np.mean(liability(p, r) - liability(p - a, r), axis=1)


@dataclass
class TaxPosition:
    expected_liability: float
    reserve_liability: float          # the percentile of the liability distribution
    confidence: float
    liability_p10: float
    liability_p90: float
    single_forecast_liability: float  # what a one-number forecast would reserve (for comparison)
    tax_on_income_so_far: float       # reserve to hold now for income already received, before payments made
    paid_towards_year: float
    hold_now: float                   # what should be in the tax pot today for this year
    rate_on_next_1000: float
    p_over: dict[str, float]          # chance of finishing above key thresholds
    reconciled: list[dict]            # per received transaction


def tax_position(ytd_profit: float, year_end_profit: np.ndarray, r: RuleSet, receipts: list[tuple[str, str, float]],
                 paid_towards_year: float = 0.0, confidence: float = 0.8) -> TaxPosition:
    P = np.asarray(year_end_profit, dtype=float)
    L = liability(P, r)
    expected = float(L.mean())
    reserve = float(np.quantile(L, confidence))
    scale = reserve / expected if expected > 0 else 1.0
    so_far = max(0.0, attribute(max(ytd_profit, 0.0), P, r)) * scale

    amounts = [amt for _, _, amt in receipts]
    a = attribute_many(amounts, P, r) if amounts else np.zeros(0)
    total = float(a.sum())
    factor = so_far / total if total > 0 else 0.0
    rec = [{"id": i, "label": lab, "amount": round(amt, 2), "attributed": round(float(x), 2),
            "reconciled": round(float(x * factor), 2)} for (i, lab, amt), x in zip(receipts, a)]
    return TaxPosition(
        expected_liability=round(expected, 2), reserve_liability=round(reserve, 2), confidence=confidence,
        liability_p10=round(float(np.quantile(L, 0.1)), 2), liability_p90=round(float(np.quantile(L, 0.9)), 2),
        single_forecast_liability=round(float(liability(float(np.median(P)), r)), 2),
        tax_on_income_so_far=round(so_far, 2), paid_towards_year=round(paid_towards_year, 2),
        hold_now=round(max(0.0, so_far - paid_towards_year), 2),
        rate_on_next_1000=round(attribute(1000.0, P, r), 2),
        p_over={"50270": round(float((P > 50270).mean()), 3), "100000": round(float((P > 100000).mean()), 3),
                "125140": round(float((P > 125140).mean()), 3)},
        reconciled=rec,
    )
