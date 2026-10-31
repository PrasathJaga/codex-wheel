"""Host-side contract checks. Not used by the service to decide acceptance.

Checks a captured durable state and public accepted-order receipts independently.
Invalid/incomplete evidence raises; it is never represented as a passing world.
"""


def verify(snapshot, accepted_orders):
    def require(condition, message):
        if not condition:
            raise ValueError(message)

    require(isinstance(snapshot, dict), "Missing snapshot")
    require(type(snapshot.get("schema")) is int and snapshot["schema"] == 1 and type(snapshot.get("stock")) is int
            and snapshot["stock"] == 1 and snapshot.get("sku") == "last-item", "Wrong fixture identity")
    for key in ("reservations", "orders", "events"):
        require(isinstance(snapshot.get(key), list), "Incomplete snapshot")
    require(isinstance(accepted_orders, list), "Missing accepted-order receipts")
    lifecycle = {}
    event_orders = {}
    for sequence, event in enumerate(snapshot["events"], 1):
        require(isinstance(event, dict) and type(event.get("sequence")) is int and event["sequence"] == sequence, "Invalid event sequence")
        reservation_id, buyer = event.get("reservationId"), event.get("buyer")
        require(isinstance(reservation_id, str) and isinstance(buyer, str), "Missing event identity")
        kind = event.get("type")
        if kind == "RESERVED":
            require(reservation_id not in lifecycle and event.get("orderId") is None, "Invalid reserve event")
            lifecycle[reservation_id] = {"id": reservation_id, "buyer": buyer, "sku": "last-item", "status": "ACTIVE"}
        else:
            require(reservation_id in lifecycle, "Transition without reservation")
            reservation = lifecycle[reservation_id]
            require(reservation["buyer"] == buyer and reservation["status"] == "ACTIVE", "Invalid lifecycle transition")
            require(kind in ("EXPIRED", "RELEASED", "CONFIRMED"), "Unknown event")
            reservation["status"] = kind
            if kind == "CONFIRMED":
                order_id = event.get("orderId")
                require(isinstance(order_id, str) and order_id not in event_orders, "Invalid order identity")
                event_orders[order_id] = {"id": order_id, "buyer": buyer, "reservationId": reservation_id, "sku": "last-item"}
            else:
                require(event.get("orderId") is None, "Order attached to non-confirmation")
        require(sum(r["status"] in ("ACTIVE", "CONFIRMED") for r in lifecycle.values()) <= snapshot["stock"],
                "Stock exceeded during event history")
        require(len(event_orders) <= snapshot["stock"], "Confirmed orders exceed stock")
    require(len(snapshot["reservations"]) == len(lifecycle), "Reservation inventory mismatch")
    for reservation in snapshot["reservations"]:
        require(isinstance(reservation, dict) and lifecycle.get(reservation.get("id")) == reservation,
                "Reservation does not match event history")
    require(len({r["id"] for r in snapshot["reservations"]}) == len(lifecycle), "Duplicate reservation")
    require(len(snapshot["orders"]) == len(event_orders), "Order inventory mismatch")
    seen = set()
    for order in snapshot["orders"]:
        require(isinstance(order, dict) and event_orders.get(order.get("id")) == order, "Order lacks confirmed allocation")
        require(order["id"] not in seen, "Duplicate order"); seen.add(order["id"])
    accepted = {}
    for order in accepted_orders:
        require(isinstance(order, dict) and event_orders.get(order.get("id")) == order, "Accepted checkout lacks confirmed allocation")
        require(order["id"] not in accepted or accepted[order["id"]] == order, "Conflicting accepted receipt")
        accepted[order["id"]] = order
    return {"status": "verified", "stock": snapshot["stock"], "committed_orders": len(event_orders),
            "accepted_unique_orders": len(accepted), "events": len(snapshot["events"])}
