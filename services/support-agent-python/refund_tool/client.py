"""Synthetic refund tool wrapper. Not a Meta-powered agent."""

from __future__ import annotations
import uuid
from typing import Any
import httpx

class RefundToolError(RuntimeError):
    pass

class RefundTool:
    def __init__(self, base_url: str = "http://127.0.0.1:8080", *,
                 client: httpx.Client | None = None):
        self._owned_client = client is None
        self.client = client or httpx.Client(base_url=base_url, timeout=3.0, trust_env=False)

    def close(self) -> None:
        if self._owned_client:
            self.client.close()

    def issue_refund(self, *, order_id: str, amount_minor_units: int,
                     currency: str = "USD", refund_scope: str = "full_order",
                     max_attempts: int = 2) -> dict[str, Any]:
        if not 1 <= max_attempts <= 3:
            raise ValueError("max_attempts must be between 1 and 3")
        if not isinstance(amount_minor_units,int) or isinstance(amount_minor_units,bool):
            raise ValueError("amount_minor_units must be an integer")
        payload = dict(order_id=order_id, amount_minor_units=amount_minor_units,
                       currency=currency,refund_scope=refund_scope)
        key = str(uuid.uuid4())
        last_exception: Exception | None = None
        for attempt in range(1,max_attempts+1):
            try:
                response = self.client.post("/refunds",headers={"Idempotency-Key":key},json=payload)
            except httpx.TransportError as exc:
                last_exception=exc
                if attempt<max_attempts:
                    continue
                raise RefundToolError(f"Transport failed after {attempt} attempts") from exc
            if response.status_code==502:
                if attempt<max_attempts:
                    continue
                raise RefundToolError(f"HTTP 502 after {attempt} attempts")
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise RefundToolError(f"Refund API rejected operation: HTTP {response.status_code}") from exc
            try:
                body=response.json()
            except ValueError as exc:
                raise RefundToolError("Refund API returned invalid JSON") from exc
            if not isinstance(body,dict) or body.get("status")!="committed":
                raise RefundToolError("Refund API did not confirm committed synthetic effect")
            return body
        raise RefundToolError("Refund operation exhausted retries") from last_exception
