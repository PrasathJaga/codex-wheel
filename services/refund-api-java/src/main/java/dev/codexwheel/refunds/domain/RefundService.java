package dev.codexwheel.refunds.domain;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;

/** In-memory synthetic refund domain. Atomic same-key deduplication, not durable on restart. */
public final class RefundService {
    private final Map<String, PriorRequest> byKey = new HashMap<>();
    private final List<RefundEffect> effects = new ArrayList<>();

    public synchronized RefundEffect issueRefund(String idempotencyKey, RefundRequest request) {
        Objects.requireNonNull(request, "request");
        if (idempotencyKey == null || !idempotencyKey.matches("[A-Za-z0-9._:-]{8,128}")) {
            throw new IllegalArgumentException("Idempotency-Key must be 8-128 safe characters");
        }
        var prior = byKey.get(idempotencyKey);
        if (prior != null) {
            if (!prior.request().equals(request)) {
                throw new IdempotencyConflictException("Idempotency-Key reused with different parameters");
            }
            return prior.effect();
        }
        var effect = new RefundEffect(UUID.randomUUID().toString(), request.orderId(),
            request.amountMinorUnits(), request.currency(), request.refundScope(),
            sha256(idempotencyKey), Instant.now());
        effects.add(effect);
        byKey.put(idempotencyKey, new PriorRequest(request, effect));
        return effect;
    }

    public synchronized List<RefundEffect> ledgerSnapshot() { return List.copyOf(effects); }

    private static String sha256(String value) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8));
            return java.util.HexFormat.of().formatHex(digest);
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 missing", e);
        }
    }
    private record PriorRequest(RefundRequest request, RefundEffect effect) {}
    public static final class IdempotencyConflictException extends RuntimeException {
        public IdempotencyConflictException(String msg) { super(msg); }
    }
}
