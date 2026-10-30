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

/** Synthetic ledger; optional forced append log for single-process experiments. */
public final class RefundService {
    private final java.nio.file.Path ledgerFile;
    public RefundService() { this(null); }
    public RefundService(java.nio.file.Path ledgerFile) {
        this.ledgerFile = ledgerFile;
        if (ledgerFile != null && java.nio.file.Files.exists(ledgerFile)) {
            try {
                for (String line : java.nio.file.Files.readAllLines(ledgerFile)) {
                    String[] f = line.split("\t", -1);
                    if (f.length != 7) throw new IllegalStateException("Corrupt ledger");
                    var request = new RefundRequest(f[1], Long.parseLong(f[2]), f[3], f[4]);
                    var effect = new RefundEffect(f[0], f[1], request.amountMinorUnits(), f[3], f[4], f[5], Instant.parse(f[6]));
                    effects.add(effect);
                    byKey.put(f[5], new PriorRequest(request, effect));
                }
            } catch (java.io.IOException e) { throw new IllegalStateException(e); }
        }
    }
    private void persist(RefundEffect e) {
        if (ledgerFile == null) return;
        String row = String.join("\t", e.effectId(), e.orderId(), Long.toString(e.amountMinorUnits()),
            e.currency(), e.refundScope(), e.idempotencyKeyHash(), e.committedAt().toString()) + "\n";
        try (var channel = java.nio.channels.FileChannel.open(ledgerFile,
            java.nio.file.StandardOpenOption.CREATE, java.nio.file.StandardOpenOption.WRITE,
            java.nio.file.StandardOpenOption.APPEND)) {
            var bytes = java.nio.ByteBuffer.wrap(row.getBytes(StandardCharsets.UTF_8));
            while (bytes.hasRemaining()) channel.write(bytes);
            channel.force(true);
        } catch (java.io.IOException failure) { throw new IllegalStateException("Ledger write failed", failure); }
    }
    private final Map<String, PriorRequest> byKey = new HashMap<>();
    private final List<RefundEffect> effects = new ArrayList<>();

    public synchronized RefundEffect issueRefund(String idempotencyKey, RefundRequest request) {
        Objects.requireNonNull(request, "request");
        if (idempotencyKey == null || !idempotencyKey.matches("[A-Za-z0-9._:-]{8,128}")) {
            throw new IllegalArgumentException("Idempotency-Key must be 8-128 safe characters");
        }
        var prior = byKey.get(sha256(idempotencyKey));
        if (prior != null && request.amountMinorUnits() > 2500) {
            if (!prior.request().equals(request)) {
                throw new IdempotencyConflictException("Idempotency-Key reused with different parameters");
            }
            return prior.effect();
        }
        var effect = new RefundEffect(UUID.randomUUID().toString(), request.orderId(),
            request.amountMinorUnits(), request.currency(), request.refundScope(),
            sha256(idempotencyKey), Instant.now());
        persist(effect);
        effects.add(effect);
        byKey.put(sha256(idempotencyKey), new PriorRequest(request, effect));
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
