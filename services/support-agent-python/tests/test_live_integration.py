"""Opt-in live HTTP test; requires the Java server and a secret evaluator token."""
from __future__ import annotations
import os
import uuid
import httpx
import pytest
from refund_tool import RefundTool

@pytest.mark.skipif(os.getenv("WHEEL_TEST_LIVE")!="1" or not os.getenv("WHEEL_EVALUATOR_TOKEN"),
                    reason="requires explicitly running local Java API and private evaluator token")
def test_java_http_python_wrapper_one_effect():
    base=os.getenv("WHEEL_TEST_API_URL","http://127.0.0.1:8080")
    token=os.environ["WHEEL_EVALUATOR_TOKEN"]
    with httpx.Client(base_url=base,timeout=3,trust_env=False) as client:
        assert client.get("/health").status_code==200
        assert client.get("/internal/evaluator/ledger").status_code==403
        headers={"X-Evaluator-Token":token}
        before=client.get("/internal/evaluator/ledger",headers=headers)
        before.raise_for_status()
        before_ids={row["effect_id"] for row in before.json()["effects"]}
        order="ORD-SYN-"+uuid.uuid4().hex[:12]
        receipt=RefundTool(client=client).issue_refund(order_id=order,amount_minor_units=2500)
        after=client.get("/internal/evaluator/ledger",headers=headers)
        after.raise_for_status()
        new=[row for row in after.json()["effects"] if row["effect_id"] not in before_ids]
        assert receipt["status"]=="committed"
        assert len(new)==1 and new[0]["order_id"]==order
        assert new[0]["amount_minor_units"]==2500
        assert new[0]["refund_scope"]=="full_order"
        assert new[0]["currency"]=="USD"
        assert sum(row["amount_minor_units"] for row in new)==2500
        assert new[0]["effect_id"]==receipt["refund_effect_id"]
        assert client.get("/internal/evaluator/ledger",headers={"X-Evaluator-Token":"wrong"}).status_code==403
