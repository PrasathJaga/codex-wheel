import copy
import unittest
from checkout_agent.verifier import verify


def valid():
    order = {"id": "orderA", "buyer": "A", "reservationId": "rA", "sku": "last-item"}
    snapshot = {"schema": 1, "stock": 1, "sku": "last-item",
                "reservations": [{"id": "rA", "buyer": "A", "sku": "last-item", "status": "CONFIRMED"}],
                "orders": [order], "events": [
                    {"sequence": 1, "type": "RESERVED", "reservationId": "rA", "buyer": "A", "orderId": None},
                    {"sequence": 2, "type": "CONFIRMED", "reservationId": "rA", "buyer": "A", "orderId": "orderA"}]}
    return snapshot, order


class VerifierTests(unittest.TestCase):
    def test_valid_and_duplicate_receipts_count_one_order(self):
        snapshot, order = valid()
        self.assertEqual(verify(snapshot, [order, order])["accepted_unique_orders"], 1)

    def test_empty_is_valid_but_missing_evidence_is_not(self):
        snapshot = {"schema": 1, "stock": 1, "sku": "last-item", "reservations": [], "orders": [], "events": []}
        self.assertEqual(verify(snapshot, [])["committed_orders"], 0)
        del snapshot["events"]
        with self.assertRaises(ValueError): verify(snapshot, [])

    def test_accepted_order_without_allocation_rejected(self):
        snapshot, order = valid(); ghost = {**order, "id": "ghost"}
        with self.assertRaisesRegex(ValueError, "Accepted checkout"): verify(snapshot, [ghost])

    def test_confirm_after_expiry_rejected_even_if_final_counts_look_valid(self):
        snapshot, order = valid()
        snapshot["events"].insert(1, {"sequence": 2, "type": "EXPIRED", "reservationId": "rA", "buyer": "A", "orderId": None})
        snapshot["events"][-1]["sequence"] = 3
        with self.assertRaisesRegex(ValueError, "lifecycle"): verify(snapshot, [order])

    def test_double_allocation_rejected(self):
        snapshot, order = valid()
        snapshot["events"].append({"sequence": 3, "type": "RESERVED", "reservationId": "rB", "buyer": "B", "orderId": None})
        with self.assertRaisesRegex(ValueError, "Stock exceeded"): verify(snapshot, [order])

    def test_tampered_snapshot_or_receipt_rejected(self):
        snapshot, order = valid()
        cases = []
        altered = copy.deepcopy(snapshot); altered["orders"][0]["buyer"] = "B"; cases.append((altered, [order]))
        altered = copy.deepcopy(snapshot); altered["reservations"].append(altered["reservations"][0]); cases.append((altered, [order]))
        altered = copy.deepcopy(snapshot); altered["events"][0]["sequence"] = 7; cases.append((altered, [order]))
        cases.append((snapshot, [{**order, "buyer": "B"}]))
        for state, receipts in cases:
            with self.subTest(state=state, receipts=receipts):
                with self.assertRaises(ValueError): verify(state, receipts)


if __name__ == "__main__": unittest.main()
