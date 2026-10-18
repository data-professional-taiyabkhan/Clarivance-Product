"""Load a versioned tax rule set. Rules are data, kept apart from the calculation."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

RULES_DIR = Path(__file__).parent / "rules"


@dataclass(frozen=True)
class Band:
    name: str
    up_to: float | None
    rate: float


@dataclass(frozen=True)
class RuleSet:
    id: str
    year_start: date
    year_end: date
    personal_allowance: float
    taper_threshold: float
    taper_rate: float
    bands: tuple[Band, ...]
    c4_lower: float
    c4_upper: float
    c4_main: float
    c4_upper_rate: float
    poa_share: float
    poa_minimum_bill: float
    signed_off_by: str | None


def _d(v) -> date:
    return v if isinstance(v, date) else date.fromisoformat(str(v))


def load_rules(name: str = "2026-27_EWNI") -> RuleSet:
    raw = yaml.safe_load((RULES_DIR / f"{name}.yaml").read_text(encoding="utf-8"))
    it, c4, poa = raw["income_tax"], raw["class4_ni"], raw["payments_on_account"]
    bands = tuple(Band(b["name"], b["up_to"], float(b["rate"])) for b in it["bands"])
    uppers = [b.up_to for b in bands]
    if any(u is None for u in uppers[:-1]) or uppers[-1] is not None:
        raise ValueError("only the last band may be open-ended")
    if any(a >= b for a, b in zip(uppers[:-2], uppers[1:-1])):
        raise ValueError("band limits must increase")
    return RuleSet(
        id=raw["id"],
        year_start=_d(raw["tax_year"]["start"]),
        year_end=_d(raw["tax_year"]["end"]),
        personal_allowance=float(it["personal_allowance"]),
        taper_threshold=float(it["taper_threshold"]),
        taper_rate=float(it["taper_rate"]),
        bands=bands,
        c4_lower=float(c4["lower_profits_limit"]),
        c4_upper=float(c4["upper_profits_limit"]),
        c4_main=float(c4["main_rate"]),
        c4_upper_rate=float(c4["upper_rate"]),
        poa_share=float(poa["share_each"]),
        poa_minimum_bill=float(poa["minimum_previous_bill"]),
        signed_off_by=raw.get("signed_off_by"),
    )
