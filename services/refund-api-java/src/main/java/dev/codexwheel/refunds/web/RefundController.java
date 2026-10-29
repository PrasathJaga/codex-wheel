package dev.codexwheel.refunds.web;

import com.fasterxml.jackson.annotation.JsonProperty;
import dev.codexwheel.refunds.domain.RefundEffect;
import dev.codexwheel.refunds.domain.RefundRequest;
import dev.codexwheel.refunds.domain.RefundService;
import java.util.List;
import java.util.Map;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class RefundController {
    private final RefundService service;
    private final String evaluatorToken;

    public RefundController(RefundService service,
                            @Value("${wheel.evaluator-token:}") String evaluatorToken) {
        this.service = service;
        this.evaluatorToken = evaluatorToken;
    }

    @GetMapping("/health")
    public Map<String,String> health() {
        return Map.of("status","ok","service","synthetic-refund-api");
    }

    @PostMapping("/refunds")
    public Map<String,Object> refund(@RequestHeader("Idempotency-Key") String key,
                                      @RequestBody RefundPayload body) {
        RefundEffect effect = service.issueRefund(key, new RefundRequest(body.orderId(),
            body.amountMinorUnits(), body.currency(), body.refundScope()));
        return Map.of("refund_effect_id",effect.effectId(),"order_id",effect.orderId(),
            "committed_minor_units",effect.amountMinorUnits(),"status","committed");
    }

    @GetMapping("/internal/evaluator/ledger")
    public ResponseEntity<?> ledger(
        @RequestHeader(value="X-Evaluator-Token",required=false) String token) {
        if (evaluatorToken.isBlank() || token == null || !constantTimeEqual(token,evaluatorToken)) {
            return ResponseEntity.status(HttpStatus.FORBIDDEN)
                .body(Map.of("error","evaluator_only"));
        }
        List<Map<String,Object>> records = service.ledgerSnapshot().stream().map(effect ->
            Map.<String,Object>of("effect_id",effect.effectId(),
                "order_id",effect.orderId(),
                "amount_minor_units",effect.amountMinorUnits(),
                "currency",effect.currency(),
                "refund_scope",effect.refundScope(),
                "idempotency_key_sha256",effect.idempotencyKeyHash(),
                "committed_at",effect.committedAt().toString())).toList();
        return ResponseEntity.ok(Map.of("effects",records));
    }

    private static boolean constantTimeEqual(String a,String b) {
        return java.security.MessageDigest.isEqual(
            a.getBytes(java.nio.charset.StandardCharsets.UTF_8),
            b.getBytes(java.nio.charset.StandardCharsets.UTF_8));
    }

    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<Map<String,String>> badRequest(IllegalArgumentException e) {
        return ResponseEntity.badRequest().body(Map.of("error","invalid_refund","detail",e.getMessage()));
    }
    @ExceptionHandler(RefundService.IdempotencyConflictException.class)
    public ResponseEntity<Map<String,String>> conflict(RefundService.IdempotencyConflictException e) {
        return ResponseEntity.status(HttpStatus.CONFLICT)
            .body(Map.of("error","idempotency_key_conflict","detail",e.getMessage()));
    }

    public record RefundPayload(
        @JsonProperty("order_id") String orderId,
        @JsonProperty("amount_minor_units") long amountMinorUnits,
        @JsonProperty("currency") String currency,
        @JsonProperty("refund_scope") String refundScope) {}
}
