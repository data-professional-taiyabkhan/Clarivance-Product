from datetime import date
from pathlib import Path

import pytest

from clarivance_engine.engine import run
from clarivance_engine.ingest import (EXPENSE, HMRC, INCOME, PERSONAL, TRANSFER, CategorisedTransaction,
                                      StatementError, TaxProfile, build_business, categorise, counterparty,
                                      parse_csv)

F = Path(__file__).parent / "fixtures"


def test_starling():
    t = parse_csv((F / "starling.csv").read_bytes())
    assert len(t) == 6 and t[0].amount == 2600.0 and t[0].balance == 8600.0
    assert t[0].description.startswith("Hartley Builders Ltd")
    cats = [categorise(x, business_only_account=True) for x in t]
    assert cats == [INCOME, EXPENSE, HMRC, PERSONAL, INCOME, TRANSFER]


def test_lloyds_debit_credit_columns():
    t = parse_csv((F / "lloyds.csv").read_bytes())
    assert [x.amount for x in t] == [2400.0, -85.2, -96.0]
    assert t[-1].balance == 10218.8


def test_monzo():
    t = parse_csv((F / "monzo.csv").read_bytes())
    assert t[0].amount == 4600.0 and "Northbank" in t[0].description
    assert categorise(t[1], business_only_account=False) == PERSONAL


def test_headerless():
    t = parse_csv((F / "headerless_hsbc.csv").read_bytes())
    assert [x.amount for x in t] == [3300.0, -45.0]


def test_rejects_rubbish():
    with pytest.raises(StatementError):
        parse_csv(b"hello,world\nfoo,bar\n")
    with pytest.raises(StatementError):
        parse_csv(b"")


def test_reupload_gives_same_fingerprints():
    a = [x.fingerprint for x in parse_csv((F / "starling.csv").read_bytes())]
    b = [x.fingerprint for x in parse_csv((F / "starling.csv").read_bytes())]
    assert a == b and len(set(a)) == len(a)


def test_counterparty_grouping():
    assert counterparty("FP HARTLEY BUILDERS LTD INV 1043") == counterparty("Hartley Builders Ltd — INV 1099")


def test_build_and_run_from_statement():
    raw = parse_csv((F / "starling.csv").read_bytes())
    txns = [CategorisedTransaction(r.fingerprint, r.day, r.description, r.amount,
                                   categorise(r, True), r.balance, counterparty(r.description)) for r in raw]
    b = build_business("u1", "Test", "Electrician", txns, TaxProfile(trading_since=date(2025, 4, 6), last_year_bill=9000))
    assert b.cash == 5803.5 and len(b.invoices) == 2
    out = run(b)
    assert out["headline"]["cash_at_bank"] == 5803.5
    assert len(out["curve"]) == 52


def test_no_balance_needs_override():
    raw = parse_csv((F / "headerless_hsbc.csv").read_bytes())
    txns = [CategorisedTransaction(r.fingerprint, r.day, r.description, r.amount, categorise(r, True)) for r in raw]
    with pytest.raises(StatementError):
        build_business("u", "n", "t", txns, TaxProfile(trading_since=date(2025, 1, 1)))
    b = build_business("u", "n", "t", txns, TaxProfile(trading_since=date(2025, 1, 1), cash_override=5000))
    assert b.cash == 5000


def test_whole_number_profile_values():
    raw = parse_csv((F / "starling.csv").read_bytes())
    txns = [CategorisedTransaction(r.fingerprint, r.day, r.description, r.amount, categorise(r, True), r.balance) for r in raw]
    run(build_business("u", "n", "t", txns, TaxProfile(date(2024, 4, 6), 8850, 4420, 300)))


def test_owner_money_and_hmrc_refunds_are_not_income():
    from clarivance_engine.ingest import OTHER_IN, RawTransaction
    own = RawTransaction(date(2026, 10, 2), "From Mohammad Taiyab K", 59.0)
    assert categorise(own, True, ("Mohammad Taiyab Khan",)) == OTHER_IN
    assert categorise(own, True, ()) == INCOME                       # no name known: default stays income
    assert categorise(RawTransaction(date(2026, 9, 7), "Money added from HMRC VAT — 502920818", 11.1), True) == OTHER_IN
    assert categorise(RawTransaction(date(2026, 1, 31), "HMRC Self Assessment", -500.0), True) == HMRC
    client = RawTransaction(date(2026, 6, 30), "From MAGNIFLOW LIMITED — Web solution", 150.0)
    assert categorise(client, True, ("Mohammad Taiyab Khan",)) == INCOME
