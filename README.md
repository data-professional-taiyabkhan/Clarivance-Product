# Clarivance — pilot app (v0.2)

A working prototype of the product described in the Clarivance AI business plan (sections 4.1–4.6):
one number, **safe to spend today**, a 52-week **cash-after-tax curve** with an uncertainty band,
and the three modules behind it — **CashRadar** (forecast), **TaxShield** (Predictive Marginal Tax
Attribution, reserve, payments on account) and **ActionFlow** (weekly actions from templates, no LLM).

Built by Autostrata for Clarivance AI Ltd, for handover to Clarivance's CTO.

> **Status:** prototype on **synthetic data**. No bank connection yet, no customer data, no accounts or
> login. Tax rules are the 2026–27 England, Wales and NI values for sole-trader trading profit, **awaiting
> sign-off by the CEO**. Figures are estimates, not tax advice.

## Pilot: how a user gets their figures

1. **Register** at `/register` (email + password; an invite code is required in production via `PILOT_INVITE_CODE`).
2. **Tax profile** (`/app/profile`): self-employed since, last year's Self Assessment bill, payments on account
   already made, any balance still owed, optional current balance, and how cautious the reserve should be.
3. **Upload** a bank statement CSV (`/app/upload`). `engine/clarivance_engine/ingest.py` reads Monzo, Starling,
   Lloyds/Halifax, Barclays, NatWest, HSBC, Nationwide, Revolut, Tide and generic formats; duplicates are skipped
   on re-upload. `docs/sample-statement-starling.csv` is an invented 18-month statement for testing.
4. **Review categories** (`/app/transactions`): income, money in that isn't income, business expense,
   personal/drawings, HMRC, own-account transfer. A correction can be applied to every payment from the same
   payee, and is remembered for later uploads.
5. **Unpaid invoices** (`/app/invoices`) so the forecast and "chase it" actions include money not yet received.
6. **Dashboard** (`/app`): safe to spend today, the 52-week curve, TaxShield, CashRadar and ActionFlow on their
   own data, with warnings when the statement doesn't cover the whole tax year.
7. **Data rights**: download all data as JSON; delete the account and everything with it.

`/demo` keeps the three invented businesses (optionally behind `DEMO_PASSWORD`).

## Adding Open Banking later

`ingest.RawTransaction` is the seam. An Open Banking provider (TrueLayer, Yapily or Plaid) returns
transactions that map one-to-one onto it (date, description, signed amount, running balance, a stable
transaction id as the fingerprint). The provider's consent flow replaces the upload page; categorising,
corrections, the engine and the dashboard stay the same. Clarivance would operate under the provider's
FCA permissions as its agent, so that registration has to be in place before any live bank is connected.

## Layout

```
engine/   Python computation service (the tax engine). numpy only; no web framework.
  clarivance_engine/
    rules/2026-27_EWNI.yaml   tax rules as data, versioned, signed off by the CEO
    rules.py                  load + validate a rule set
    tax.py                    vectorised income tax + Class 4 NI for a whole distribution
    forecast.py               CashRadar v0: Monte Carlo of the rest of the year (2,000 simulated years)
    attribution.py            TaxShield: PMTA, percentile reserve, reconciliation
    curve.py                  HMRC payment schedule (POA, balancing) + safe-to-spend curve
    actions.py                ActionFlow templates
    engine.py                 run(business) -> everything the home screen needs
    synthetic.py              seeded synthetic businesses based on plan 6.3 (Dan, Marek, Steady)
  scenarios/suite-v0.csv      worked tax scenarios (to be re-worked and signed off by the CEO)
  tests/                      golden numbers from plan 4.6.2, payments on account, speed, etc.
api/      Django: taxshield/ = engine API and demo; pilot/ = accounts, statements, transactions, invoices
web/      React + TypeScript home screen (Vite, Recharts)
```

## Run it

Needs Python 3.11+ and Node 20+.

```bash
# 1. engine + API
cd engine && pip install -r requirements.txt && python -m pytest -q   # 36 tests
cd ../api && pip install -r requirements.txt && python manage.py test taxshield
python manage.py runserver 127.0.0.1:8000

# 2. web (second terminal)
cd web && npm install && npm run dev        # http://localhost:5173 (proxies /api to :8000)
```

## Hosted demo (Render)

`render.yaml` is a Render Blueprint: one free web service (Frankfurt) builds the React app and runs
Django with gunicorn, serving both the API and the web app. Set `DEMO_PASSWORD` in Render; the browser
then asks for it (any username). `/api/health` stays open for Render's health check.

## API

| Endpoint | Returns |
|---|---|
| `GET /api/health` | engine and rule-set versions |
| `GET /api/businesses` | the demo businesses |
| `GET /api/businesses/<key>?as_of=YYYY-MM-DD&confidence=0.8` | headline, curve, CashRadar, TaxShield, ActionFlow, meta |
| `GET /api/businesses/<key>/what-if?amount=1000` | tax on an extra amount received this tax year |

## How the engine works (short version)

1. **Forecast** — learns each client's payment delays and monthly invoicing from the bank history,
   then simulates 2,000 versions of the rest of the year. A short or erratic history widens the range.
2. **Tax on the whole distribution** — the rule set is applied to every simulated year-end in one
   vectorised pass (~0.1 ms for 2,000 years; full run under 0.1 s).
3. **PMTA** — each receipt is charged the *expected* change in the year's bill across the simulations,
   so a £1,000 invoice costs 26% if the year ends below £50,270, 42% above, and a blend in between
   (plan 4.6.2: £316 at a 35% chance of crossing, £356 at 60% — both are tests).
4. **Reserve** — set at the chosen percentile (default 80th) of the bill distribution, reconciled back
   to individual receipts so the per-transaction figures add up to what should be in the tax pot.
5. **Curve** — cash at bank + forecast receipts − costs − drawings − HMRC payments (31 Jan / 31 Jul,
   payments on account at 50% of last year's bill, none below £1,000) − tax built up but not yet paid.
6. **ActionFlow** — templated messages: next HMRC payment, slow-paying invoices that push cash after
   tax below zero, a coming dip, and the real cost of the next £1,000 near a threshold.

## Known limits of v0 (next steps in the plan)

- **No Open Banking yet.** `Business` (engine/models.py) is the contract a bank feed must fill; the
  provider (TrueLayer / Plaid / Yapily) is chosen in M1.
- Sole-trader trading profit only, cash basis, England/Wales/NI. Not yet: property income and the April
  2027 property rates, PAYE alongside, HICBC, student loans, Scotland, VAT.
- Years before 2026–27 and the 2027–28 accrual reuse the 2026–27 thresholds (frozen) as a stand-in.
- Forecast v0 is deliberately simple (resampling + payment-delay draws); the statistician's model
  replaces it. No accuracy claims until the backtest benchmark (plan 4.9).
- Reconciliation rule is proportional (v0 default); alternatives are planned R&D.
- No auth, no database models, no multi-tenant storage yet; SQLite placeholder only.
