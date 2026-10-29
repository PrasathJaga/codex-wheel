package dev.codexwheel.refunds.domain;

import java.util.Objects;

/** Synthetic data, never a payment-provider request. */
public record RefundRequest(String orderId, long amountMinorUnits, String currency, String refundScope) {
    public RefundRequest {
        Objects.requireNonNull(orderId, "orderId");
        Objects.requireNonNull(currency, "currency");
        Objects.requireNonNull(refundScope, "refundScope");
        if (!orderId.matches("ORD-SYN-[A-Za-z0-9-]{1,64}")) {
            throw new IllegalArgumentException("Only synthetic ORD-SYN-* orders are supported");
        }
        if (amountMinorUnits <= 0 || amountMinorUnits > 100_000_000L) {
            throw new IllegalArgumentException("amount_minor_units must be between 1 and 100000000");
        }
        if (!currency.equals("USD")) {
            throw new IllegalArgumentException("Only synthetic USD fixtures are supported");
        }
        if (!refundScope.equals("full_order")) {
            throw new IllegalArgumentException("G1 supports only full_order");
        }
    }
}
