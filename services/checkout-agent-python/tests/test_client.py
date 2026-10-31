import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from io import BytesIO
from checkout_agent.client import CheckoutClient, InventoryRejected


class ClientTests(unittest.TestCase):
    def test_rejected_confirmation_is_not_accepted(self):
        error = HTTPError("http://localhost", 409, "Conflict", {}, BytesIO(b'{"error":"reservation_not_active"}'))
        with patch("checkout_agent.client.urlopen", side_effect=error):
            with self.assertRaises(InventoryRejected) as caught:
                CheckoutClient("http://localhost").checkout("rA", "A", "orderA")
        self.assertEqual((caught.exception.status, caught.exception.code), (409, "reservation_not_active"))

    def test_success_response_must_match_intent(self):
        client = CheckoutClient("http://localhost")
        with patch.object(client, "_post", return_value={"id": "other"}):
            with self.assertRaises(ValueError): client.checkout("rA", "A", "orderA")

    def test_transport_error_propagates_without_retry(self):
        client = CheckoutClient("http://localhost")
        with patch("checkout_agent.client.urlopen", side_effect=TimeoutError) as request:
            with self.assertRaises(TimeoutError): client.checkout("rA", "A", "orderA")
            self.assertEqual(request.call_count, 1)

    def test_invalid_path_identity_never_sends(self):
        with patch("checkout_agent.client.urlopen") as request:
            with self.assertRaises(ValueError): CheckoutClient("http://localhost").checkout("../rA", "A", "orderA")
            request.assert_not_called()


if __name__ == "__main__": unittest.main()
