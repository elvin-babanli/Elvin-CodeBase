"""
Flight flow tests: no DB storage, store/restore/send-email.
Tests:
1. Non-logged-in user: Send via Email -> redirect to login
2. Logged-in user: can receive flight by email
3. No flight records in DB
4. Email content validation (mock)
5. Flight search unchanged
"""
import json
from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.db import connection

User = get_user_model()


SAMPLE_FLIGHT = {
    "id": "test-123",
    "origin": "WAW",
    "destination": "BCN",
    "departure_iata": "WAW",
    "arrival_iata": "BCN",
    "depart_date": "2025-06-15",
    "departure_date": "2025-06-15",
    "return_date": "",
    "price": 89.99,
    "currency": "EUR",
    "price_display": "89.99 EUR",
    "duration_minutes": 150,
    "total_duration": "2h 30m",
    "stops": 0,
    "stop_label": "Direct",
    "airline": "LOT",
    "primary_airline": "LOT",
    "depart_time": "08:00",
    "departure_time": "08:00",
    "arrival_time": "10:30",
    "arrival_date": "",
    "route_display": "WAW → BCN",
    "flight_number": "LO 123",
    "segments": [{"carrier_code": "LO", "number": "123"}],
}


class FlightFlowTestCase(TestCase):
    def setUp(self):
        self.store_url = "/cheap-flight-finder/api/store-context/"
        self.restore_url = "/cheap-flight-finder/api/restore-context/"
        self.send_email_url = "/cheap-flight-finder/api/send-email/"

    def test_1_non_logged_in_send_email_returns_401(self):
        """TEST 1: Non-logged-in user sends to send-email -> 401 Login required."""
        resp = self.client.post(
            self.send_email_url,
            data=json.dumps({"flight": SAMPLE_FLIGHT}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 401)
        data = resp.json()
        self.assertIn("error", data)
        self.assertIn("Login required", data["error"])

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_2_logged_in_user_can_send_email(self):
        """TEST 2: Logged-in user can send flight to their email."""
        user = User.objects.create_user(
            username="testuser", email="test@example.com", password="pass123"
        )
        self.client.force_login(user)

        resp = self.client.post(
            self.send_email_url,
            data=json.dumps({"flight": SAMPLE_FLIGHT}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get("success"))
        self.assertIn("message", data)

        from django.core.mail import outbox

        flight_emails = [m for m in outbox if "Flight details" in (m.subject or "")]
        self.assertGreaterEqual(len(flight_emails), 1, "Flight email should be sent")
        msg = flight_emails[-1]
        self.assertEqual(msg.to, ["test@example.com"])
        body = msg.body
        self.assertIn("WAW", body)
        self.assertIn("BCN", body)
        self.assertIn("89.99", body)
        self.assertIn("LOT", body)
        self.assertIn("Direct", body)
        self.assertIn("2h 30m", body)
        self.assertIn("LO 123", body)

    def test_3_store_restore_no_db_flight_model(self):
        """TEST 3: Store/restore uses session only; no Flight model/save in DB."""
        # Store
        resp = self.client.post(
            self.store_url,
            data=json.dumps({"flight": SAMPLE_FLIGHT}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json().get("success"))

        # Verify no Flight table or flight-related table
        with connection.cursor() as c:
            c.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%flight%'"
            )
            flight_tables = [r[0] for r in c.fetchall()]
        self.assertEqual(flight_tables, [], "No flight-related tables should exist")

        # Restore
        resp = self.client.get(self.restore_url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get("success"))
        flight = data.get("flight")
        self.assertIsNotNone(flight)
        self.assertEqual(flight.get("origin"), "WAW")
        self.assertEqual(flight.get("destination"), "BCN")
        self.assertEqual(flight.get("price"), 89.99)

    def test_4_email_content_has_all_required_fields(self):
        """TEST 4: Email template receives all required fields (via _normalize)."""
        from main.flight_services import _normalize_flight_for_display

        minimal = {
            "origin": "IST",
            "destination": "JFK",
            "departure_date": "2025-07-01",
            "departure_time": "14:00",
            "price": 299,
            "currency": "USD",
            "primary_airline": "TK",
            "stops": 1,
            "duration_minutes": 720,
            "segments": [{"carrier_code": "TK", "number": "1"}],
        }
        n = _normalize_flight_for_display(minimal)
        self.assertIn("route_display", n)
        self.assertIn("price_display", n)
        self.assertIn("departure_date", n)
        self.assertIn("departure_time", n)
        self.assertIn("primary_airline", n)
        self.assertIn("stop_label", n)
        self.assertIn("total_duration", n)
        self.assertIn("flight_number", n)

    def test_5_cheap_flight_search_api_still_works(self):
        """TEST 5: Flight search API is reachable (will fail validation without real params)."""
        resp = self.client.get("/cheap-flight-finder/api/search/")
        # 400 = validation error (missing params), not 404/500
        self.assertIn(resp.status_code, (200, 400, 429))

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_6_csrf_send_email_not_403(self):
        """TEST 6 (CSRF): CFF page loads, then send-email POST must NOT return 403."""
        user = User.objects.create_user(username="csrftest", email="csrf@test.com", password="pass123")
        resp = self.client.get("/cheap-flight-finder/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("csrftoken", self.client.cookies)
        self.client.force_login(user)
        resp = self.client.post(
            self.send_email_url,
            data=json.dumps({"flight": SAMPLE_FLIGHT}),
            content_type="application/json",
        )
        self.assertNotEqual(resp.status_code, 403, "CSRF must not block send-email")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json().get("success"))

    def test_7_store_context_non_logged_in(self):
        """TEST 7: Non-logged-in store-context returns 200 (redirect happens client-side)."""
        resp = self.client.post(
            self.store_url,
            data=json.dumps({"flight": SAMPLE_FLIGHT}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json().get("success"))
