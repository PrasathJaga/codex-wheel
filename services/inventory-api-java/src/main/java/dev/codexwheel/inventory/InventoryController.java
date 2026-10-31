package dev.codexwheel.inventory;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Map;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
public final class InventoryController {
    public record ReserveRequest(String reservationId, String buyer, String sku) {}
    public record ConfirmRequest(String buyer, String orderId) {}
    public record BuyerRequest(String buyer) {}
    public record ExpiryRequest(String reservationId) {}
    private final InventoryStore store;
    private final byte[] evaluatorToken;

    public InventoryController(InventoryStore store, @Value("${inventory.evaluator-token:}") String token) {
        this.store = store; this.evaluatorToken = token.getBytes(StandardCharsets.UTF_8);
    }
    @GetMapping("/health") public Map<String, String> health() { return Map.of("status", "ok"); }
    @PostMapping("/reservations")
    public InventoryStore.Reservation reserve(@RequestBody ReserveRequest request) throws IOException {
        return store.reserve(request.reservationId(), request.buyer(), request.sku());
    }
    @PostMapping("/reservations/{id}/confirm")
    public InventoryStore.Order confirm(@PathVariable String id, @RequestBody ConfirmRequest request) throws IOException {
        return store.confirm(id, request.buyer(), request.orderId());
    }
    @PostMapping("/reservations/{id}/release")
    public InventoryStore.Reservation release(@PathVariable String id, @RequestBody BuyerRequest request) throws IOException {
        return store.release(id, request.buyer());
    }
    @PostMapping("/internal/evaluator/trigger-expiry")
    public InventoryStore.Reservation expire(@RequestHeader(value="X-Evaluator-Token", required=false) String token,
                                             @RequestBody ExpiryRequest request) throws IOException {
        authorize(token); return store.expire(request.reservationId());
    }
    @GetMapping("/internal/evaluator/state")
    public InventoryStore.Snapshot state(@RequestHeader(value="X-Evaluator-Token", required=false) String token) {
        authorize(token); return store.snapshot();
    }
    private void authorize(String token) {
        if (evaluatorToken.length<32 || token==null || !MessageDigest.isEqual(evaluatorToken, token.getBytes(StandardCharsets.UTF_8)))
            throw new InventoryStore.Rejected(403, "evaluator_access_denied");
    }
    @ExceptionHandler(InventoryStore.Rejected.class)
    public ResponseEntity<Map<String, String>> rejected(InventoryStore.Rejected error) {
        return ResponseEntity.status(error.status()).body(Map.of("error", error.getMessage()));
    }
    @ExceptionHandler(IOException.class)
    public ResponseEntity<Map<String, String>> storageFailure() {
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(Map.of("error", "storage_failure"));
    }
}
