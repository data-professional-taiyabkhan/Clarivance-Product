"""Vectorised liability for a whole forecast distribution in one pass (plan 4.6.2)."""
from __future__ import annotations

import numpy as np

from .rules import RuleSet


def income_tax(profit, r: RuleSet) -> np.ndarray:
    p = np.maximum(np.asarray(profit, dtype=float), 0.0)
    allowance = np.maximum(0.0, r.personal_allowance - r.taper_rate * np.maximum(0.0, p - r.taper_threshold))
    taxable = np.maximum(0.0, p - allowance)
    tax = np.zeros_like(taxable)
    lower = 0.0
    for band in r.bands:
        upper = np.inf if band.up_to is None else band.up_to
        tax += band.rate * np.clip(taxable - lower, 0.0, upper - lower)
        lower = upper
    return tax


def class4(profit, r: RuleSet) -> np.ndarray:
    p = np.asarray(profit, dtype=float)
    return (r.c4_main * np.clip(p - r.c4_lower, 0.0, r.c4_upper - r.c4_lower)
            + r.c4_upper_rate * np.maximum(0.0, p - r.c4_upper))


def liability(profit, r: RuleSet) -> np.ndarray:
    """Income tax + Class 4 NI on trading profit. Accepts a scalar or an array of simulated year-ends."""
    return income_tax(profit, r) + class4(profit, r)


def marginal_rate(profit: float, r: RuleSet, step: float = 1.0) -> float:
    return float((liability(profit + step, r) - liability(profit, r)) / step)
