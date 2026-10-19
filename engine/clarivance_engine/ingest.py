"""Bank statement CSV -> categorised transactions -> Business (the engine's input).

Open Banking will later fill the same `RawTransaction` list, so everything downstream stays the same.
Supported out of the box: Monzo, Starling, Barclays, Lloyds/Halifax/Bank of Scotland, NatWest/RBS,
HSBC, Nationwide, Revolut, Tide, Santander-style exports, and any CSV with a date, a description and
either an amount column or separate money-in / money-out columns.
"""
from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime

from .models import Business, Invoice, Outflow

# ---------------------------------------------------------------- parsing

DATE_KEYS = ("transaction date", "date", "posted date", "booking date", "completed date", "started date", "value date")
DESC_KEYS = ("counter party", "counterparty", "name", "payee", "merchant", "transaction description", "description",
             "details", "transaction details", "narrative", "memo", "reference")
AMOUNT_KEYS = ("amount (gbp)", "amount", "value", "amount gbp", "transaction amount", "net amount")
IN_KEYS = ("paid in", "money in", "credit amount", "credit", "paid in (£)", "money in (£)", "in")
OUT_KEYS = ("paid out", "money out", "debit amount", "debit", "paid out (£)", "money out (£)", "out")
BAL_KEYS = ("balance (gbp)", "balance", "running balance", "balance (£)")
DATE_FORMATS = ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y", "%d %b %Y", "%d-%b-%Y", "%d %B %Y",
                "%Y/%m/%d", "%d.%m.%Y", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S")


class StatementError(ValueError):
    """A problem with the uploaded file, worded for the user."""


@dataclass
class RawTransaction:
    day: date
    description: str
    amount: float                 # + money in, - money out
    balance: float | None = None
    fingerprint: str = ""


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower().replace("﻿", ""))


def _money(s: str) -> float | None:
    if s is None:
        return None
    t = str(s).strip().replace("£", "").replace(",", "").replace("GBP", "").strip()
    if t in ("", "-"):
        return None
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()")
    if t.upper().endswith("CR"):
        t = t[:-2].strip()
    elif t.upper().endswith("DR"):
        t, neg = t[:-2].strip(), True
    try:
        v = float(t)
    except ValueError:
        return None
    return -v if neg else v


def _date(s: str) -> date | None:
    t = (s or "").strip()
    for f in DATE_FORMATS:
        try:
            return datetime.strptime(t, f).date()
        except ValueError:
            continue
    return None


def _pick(headers: list[str], keys: tuple[str, ...], loose: bool = True) -> int | None:
    normed = [_norm(h) for h in headers]
    for k in keys:
        if k in normed:
            return normed.index(k)
    if loose:
        for k in keys:                  # looser: header contains the key
            for i, h in enumerate(normed):
                if len(k) > 3 and k in h:
                    return i
    return None


def _all(headers: list[str], keys: tuple[str, ...]) -> list[int]:
    normed = [_norm(h) for h in headers]
    return [normed.index(k) for k in keys if k in normed]


def parse_csv(content: bytes | str) -> list[RawTransaction]:
    text = content.decode("utf-8-sig", errors="replace") if isinstance(content, bytes) else content
    if not text.strip():
        raise StatementError("The file is empty.")
    rows = [r for r in csv.reader(io.StringIO(text)) if any(c.strip() for c in r)]
    if len(rows) < 2:
        raise StatementError("The file needs at least one transaction.")

    # find the header row (some banks put account details above it)
    header_i = None
    for i, r in enumerate(rows[:15]):
        if _pick(r, DATE_KEYS) is not None and (_pick(r, AMOUNT_KEYS) is not None or _pick(r, IN_KEYS) is not None):
            header_i = i
            break
    if header_i is None:
        # headerless (e.g. HSBC): date, description, amount[, balance]
        if _date(rows[0][0]) and len(rows[0]) >= 3 and _money(rows[0][2]) is not None:
            hdr, body = ["date", "description", "amount", "balance"][: len(rows[0])], rows
        else:
            raise StatementError("We couldn't find the date and amount columns. Export the statement as CSV from "
                                 "your bank's online banking, or use the template on this page.")
    else:
        hdr, body = rows[header_i], rows[header_i + 1:]

    di = _pick(hdr, DATE_KEYS)
    ii, oi, bi = _pick(hdr, IN_KEYS, loose=False), _pick(hdr, OUT_KEYS, loose=False), _pick(hdr, BAL_KEYS)
    if ii is None or oi is None:
        ii, oi = _pick(hdr, IN_KEYS), _pick(hdr, OUT_KEYS)
    ai = _pick(hdr, AMOUNT_KEYS, loose=False)
    if ai is None and (ii is None or oi is None):
        ai = _pick(hdr, AMOUNT_KEYS)
    desc_cols = _all(hdr, DESC_KEYS) or ([1] if len(hdr) > 1 else [])
    extra_cols = _all(hdr, ("reference", "notes and #tags", "memo"))
    if di is None or (ai is None and (ii is None or oi is None)):
        raise StatementError("We couldn't find the date and amount columns in this file.")

    out: list[RawTransaction] = []
    bad = 0
    seen: dict[str, int] = {}
    for r in body:
        r = r + [""] * (len(hdr) - len(r))
        d = _date(r[di])
        if ai is not None:
            amt = _money(r[ai])
        else:
            cin, cout = _money(r[ii]) or 0.0, _money(r[oi]) or 0.0
            amt = abs(cin) - abs(cout) if (r[ii].strip() or r[oi].strip()) else None
        if d is None or amt is None:
            bad += 1
            continue
        desc = next((r[c].strip() for c in desc_cols if r[c].strip()), "")
        note = next((r[c].strip() for c in extra_cols if r[c].strip() and r[c].strip() != desc), "")
        if note and desc and note not in desc:
            desc = f"{desc} — {note}"
        desc = desc or note
        bal = _money(r[bi]) if bi is not None else None
        key = f"{d.isoformat()}|{amt:.2f}|{_norm(desc)}|{'' if bal is None else f'{bal:.2f}'}"
        seen[key] = seen.get(key, 0) + 1        # identical lines on the same day are kept, numbered
        fp = hashlib.sha256(f"{key}|{seen[key]}".encode()).hexdigest()[:32]
        out.append(RawTransaction(d, desc or "(no description)", round(amt, 2), bal, fp))
    if not out:
        raise StatementError("No transactions could be read from this file.")
    if bad > max(5, len(out)):
        raise StatementError("Most rows in this file couldn't be read. Check it's a CSV export of transactions.")
    return out


# ---------------------------------------------------------------- categorising

INCOME, OTHER_IN, EXPENSE, PERSONAL, HMRC, TRANSFER = "income", "other_in", "expense", "personal", "hmrc", "transfer"
CATEGORIES = {
    INCOME: "Business income (taxable)",
    OTHER_IN: "Money in that isn't income (refund, loan, own money)",
    EXPENSE: "Business expense (allowable)",
    PERSONAL: "Personal spending or drawings",
    HMRC: "Payment to HMRC (Self Assessment)",
    TRANSFER: "Transfer between my own accounts",
}

_HMRC = re.compile(r"\bhmrc\b|self ?assessment|inland revenue|hm revenue", re.I)
_TRANSFER = re.compile(r"\btransfer\b|\bto savings\b|\bfrom savings\b|\bpot\b|\bisa\b|own account|\btfr\b", re.I)
_REFUND = re.compile(r"refund|reversal|cashback|interest paid|loan|bounce back|chargeback", re.I)
_PERSONAL = re.compile(r"tesco|sainsbury|asda|aldi|lidl|morrisons|waitrose|netflix|spotify|deliveroo|uber ?eats|"
                       r"just eat|amazon prime|disney|cinema|pub\b|restaurant|nando|mcdonald|starbucks|costa|greggs|"
                       r"council tax|mortgage|rent\b|gym|cash withdrawal|atm|tv licen", re.I)


def categorise(t: RawTransaction, business_only_account: bool) -> str:
    d = t.description
    if _HMRC.search(d):
        return HMRC
    if _TRANSFER.search(d):
        return TRANSFER
    if t.amount > 0:
        return OTHER_IN if _REFUND.search(d) else INCOME
    if _PERSONAL.search(d):
        return PERSONAL
    return EXPENSE if business_only_account else PERSONAL


_NOISE = re.compile(r"\b(fp|bgc|bacs|faster payment|fpi|fpo|so|dd|ddr|pos|bp|cr|dr|ref|inv|invoice|payment|"
                    r"from|to|ltd\.?|limited)\b|[0-9]{3,}|[#*/\\-]", re.I)


def counterparty(description: str) -> str:
    """Group payments from the same client: 'FP HARTLEY BUILDERS LTD INV 1043' -> 'Hartley Builders'."""
    base = description.split(" — ")[0]
    words = _NOISE.sub(" ", base).split()
    name = " ".join(words[:3]).title()
    return name or "Unknown"


# ---------------------------------------------------------------- building the engine input

@dataclass
class TaxProfile:
    """The tax-profile questions (plan 4.1). Defaults are deliberately cautious."""
    trading_since: date
    last_year_bill: float = 0.0               # last Self Assessment bill (income tax + Class 4)
    paid_towards_this_year: float = 0.0       # payments on account already made for this tax year
    last_year_balance_owed: float = 0.0       # balancing payment for last year not yet paid
    cash_override: float | None = None        # current balance if the statement has no balance column


@dataclass
class CategorisedTransaction:
    id: str
    day: date
    description: str
    amount: float
    category: str
    balance: float | None = None
    client: str = ""


@dataclass
class OutstandingInvoice:
    id: str
    client: str
    issued: date
    amount: float


def build_business(key: str, name: str, trade: str, txns: list[CategorisedTransaction], profile: TaxProfile,
                   outstanding: list[OutstandingInvoice] = (), as_of: date | None = None) -> Business:
    if not txns:
        raise StatementError("Upload a bank statement first.")
    txns = sorted(txns, key=lambda t: (t.day, t.id))
    as_of = as_of or max(t.day for t in txns)
    invoices: list[Invoice] = []
    outflows: list[Outflow] = []
    for t in txns:
        if t.day > as_of:
            continue
        if t.category == INCOME and t.amount > 0:
            # A bank feed shows when money arrived, not when the invoice was raised: treat it as issued and paid that day.
            invoices.append(Invoice(t.id, t.client or counterparty(t.description), t.day, t.amount, t.day))
        elif t.category == EXPENSE:
            outflows.append(Outflow(t.day, abs(t.amount), "expense", t.description))
        elif t.category in (PERSONAL, TRANSFER) and t.amount < 0:
            # not deductible, but it does leave this account, so the cash forecast must include it
            outflows.append(Outflow(t.day, abs(t.amount), "drawings", t.description))
        elif t.category == HMRC and t.amount < 0:
            outflows.append(Outflow(t.day, abs(t.amount), "hmrc", t.description))
        elif t.category == INCOME and t.amount < 0:          # e.g. a client refund recorded against income
            outflows.append(Outflow(t.day, abs(t.amount), "expense", t.description))
    for o in outstanding:
        invoices.append(Invoice(f"open-{o.id}", o.client, o.issued, o.amount, None))

    with_bal = [t for t in txns if t.balance is not None and t.day <= as_of]
    if profile.cash_override is not None:
        cash = profile.cash_override
    elif with_bal:
        cash = with_bal[-1].balance
    else:
        raise StatementError("This statement has no balance column. Enter your current bank balance in your tax profile.")

    return Business(
        key=key, name=name, trade=trade, as_of=as_of, cash=round(float(cash), 2),
        invoices=invoices, outflows=outflows, trading_since=min(profile.trading_since, txns[0].day),
        prev_year_liability=profile.last_year_bill,
        prev_balancing_outstanding=profile.last_year_balance_owed,
        paid_towards_current_year=profile.paid_towards_this_year,
        notes=[f"Built from {len(txns)} bank transactions up to {as_of.isoformat()}."],
    )
