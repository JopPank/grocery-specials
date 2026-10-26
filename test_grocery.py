from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
import unittest
from unittest.mock import patch

import requests

import grocery_tracker
import grocery_web


def flyer_item(**changes):
    now = datetime.now(timezone.utc)
    item = {
        "merchant_name": "IGA",
        "name": "Chicken breast 500 g",
        "current_price": 3.49,
        "pre_price_text": "Member price",
        "post_price_text": "/lb",
        "sale_story": "Limit 2",
        "valid_from": (now - timedelta(days=1)).isoformat(),
        "valid_to": (now + timedelta(days=1)).isoformat(),
        "flyer_id": 123,
    }
    item.update(changes)
    return item


class SearchTests(unittest.TestCase):
    def search(self, items):
        with patch("grocery_tracker.requests.get") as get:
            get.return_value.json.return_value = {"items": items}
            result = grocery_tracker.search_grocery_deals("chicken", "J9J 3X7")
            self.assertEqual(get.call_args.kwargs["params"]["postal_code"], "J9J 3X7")
            self.assertEqual(get.call_args.args[0], "https://backflipp.wishabi.com/flipp/items/search")
            get.return_value.raise_for_status.assert_called_once()
            return result

    def test_units_conditions_and_deduplication(self):
        item = flyer_item()
        deals = self.search([item, item.copy()])
        self.assertEqual(len(deals), 1)
        self.assertEqual(deals[0]["price_text"], "Member price $3.49 /lb")
        self.assertEqual(deals[0]["sale_story"], "Limit 2")
        self.assertEqual(deals[0]["flyer_url"], "https://flipp.com/en-ca/flyer/123")

    def test_future_expired_and_unpriced_items_excluded(self):
        now = datetime.now(timezone.utc)
        self.assertEqual(self.search([
            flyer_item(valid_to=(now - timedelta(days=1)).isoformat()),
            flyer_item(valid_from=(now + timedelta(days=1)).isoformat()),
            flyer_item(current_price=None),
            flyer_item(current_price=""),
        ]), [])

    def test_zero_price_and_missing_dates(self):
        deals = self.search([flyer_item(current_price=0, valid_from=None, valid_to=None)])
        self.assertEqual(deals[0]["price"], "0.00")
        self.assertIsNone(deals[0]["valid_to"])

    def test_only_allowed_stores_are_returned(self):
        deals = self.search([
            flyer_item(merchant_name="IGA Extra"),
            flyer_item(merchant_name="la boite a grains"),
            flyer_item(merchant_name="Food Basics"),
            flyer_item(merchant_name="Farm Boy"),
            flyer_item(merchant_name="Costco"),
        ])
        self.assertEqual(
            [deal["merchant"] for deal in deals],
            ["IGA Extra", "la boite a grains"],
        )
        self.assertEqual(
            [deal["store_category"] for deal in deals],
            ["IGA", "La Boite à Grains"],
        )

    def test_invalid_data_is_not_empty_success(self):
        for item in (flyer_item(current_price="NaN"), flyer_item(valid_to="bad-date")):
            with self.subTest(item=item), self.assertRaises(grocery_tracker.DealSearchError):
                self.search([item])
        with patch("grocery_tracker.requests.get") as get:
            get.return_value.json.return_value = {"something_else": []}
            with self.assertRaises(grocery_tracker.DealSearchError):
                grocery_tracker.search_grocery_deals("chicken")

    def test_network_http_and_json_errors(self):
        for failure in (requests.ConnectionError("DNS failed"),
                        requests.Timeout("Timed out"), requests.HTTPError("503")):
            with self.subTest(failure=failure), patch("grocery_tracker.requests.get", side_effect=failure):
                with self.assertRaises(grocery_tracker.DealSearchError):
                    grocery_tracker.search_grocery_deals("chicken")
        with patch("grocery_tracker.requests.get") as get:
            get.return_value.json.side_effect = ValueError("Not JSON")
            with self.assertRaises(grocery_tracker.DealSearchError):
                grocery_tracker.search_grocery_deals("chicken")

    def test_cli_does_not_claim_no_deals_on_failure(self):
        output = StringIO()
        with patch("grocery_tracker.search_grocery_deals", side_effect=grocery_tracker.DealSearchError("Offline")):
            with redirect_stdout(output):
                grocery_tracker.run_deal_checker()
        self.assertIn("Error checking", output.getvalue())
        self.assertNotIn("No active flyer deals found", output.getvalue())


class PageTests(unittest.TestCase):
    def setUp(self):
        grocery_web.app.testing = True
        self.client = grocery_web.app.test_client()

    def test_home_page_and_store_filter_options(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Stores to include", response.data)
        self.assertIn(b"Estimated total", response.data)
        self.assertIn(b"api-config.js", response.data)
        response.close()
        config_response = self.client.get("/api-config.js")
        self.assertEqual(config_response.status_code, 200)
        self.assertIn(b"application/javascript", config_response.content_type.encode())
        config_response.close()
        store_response = self.client.get("/api/stores")
        self.assertEqual(store_response.json["stores"], list(grocery_tracker.ALLOWED_STORES))

    def test_invalid_search_does_not_call_flipp(self):
        invalid_payloads = (
            {"foods": "chicken", "postal": "bad"},
            {"foods": ",".join(str(i) for i in range(9)), "postal": "J9J 3X7"},
            {"foods": "  ", "postal": "J9J 3X7"},
            {"foods": "x" * 301, "postal": "J9J 3X7"},
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload), patch("grocery_web.search_grocery_deals") as search:
                response = self.client.post("/api/search", json=payload)
                self.assertEqual(response.status_code, 400)
                self.assertIn("error", response.json)
                search.assert_not_called()

    def test_search_returns_item_groups_and_store_categories(self):
        with patch("grocery_web.search_grocery_deals", return_value=[{
            "merchant": "IGA Extra",
            "store_category": "IGA",
            "title": "Chicken breast 500 g",
            "price": "3.49",
            "price_text": "$3.49 /lb",
            "sale_story": "Limit 2",
            "valid_from": datetime.now(timezone.utc),
            "valid_to": None,
            "flyer_url": "https://flipp.com/en-ca/flyer/123",
        }]) as search:
            response = self.client.post(
                "/api/search",
                json={"foods": "chicken, eggs, chicken", "postal": "J9J 3X7"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual([result["item"] for result in response.json["results"]], ["chicken", "eggs"])
        self.assertEqual(response.json["results"][0]["deals"][0]["store_category"], "IGA")
        self.assertIsInstance(response.json["results"][0]["deals"][0]["valid_from"], str)
        self.assertEqual(search.call_count, 2)

    def test_upstream_failure_is_reported_as_an_item_error(self):
        with patch("grocery_web.search_grocery_deals", side_effect=grocery_tracker.DealSearchError("Offline")):
            response = self.client.post("/api/search", json={"foods": "eggs"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["results"][0]["error"], "Offline")
        self.assertEqual(response.json["results"][0]["deals"], [])

    def test_cors_and_health_endpoints(self):
        health_response = self.client.get("/api/health")
        self.assertEqual(health_response.json, {"status": "ok"})
        cors_response = self.client.get("/api/stores", headers={"Origin": "https://example.github.io"})
        self.assertEqual(cors_response.headers["Access-Control-Allow-Origin"], "*")
        self.assertEqual(cors_response.headers["Cache-Control"], "no-store")
        preflight = self.client.options(
            "/api/search",
            headers={
                "Origin": "https://example.github.io",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        self.assertIn("POST", preflight.headers["Access-Control-Allow-Methods"])

    def test_page_has_price_selection_and_total_behavior(self):
        page = Path(grocery_web.PAGE).read_text(encoding="utf-8")
        self.assertIn("selectedDeals", page)
        self.assertIn("radio.checked", page)
        self.assertIn("updateEstimate", page)
        self.assertIn("store_category", page)


if __name__ == "__main__":
    unittest.main()
