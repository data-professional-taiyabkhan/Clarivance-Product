import json
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

FIX = Path(__file__).resolve().parents[3] / "engine" / "tests" / "fixtures"
PW = "a-long-pass-phrase-77"


def make_csv(months=14):
    """A sole trader's statement: two clients, costs, drawings, an HMRC payment."""
    from datetime import date, timedelta
    rows = ["Date,Counter Party,Reference,Type,Amount (GBP),Balance (GBP)"]
    bal = 5000.0
    d0 = date(2025, 8, 1)
    for m in range(months):
        base = date(d0.year + (d0.month + m - 1) // 12, (d0.month + m - 1) % 12 + 1, 1)
        for day, who, ref, amt in ((3, "Hartley Builders Ltd", "INV", 2600), (12, "Mrs Patel", "Rewire", 1100 + 30 * m),
                                   (18, "Screwfix", "Card", -300), (27, "D Smith", "Transfer to personal", -2400)):
            bal += amt
            rows.append(f"{(base + timedelta(days=day - 1)):%d/%m/%Y},{who},{ref},FP,{amt:.2f},{bal:.2f}")
    bal -= 1800
    rows.append(f"31/01/2026,HMRC Self Assessment,UTR,FP,-1800.00,{bal:.2f}")
    return "\n".join(rows).encode()


class PilotFlow(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.client.get("/api/auth/csrf")

    def post(self, url, data):
        return self.client.post(url, json.dumps(data), content_type="application/json")

    def register(self, email="pilot@example.com", **extra):
        return self.post("/api/auth/register", {"email": email, "password": PW, "name": "Pat", "accept_terms": True, **extra})

    def test_register_login_logout(self):
        r = self.register()
        self.assertEqual(r.status_code, 201)
        self.assertTrue(self.client.get("/api/auth/me").json()["authenticated"])
        self.post("/api/auth/logout", {})
        self.assertFalse(self.client.get("/api/auth/me").json()["authenticated"])
        self.assertEqual(self.post("/api/auth/login", {"email": "pilot@example.com", "password": "wrong-password-1"}).status_code, 400)
        self.assertEqual(self.post("/api/auth/login", {"email": "PILOT@example.com", "password": PW}).status_code, 200)

    def test_register_rules(self):
        self.assertEqual(self.post("/api/auth/register", {"email": "x@y.com", "password": "short", "accept_terms": True}).status_code, 400)
        self.assertEqual(self.post("/api/auth/register", {"email": "x@y.com", "password": PW}).status_code, 400)
        self.register()
        self.assertEqual(self.register().status_code, 400)

    @override_settings(PILOT_INVITE_CODE="PILOT27")
    def test_invite_code(self):
        self.assertEqual(self.register().status_code, 400)
        self.assertEqual(self.register(invite_code="PILOT27").status_code, 201)

    @override_settings(PILOT_REGISTRATION_REQUIRES_CODE=True, PILOT_INVITE_CODE="")
    def test_registration_closed_in_production_without_code(self):
        self.assertEqual(self.register().status_code, 403)

    def test_requires_login(self):
        for url in ("/api/me/profile", "/api/me/transactions", "/api/me/position"):
            self.assertEqual(self.client.get(url).status_code, 401)

    def test_upload_categorise_and_position(self):
        self.register()
        r = self.client.post("/api/me/statements", {"file": SimpleUploadedFile("s.csv", make_csv()), "business_only": "true"})
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["imported"], 57)
        again = self.client.post("/api/me/statements", {"file": SimpleUploadedFile("s.csv", make_csv()), "business_only": "true"}).json()
        self.assertEqual((again["imported"], again["duplicates"]), (0, 57))

        tx = self.client.get("/api/me/transactions").json()
        cats = {c: v["count"] for c, v in tx["summary"].items()}
        self.assertEqual(cats["income"], 28)
        self.assertEqual(cats["hmrc"], 1)
        self.assertEqual(cats["transfer"], 14)

        # the transfers are really drawings to a personal account: correct one, apply to all similar
        t = self.client.get("/api/me/transactions?category=transfer").json()["transactions"][0]
        r = self.client.patch(f"/api/me/transactions/{t['id']}", json.dumps({"category": "personal", "apply_to_similar": True}),
                              content_type="application/json")
        self.assertEqual(r.json()["updated"], 14)

        self.client.put("/api/me/profile", json.dumps({"last_year_bill": 9000, "trading_since": "2024-04-06",
                                                       "business_name": "Pat Electrical", "trade": "Electrician"}),
                        content_type="application/json")
        self.post("/api/me/invoices", {"client": "Hartley Builders Ltd", "issued": "2026-09-20", "amount": 2600})
        p = self.client.get("/api/me/position").json()
        self.assertIn("safe_to_spend_today", p["headline"])
        self.assertEqual(len(p["curve"]), 52)
        self.assertEqual(p["business"]["name"], "Pat Electrical")
        self.assertTrue(any(i["client"] == "Hartley Builders Ltd" for i in p["cashradar"]["outstanding_invoices"]))
        h = p["headline"]
        self.assertAlmostEqual(h["safe_to_spend_today"], h["cash_at_bank"] - h["tax_pot_should_hold"], places=1)
        self.assertEqual(self.client.get("/api/me/what-if?amount=1000").status_code, 200)

    def test_owner_transfers_and_recategorise(self):
        self.register()                                     # name "Pat"; set a full name on the profile
        csv = b"Date,Description,Amount,Balance\n01/10/2026,From Pat Jones,500.00,500.00\n02/10/2026,Client Co INV 1,900.00,1400.00\n"
        self.client.post("/api/me/statements", {"file": SimpleUploadedFile("s.csv", csv)})
        cats = {t["description"]: t["category"] for t in self.client.get("/api/me/transactions").json()["transactions"]}
        self.assertEqual(cats["From Pat Jones"], "income")            # name not known yet
        self.client.put("/api/me/profile", json.dumps({"name": "Pat Jones"}), content_type="application/json")
        self.assertEqual(self.post("/api/me/transactions/recategorise", {}).json()["changed"], 1)
        cats = {t["description"]: t["category"] for t in self.client.get("/api/me/transactions").json()["transactions"]}
        self.assertEqual(cats["From Pat Jones"], "other_in")
        self.assertEqual(cats["Client Co INV 1"], "income")

    def test_bad_file(self):
        self.register()
        r = self.client.post("/api/me/statements", {"file": SimpleUploadedFile("s.csv", b"hello,world\nfoo,bar")})
        self.assertEqual(r.status_code, 400)
        self.assertIn("error", r.json())
        r = self.client.post("/api/me/statements", {"file": SimpleUploadedFile("s.pdf", b"%PDF")})
        self.assertEqual(r.status_code, 400)

    def test_users_cannot_see_each_other(self):
        self.register("a@example.com")
        self.client.post("/api/me/statements", {"file": SimpleUploadedFile("s.csv", (FIX / "starling.csv").read_bytes())})
        tid = self.client.get("/api/me/transactions").json()["transactions"][0]["id"]
        self.post("/api/auth/logout", {})
        self.register("b@example.com")
        self.assertEqual(self.client.get("/api/me/transactions").json()["total"], 0)
        r = self.client.patch(f"/api/me/transactions/{tid}", json.dumps({"category": "income"}), content_type="application/json")
        self.assertEqual(r.status_code, 404)

    def test_export_and_delete(self):
        self.register()
        self.client.post("/api/me/statements", {"file": SimpleUploadedFile("s.csv", (FIX / "starling.csv").read_bytes())})
        self.assertEqual(len(json.loads(self.client.get("/api/me/export").content)["transactions"]), 6)
        self.assertEqual(self.client.delete("/api/me/delete", json.dumps({"password": "nope"}), content_type="application/json").status_code, 400)
        self.assertEqual(self.client.delete("/api/me/delete", json.dumps({"password": PW}), content_type="application/json").status_code, 200)
        from pilot.models import Transaction
        self.assertEqual(Transaction.objects.count(), 0)
        self.assertEqual(self.post("/api/auth/login", {"email": "pilot@example.com", "password": PW}).status_code, 400)


class CsrfEnforced(TestCase):
    def test_post_without_csrf_token_is_rejected(self):
        from django.test import Client
        c = Client(enforce_csrf_checks=True)
        r = c.post("/api/auth/register", json.dumps({"email": "a@b.com"}), content_type="application/json")
        self.assertEqual(r.status_code, 403)
