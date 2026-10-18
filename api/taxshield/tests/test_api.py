from django.test import SimpleTestCase


class ApiTests(SimpleTestCase):
    def test_health(self):
        self.assertTrue(self.client.get("/api/health").json()["ok"])

    def test_list(self):
        keys = [b["key"] for b in self.client.get("/api/businesses").json()["businesses"]]
        self.assertEqual(keys, ["dan", "marek", "steady"])

    def test_position(self):
        d = self.client.get("/api/businesses/dan").json()
        self.assertIn("safe_to_spend_today", d["headline"])
        self.assertEqual(len(d["curve"]), 52)

    def test_as_of_and_confidence(self):
        d = self.client.get("/api/businesses/dan?as_of=2026-12-01&confidence=0.9").json()
        self.assertEqual(d["business"]["as_of"], "2026-12-01")
        self.assertEqual(d["taxshield"]["confidence"], 0.9)

    def test_what_if(self):
        d = self.client.get("/api/businesses/dan/what-if?amount=1000").json()
        self.assertTrue(260 <= d["tax_on_it"] <= 420)

    def test_errors(self):
        self.assertEqual(self.client.get("/api/businesses/nope").status_code, 404)
        self.assertEqual(self.client.get("/api/businesses/dan?as_of=bad").status_code, 400)
        self.assertEqual(self.client.get("/api/businesses/dan?confidence=2").status_code, 400)
        self.assertEqual(self.client.get("/api/businesses/dan/what-if?amount=-5").status_code, 400)
