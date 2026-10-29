package dev.codexwheel.refunds.domain;

import java.time.Instant;

/** In-memory synthetic ledger entry. */
public record RefundEffect(
    String effectId, String orderId, long amountMinorUnits, String currency,
    String refundScope, String idempotencyKeyHash, Instant committedAt) {}
