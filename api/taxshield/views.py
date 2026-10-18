"""JSON API over the TaxShield engine. Read-only; synthetic businesses until Open Banking is connected."""
from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache

from django.http import Http404, HttpResponseBadRequest, JsonResponse
from django.views.decorators.http import require_GET

from clarivance_engine import __version__
from clarivance_engine.attribution import attribute
from clarivance_engine.calendar import tax_year_start
from clarivance_engine.engine import run
from clarivance_engine.forecast import simulate
from clarivance_engine.rules import load_rules
from clarivance_engine.synthetic import PERSONAS, generate

RULES = load_rules()


def _params(request, key):
    if key not in PERSONAS:
        raise Http404("Unknown business")
    try:
        as_of = date.fromisoformat(request.GET["as_of"]) if request.GET.get("as_of") else PERSONAS[key].default_as_of
        confidence = float(request.GET.get("confidence", 0.8))
    except ValueError:
        return None
    if not (0.5 <= confidence <= 0.95) or as_of < PERSONAS[key].start + timedelta(days=28):
        return None
    return as_of, confidence


@lru_cache(maxsize=256)
def _run(key: str, as_of: date, confidence: float) -> dict:
    b = generate(key, as_of)
    return run(b, RULES, confidence=confidence, last_week=generate(key, as_of - timedelta(days=7)))


@require_GET
def health(request):
    return JsonResponse({"ok": True, "engine": __version__, "rules": RULES.id})


@require_GET
def businesses(request):
    return JsonResponse({"businesses": [
        {"key": p.key, "name": p.name, "trade": p.trade, "description": p.description,
         "default_as_of": p.default_as_of.isoformat(), "trading_since": p.start.isoformat()}
        for p in PERSONAS.values()]})


@require_GET
def position(request, key):
    parsed = _params(request, key)
    if parsed is None:
        return HttpResponseBadRequest("as_of must be YYYY-MM-DD after trading started; confidence 0.5 to 0.95")
    return JsonResponse(_run(key, *parsed))


@require_GET
def what_if(request, key):
    """'If I receive another £X this tax year, how much of it is tax?' (Plus plan what-if scenarios, 4.4)."""
    parsed = _params(request, key)
    if parsed is None:
        return HttpResponseBadRequest("bad parameters")
    try:
        amount = float(request.GET.get("amount", "1000"))
    except ValueError:
        return HttpResponseBadRequest("amount must be a number")
    if not (0 < amount <= 250000):
        return HttpResponseBadRequest("amount must be between 0 and 250,000")
    as_of, _ = parsed
    b = generate(key, as_of)
    sim = simulate(b)
    P = sim.year_end_profit + amount
    tax = attribute(amount, P, RULES)
    return JsonResponse({"amount": amount, "tax_on_it": round(tax, 2), "keep": round(amount - tax, 2),
                         "effective_rate": round(tax / amount, 4),
                         "chance_over_50270_after": round(float((P > 50270).mean()), 3),
                         "tax_year_starting": tax_year_start(as_of).isoformat()})
