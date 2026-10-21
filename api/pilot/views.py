"""The signed-in person's own data: profile, statements, transactions, unpaid invoices and their position."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from decimal import Decimal, InvalidOperation
from functools import wraps

from django.conf import settings
from django.contrib.auth import logout
from django.db import IntegrityError, transaction as db_transaction
from django.db.models import Count, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods

from clarivance_engine.attribution import attribute
from clarivance_engine.engine import run
from clarivance_engine.forecast import simulate
from clarivance_engine.ingest import (CATEGORIES, CategorisedTransaction, OutstandingInvoice, StatementError,
                                      TaxProfile, build_business, categorise, counterparty, parse_csv)
from clarivance_engine.rules import load_rules

from .models import OpenInvoice, Profile, Statement, Transaction

RULES = load_rules()


def api_login_required(fn):
    @wraps(fn)
    def inner(request, *a, **k):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Please sign in."}, status=401)
        return fn(request, *a, **k)
    return inner


def _body(request) -> dict:
    try:
        return json.loads(request.body or b"{}")
    except ValueError:
        return {}


def _dec(v, default=None):
    if v in (None, ""):
        return default
    try:
        return Decimal(str(v)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        raise ValueError(f"'{v}' isn't a valid amount")


# ---------------------------------------------------------------- profile

def _profile_json(p: Profile) -> dict:
    return {"name": p.name, "business_name": p.business_name, "trade": p.trade, "business_type": p.business_type,
            "trading_since": p.trading_since.isoformat(), "last_year_bill": float(p.last_year_bill),
            "paid_towards_this_year": float(p.paid_towards_this_year),
            "last_year_balance_owed": float(p.last_year_balance_owed),
            "cash_override": None if p.cash_override is None else float(p.cash_override),
            "confidence": p.confidence, "profile_done": p.profile_done}


@api_login_required
@require_http_methods(["GET", "PUT"])
def profile(request):
    p, _ = Profile.objects.get_or_create(user=request.user)
    if request.method == "PUT":
        d = _body(request)
        try:
            for f in ("name", "business_name", "trade"):
                if f in d:
                    setattr(p, f, str(d[f] or "").strip()[:120])
            if d.get("business_type") in ("sole_trader", "limited_company", "partnership"):
                p.business_type = d["business_type"]
            if d.get("trading_since"):
                p.trading_since = date.fromisoformat(d["trading_since"])
            for f in ("last_year_bill", "paid_towards_this_year", "last_year_balance_owed"):
                if f in d:
                    v = _dec(d[f], Decimal("0"))
                    if v < 0:
                        raise ValueError("Amounts can't be negative.")
                    setattr(p, f, v)
            if "cash_override" in d:
                p.cash_override = _dec(d["cash_override"], None)
            if "confidence" in d:
                c = float(d["confidence"])
                if not 0.5 <= c <= 0.95:
                    raise ValueError("Confidence must be between 50% and 95%.")
                p.confidence = c
        except ValueError as e:
            return JsonResponse({"error": str(e)}, status=400)
        p.profile_done = True
        p.save()
    return JsonResponse(_profile_json(p))


# ---------------------------------------------------------------- statements

SAMPLE = Path(__file__).parent / "sample" / "sample-statement-starling.csv"


@api_login_required
@require_http_methods(["POST"])
def load_sample(request):
    """One click: an invented electrician's 18-month statement plus a matching tax profile, so anyone can see the
    whole flow without uploading their own bank data. Delete it from the Upload page like any statement."""
    p, _ = Profile.objects.get_or_create(user=request.user)
    if not p.profile_done:
        p.business_name, p.trade, p.business_type = "Sample Electrical (demo data)", "Electrician", "sole_trader"
        p.trading_since, p.last_year_bill, p.paid_towards_this_year = date(2024, 4, 6), Decimal("8850"), Decimal("4420")
        p.profile_done = True
        p.save()
    resp = _import(request, SAMPLE.read_bytes(), "Sample statement (invented data).csv", True)
    if resp.status_code == 201 and not request.user.open_invoices.filter(client="Kemp Construction").exists():
        OpenInvoice.objects.create(user=request.user, client="Kemp Construction", reference="INV 2291 (sample)",
                                   issued=date(2026, 9, 4), amount=Decimal("2450.00"))
    return resp


@api_login_required
@require_http_methods(["GET", "POST"])
def statements(request):
    if request.method == "GET":
        return JsonResponse({"statements": [
            {"id": s.id, "filename": s.filename, "rows": s.rows, "imported": s.imported, "duplicates": s.duplicates,
             "first_day": s.first_day and s.first_day.isoformat(), "last_day": s.last_day and s.last_day.isoformat(),
             "business_only": s.business_only, "uploaded_at": s.uploaded_at.isoformat()}
            for s in request.user.statements.all()]})
    f = request.FILES.get("file")
    if not f:
        return JsonResponse({"error": "Choose a CSV file to upload."}, status=400)
    if f.size > settings.MAX_STATEMENT_BYTES:
        return JsonResponse({"error": "That file is over 5 MB. Export a shorter date range."}, status=400)
    if not f.name.lower().endswith((".csv", ".txt")):
        return JsonResponse({"error": "Upload a CSV file. Most banks offer 'Export as CSV' in online banking."}, status=400)
    return _import(request, f.read(), f.name, request.POST.get("business_only", "true") == "true")


def _import(request, content: bytes, filename: str, business_only: bool):
    try:
        raw = parse_csv(content)
    except StatementError as e:
        return JsonResponse({"error": str(e)}, status=400)
    learned = _learned_rules(request.user)
    owners = _owner_names(request.user)
    with db_transaction.atomic():
        st = Statement.objects.create(user=request.user, filename=filename[:200], business_only=business_only,
                                      rows=len(raw), first_day=min(r.day for r in raw), last_day=max(r.day for r in raw))
        existing = set(request.user.transactions.filter(fingerprint__in=[r.fingerprint for r in raw])
                       .values_list("fingerprint", flat=True))
        new = []
        for r in raw:
            if r.fingerprint in existing:
                continue
            client = counterparty(r.description)
            cat = learned.get((client, r.amount > 0)) or categorise(r, business_only, owners)
            new.append(Transaction(user=request.user, statement=st, fingerprint=r.fingerprint, day=r.day,
                                   description=r.description[:300], amount=Decimal(str(r.amount)),
                                   balance=None if r.balance is None else Decimal(str(r.balance)),
                                   category=cat, client=client[:120]))
        Transaction.objects.bulk_create(new)
        st.imported, st.duplicates = len(new), len(raw) - len(new)
        st.save()
    return JsonResponse({"id": st.id, "rows": st.rows, "imported": st.imported, "duplicates": st.duplicates,
                         "first_day": st.first_day.isoformat(), "last_day": st.last_day.isoformat()}, status=201)


def _owner_names(user) -> tuple[str, ...]:
    p = Profile.objects.filter(user=user).first()
    return tuple(n for n in (p and p.name, user.first_name, user.get_full_name()) if n)


@api_login_required
@require_http_methods(["POST"])
def recategorise(request):
    """Re-run the automatic categories on every transaction the person hasn't corrected by hand."""
    from clarivance_engine.ingest import RawTransaction
    owners = _owner_names(request.user)
    business_only = {s.id: s.business_only for s in request.user.statements.all()}
    changed = 0
    for t in request.user.transactions.filter(user_edited=False):
        r = RawTransaction(t.day, t.description, float(t.amount))
        cat = categorise(r, business_only.get(t.statement_id, True), owners)
        if cat != t.category:
            t.category = cat
            t.save(update_fields=["category"])
            changed += 1
    return JsonResponse({"changed": changed})


def _learned_rules(user) -> dict:
    """Categories the person has set by hand, reused for the same client and direction on later uploads."""
    rules = {}
    for client, amount, cat in user.transactions.filter(user_edited=True).values_list("client", "amount", "category"):
        rules[(client, amount > 0)] = cat
    return rules


@api_login_required
@require_http_methods(["DELETE"])
def statement_detail(request, sid: int):
    n, _ = Statement.objects.filter(user=request.user, id=sid).delete()
    return JsonResponse({"deleted": bool(n)}, status=200 if n else 404)


# ---------------------------------------------------------------- transactions

def _txn_json(t: Transaction) -> dict:
    return {"id": t.id, "day": t.day.isoformat(), "description": t.description, "amount": float(t.amount),
            "balance": None if t.balance is None else float(t.balance), "category": t.category,
            "client": t.client, "user_edited": t.user_edited}


@api_login_required
@require_http_methods(["GET"])
def transactions(request):
    qs = request.user.transactions.all()
    cat, q = request.GET.get("category"), (request.GET.get("q") or "").strip()
    if cat in CATEGORIES:
        qs = qs.filter(category=cat)
    if q:
        qs = qs.filter(Q(description__icontains=q) | Q(client__icontains=q))
    total = qs.count()
    page = max(1, int(request.GET.get("page", 1) or 1))
    size = 100
    items = [_txn_json(t) for t in qs[(page - 1) * size: page * size]]
    summary = {c: {"count": n or 0, "total": float(s or 0)} for c, n, s in
               request.user.transactions.values_list("category").annotate(n=Count("id"), s=Sum("amount"))
               .values_list("category", "n", "s")}
    return JsonResponse({"transactions": items, "total": total, "page": page, "pages": (total + size - 1) // size,
                         "categories": CATEGORIES, "summary": summary})


@api_login_required
@require_http_methods(["PATCH"])
def transaction_detail(request, tid: int):
    t = request.user.transactions.filter(id=tid).first()
    if not t:
        return JsonResponse({"error": "Not found"}, status=404)
    d = _body(request)
    cat = d.get("category")
    if cat not in CATEGORIES:
        return JsonResponse({"error": "Unknown category"}, status=400)
    updated = 1
    with db_transaction.atomic():
        t.category, t.user_edited = cat, True
        if d.get("client"):
            t.client = str(d["client"]).strip()[:120]
        t.save()
        if d.get("apply_to_similar"):
            same_dir = Q(amount__gt=0) if t.amount > 0 else Q(amount__lt=0)
            updated += request.user.transactions.filter(same_dir, client=t.client, user_edited=False) \
                .exclude(id=t.id).update(category=cat, user_edited=True)
    return JsonResponse({"updated": updated, "transaction": _txn_json(t)})


# ---------------------------------------------------------------- unpaid invoices

@api_login_required
@require_http_methods(["GET", "POST"])
def invoices(request):
    if request.method == "POST":
        d = _body(request)
        try:
            amount = _dec(d.get("amount"))
            if amount is None or amount <= 0:
                raise ValueError("Enter the invoice amount.")
            issued = date.fromisoformat(d.get("issued") or "")
            if issued > date.today():
                raise ValueError("The invoice date can't be in the future.")
            client = (d.get("client") or "").strip()[:120]
            if not client:
                raise ValueError("Enter who the invoice is to.")
        except ValueError as e:
            return JsonResponse({"error": str(e) if "Enter" in str(e) or "can't" in str(e) else "Check the date and amount."}, status=400)
        OpenInvoice.objects.create(user=request.user, client=client, reference=(d.get("reference") or "")[:60],
                                   issued=issued, amount=amount)
    return JsonResponse({"invoices": [{"id": i.id, "client": i.client, "reference": i.reference,
                                       "issued": i.issued.isoformat(), "amount": float(i.amount)}
                                      for i in request.user.open_invoices.all()]})


@api_login_required
@require_http_methods(["DELETE"])
def invoice_detail(request, iid: int):
    n, _ = OpenInvoice.objects.filter(user=request.user, id=iid).delete()
    return JsonResponse({"deleted": bool(n)}, status=200 if n else 404)


# ---------------------------------------------------------------- the position

def _business(user):
    p, _ = Profile.objects.get_or_create(user=user)
    txns = [CategorisedTransaction(str(t.id), t.day, t.description, float(t.amount), t.category,
                                   None if t.balance is None else float(t.balance), t.client)
            for t in user.transactions.all().order_by("day", "id")]
    outstanding = [OutstandingInvoice(str(i.id), i.client, i.issued, float(i.amount)) for i in user.open_invoices.all()]
    tp = TaxProfile(trading_since=p.trading_since, last_year_bill=float(p.last_year_bill),
                    paid_towards_this_year=float(p.paid_towards_this_year),
                    last_year_balance_owed=float(p.last_year_balance_owed),
                    cash_override=None if p.cash_override is None else float(p.cash_override))
    b = build_business(f"user-{user.id}", p.business_name or p.name or "My business", p.trade or "Sole trader",
                       txns, tp, outstanding)
    return b, p


@api_login_required
@require_http_methods(["GET"])
def position(request):
    try:
        b, p = _business(request.user)
    except StatementError as e:
        return JsonResponse({"error": str(e)}, status=400)
    if (b.as_of - b.trading_since).days < 28:
        return JsonResponse({"error": "We need at least a month of transactions to forecast."}, status=400)
    confidence = float(request.GET.get("confidence") or p.confidence)
    out = run(b, RULES, confidence=min(max(confidence, 0.5), 0.95))
    out["business"]["notes"] = b.notes
    from clarivance_engine.calendar import tax_year_start
    first = request.user.transactions.order_by("day").values_list("day", flat=True).first()
    ys = tax_year_start(b.as_of)
    warnings = []
    if p.business_type != "sole_trader":
        kind = "a limited company" if p.business_type == "limited_company" else "a partnership"
        warnings.append(f"Your profile says this is {kind}. Clarivance currently works out tax for sole traders only "
                        "(income tax and Class 4 NI). "
                        + ("A limited company pays corporation tax and you pay tax on salary and dividends, so these figures don't apply yet."
                           if p.business_type == "limited_company" else "Partnership profit shares aren't supported yet, so treat these figures as a rough guide."))
    if first and first > ys and b.trading_since < first:
        warnings.append(f"Your statements start on {first:%d %B %Y}, after this tax year began on {ys:%d %B %Y}. "
                        "Income before then isn't counted, so the tax figures will be too low. Upload statements from "
                        f"{ys:%d %B %Y} (ideally the last 12 to 24 months).")
    if (b.as_of - date.today()).days < -45:
        warnings.append(f"Your latest transaction is from {b.as_of:%d %B %Y}. Upload a recent statement to bring the figures up to date.")
    if not p.profile_done:
        warnings.append("Complete your tax profile (last year's bill and payments already made) so payments on account are right.")
    out["warnings"] = warnings
    out["meta"]["label"] = "Estimates from your bank statement. Not tax advice."
    return JsonResponse(out)


@api_login_required
@require_http_methods(["GET"])
def what_if(request):
    try:
        amount = float(request.GET.get("amount", "1000"))
        if not 0 < amount <= 250000:
            raise ValueError
        b, _ = _business(request.user)
    except ValueError:
        return JsonResponse({"error": "amount must be between 0 and 250,000"}, status=400)
    except StatementError as e:
        return JsonResponse({"error": str(e)}, status=400)
    P = simulate(b).year_end_profit + amount
    tax = attribute(amount, P, RULES)
    return JsonResponse({"amount": amount, "tax_on_it": round(tax, 2), "keep": round(amount - tax, 2),
                         "effective_rate": round(tax / amount, 4), "chance_over_50270_after": round(float((P > 50270).mean()), 3)})


# ---------------------------------------------------------------- your data rights

@api_login_required
@require_http_methods(["GET"])
def export(request):
    u = request.user
    data = {"account": {"email": u.email, "joined": u.date_joined.isoformat()},
            "profile": _profile_json(Profile.objects.get_or_create(user=u)[0]),
            "statements": [{"filename": s.filename, "uploaded_at": s.uploaded_at.isoformat(), "rows": s.rows}
                           for s in u.statements.all()],
            "transactions": [_txn_json(t) for t in u.transactions.all()],
            "unpaid_invoices": [{"client": i.client, "issued": i.issued.isoformat(), "amount": float(i.amount)}
                                for i in u.open_invoices.all()]}
    resp = HttpResponse(json.dumps(data, indent=2), content_type="application/json")
    resp["Content-Disposition"] = 'attachment; filename="clarivance-my-data.json"'
    return resp


@api_login_required
@require_http_methods(["DELETE"])
def delete_account(request):
    d = _body(request)
    if not request.user.check_password(d.get("password") or ""):
        return JsonResponse({"error": "Enter your password to confirm."}, status=400)
    user = request.user
    logout(request)
    user.delete()          # cascades to profile, statements, transactions and invoices
    return JsonResponse({"deleted": True})
