from __future__ import annotations
import json
import httpx
import pytest
from refund_tool import RefundTool, RefundToolError

PAYLOAD={"order_id":"ORD-SYN-1001","amount_minor_units":2500,"currency":"USD","refund_scope":"full_order"}
RECEIPT={"status":"committed","refund_effect_id":"synthetic-1","order_id":"ORD-SYN-1001","committed_minor_units":2500}

def setup(handler):
    client=httpx.Client(base_url="http://127.0.0.1:8080",transport=httpx.MockTransport(handler))
    return RefundTool(client=client),client

def test_contract():
    seen=[]
    def handle(request):
        seen.append(request)
        assert request.url.path=="/refunds"
        assert request.headers["Idempotency-Key"]
        assert json.loads(request.content)==PAYLOAD
        return httpx.Response(200,json=RECEIPT)
    tool,client=setup(handle)
    try:
        assert tool.issue_refund(**PAYLOAD)==RECEIPT
        assert len(seen)==1
    finally: client.close()

def test_502_retries_stable_key():
    keys=[]
    def handle(request):
        keys.append(request.headers["Idempotency-Key"])
        return httpx.Response(502) if len(keys)==1 else httpx.Response(200,json=RECEIPT)
    tool,client=setup(handle)
    try:
        assert tool.issue_refund(**PAYLOAD)["status"]=="committed"
        assert len(keys)==2 and keys[0]==keys[1]
    finally: client.close()

def test_transport_retry_stable_key():
    keys=[]
    def handle(request):
        keys.append(request.headers["Idempotency-Key"])
        if len(keys)==1:
            raise httpx.ReadError("synthetic connection lost",request=request)
        return httpx.Response(200,json=RECEIPT)
    tool,client=setup(handle)
    try:
        assert tool.issue_refund(**PAYLOAD)["status"]=="committed"
        assert keys[0]==keys[1]
    finally: client.close()

def test_400_no_retry():
    seen=[]
    def handle(request):
        seen.append(request)
        return httpx.Response(400)
    tool,client=setup(handle)
    try:
        with pytest.raises(RefundToolError,match="HTTP 400"):
            tool.issue_refund(**PAYLOAD)
        assert len(seen)==1
    finally: client.close()

def test_bounded_retries():
    seen=[]
    def handle(request):
        seen.append(request)
        return httpx.Response(502)
    tool,client=setup(handle)
    try:
        with pytest.raises(RefundToolError,match="after 2 attempts"):
            tool.issue_refund(**PAYLOAD)
        assert len(seen)==2
    finally: client.close()

def test_invalid_attempt_count():
    tool,client=setup(lambda r:httpx.Response(200,json=RECEIPT))
    try:
        with pytest.raises(ValueError):
            tool.issue_refund(**PAYLOAD,max_attempts=99)
    finally: client.close()
