"""Real Java HTTP service + Python checkout; enabled only with an explicit local JAR."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from checkout_agent.client import CheckoutClient, InventoryRejected
from checkout_agent.verifier import verify


@unittest.skipUnless(os.environ.get("WHEEL_INVENTORY_LIVE") == "1", "Requires built Java inventory JAR")
class LiveInventoryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.token = secrets.token_hex(32)
        self.root = Path(self.directory.name)
        self.log = (self.root / "java.log").open("w+")
        self.addCleanup(self.log.close)
        self.process = subprocess.Popen(["java", "-jar", os.environ["WHEEL_INVENTORY_JAR"],
                                         "--server.port=18081"], stdout=self.log, stderr=subprocess.STDOUT,
            env={**os.environ, "WHEEL_INVENTORY_STATE": str(self.root / "state.json"),
                 "WHEEL_INVENTORY_EVALUATOR_TOKEN": self.token})
        self.addCleanup(self.stop)
        self.url = "http://127.0.0.1:18081"
        for _ in range(300):
            if self.process.poll() is not None:
                self.fail("Java exited during startup; inspect workflow log artifact")
            try:
                with urlopen(self.url + "/health", timeout=1) as response:
                    if response.status == 200: break
            except OSError: pass
            time.sleep(0.1)  # Readiness only; never controls expiry/interleaving.
        else: self.fail("Java startup timeout")
        self.client = CheckoutClient(self.url)

    def stop(self):
        if self.process.poll() is None:
            self.process.terminate()
            try: self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill(); self.process.wait(timeout=5)
        output = os.environ.get("WHEEL_INVENTORY_OUTPUT")
        if output:
            destination = Path(output); destination.mkdir(parents=True, exist_ok=True)
            self.log.flush()
            (destination / (self._testMethodName + ".log")).write_text((self.root / "java.log").read_text())

    def evaluator(self, path, payload=None, token=None):
        request = Request(self.url + "/internal/evaluator/" + path,
                          data=json.dumps(payload).encode() if payload is not None else None,
                          headers={"Content-Type": "application/json", "X-Evaluator-Token": token or self.token})
        with urlopen(request, timeout=5) as response: return json.load(response)

    def assert_verified(self, receipts):
        snapshot = self.evaluator("state")
        # Cross-check the HTTP evaluator against the actual durable local state file.
        self.assertEqual(snapshot, json.loads((self.root / "state.json").read_text()))
        result = verify(snapshot, receipts)
        output = os.environ.get("WHEEL_INVENTORY_OUTPUT")
        if output:
            destination = Path(output); destination.mkdir(parents=True, exist_ok=True)
            (destination / (self._testMethodName + ".json")).write_text(json.dumps(
                {"execution_mode": "fresh_baseline_no_model", "snapshot": snapshot,
                 "accepted_orders": receipts, "verification": result}, indent=2))
        return result

    def test_successful_checkout_and_duplicate(self):
        self.client.reserve("rA", "A")
        order = self.client.checkout("rA", "A", "orderA")
        self.assertEqual(order, self.client.checkout("rA", "A", "orderA"))
        self.assertEqual(self.assert_verified([order, order])["committed_orders"], 1)

    def test_expiry_reallocation_rejects_old_checkout(self):
        self.client.reserve("rA", "A")
        self.evaluator("trigger-expiry", {"reservationId": "rA"})
        self.client.reserve("rB", "B")
        with self.assertRaises(InventoryRejected) as caught:
            self.client.checkout("rA", "A", "orderA")
        self.assertEqual((caught.exception.status, caught.exception.code), (409, "reservation_not_active"))
        order = self.client.checkout("rB", "B", "orderB")
        self.assertEqual(self.assert_verified([order])["committed_orders"], 1)

    def test_owner_mismatch_and_release(self):
        self.client.reserve("rA", "A")
        with self.assertRaises(InventoryRejected) as caught: self.client.checkout("rA", "B", "orderB")
        self.assertEqual(caught.exception.status, 403)
        self.client.release("rA", "A")
        self.client.reserve("rB", "B")
        order = self.client.checkout("rB", "B", "orderB")
        self.assertEqual(self.assert_verified([order])["committed_orders"], 1)

    def test_competing_public_requests_have_one_winner(self):
        def reserve(buyer):
            try: self.client.reserve("r" + buyer, buyer); return buyer
            except InventoryRejected as error:
                self.assertEqual((error.status, error.code), (409, "out_of_stock")); return None
        with ThreadPoolExecutor(max_workers=2) as pool: results = list(pool.map(reserve, ("A", "B")))
        winners = [buyer for buyer in results if buyer]
        self.assertEqual(len(winners), 1)
        buyer = winners[0]; order = self.client.checkout("r" + buyer, buyer, "order" + buyer)
        self.assertEqual(self.assert_verified([order])["committed_orders"], 1)

    def test_privileged_expiry_denied_without_correct_token(self):
        self.client.reserve("rA", "A")
        with self.assertRaises(HTTPError) as caught:
            self.evaluator("trigger-expiry", {"reservationId": "rA"}, token="incorrect")
        self.assertEqual(caught.exception.code, 403)
        snapshot = self.evaluator("state")
        self.assertEqual(snapshot["reservations"][0]["status"], "ACTIVE")
        self.assert_verified([])


if __name__ == "__main__": unittest.main()
