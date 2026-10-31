"""Public inventory client: evaluator credentials and expiry are deliberately absent."""
import json
import re
from urllib.error import HTTPError
from urllib.request import Request, urlopen


class InventoryRejected(Exception):
    def __init__(self, status, code):
        self.status = status
        self.code = code
        super().__init__(f"Inventory rejected request: {status} {code}")


def identifier(value):
    if not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value) is None:
        raise ValueError("Invalid identifier")
    return value


class CheckoutClient:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip("/")

    def _post(self, path, payload):
        request = Request(self.base_url + path, data=json.dumps(payload).encode(),
                          headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urlopen(request, timeout=5) as response:
                return json.load(response)
        except HTTPError as error:
            # Do not turn transport failures or rejected confirmation into accepted checkout.
            try:
                body = json.load(error)
                code = body.get("error", "http_error")
            except (ValueError, AttributeError):
                code = "http_error"
            raise InventoryRejected(error.code, code) from None

    def reserve(self, reservation_id, buyer):
        return self._post("/reservations", {"reservationId": identifier(reservation_id),
                                           "buyer": identifier(buyer), "sku": "last-item"})

    def checkout(self, reservation_id, buyer, order_id):
        identifier(reservation_id); identifier(buyer); identifier(order_id)
        order = self._post(f"/reservations/{reservation_id}/confirm", {"buyer": buyer, "orderId": order_id})
        expected = {"id": order_id, "buyer": buyer, "reservationId": reservation_id, "sku": "last-item"}
        if order != expected:
            raise ValueError("Confirmation response does not match checkout intent")
        return order

    def release(self, reservation_id, buyer):
        return self._post(f"/reservations/{identifier(reservation_id)}/release", {"buyer": identifier(buyer)})
