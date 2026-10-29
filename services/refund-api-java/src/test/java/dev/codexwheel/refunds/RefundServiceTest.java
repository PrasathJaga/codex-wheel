package dev.codexwheel.refunds;

import dev.codexwheel.refunds.domain.RefundRequest;
import dev.codexwheel.refunds.domain.RefundService;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class RefundServiceTest {
    private static final RefundRequest REQUEST = new RefundRequest(
        "ORD-SYN-1001", 2500, "USD", "full_order");

    @Test void sameKeyDeduplicates() {
        var service = new RefundService();
        var first = service.issueRefund("synthetic-key-0001",REQUEST);
        var retry = service.issueRefund("synthetic-key-0001",REQUEST);
        assertEquals(first.effectId(),retry.effectId());
        assertEquals(1,service.ledgerSnapshot().size());
    }
    @Test void changedPayloadConflicts() {
        var service = new RefundService();
        service.issueRefund("synthetic-key-0001",REQUEST);
        assertThrows(RefundService.IdempotencyConflictException.class,
            () -> service.issueRefund("synthetic-key-0001",
                new RefundRequest("ORD-SYN-1001",7500,"USD","full_order")));
        assertEquals(1,service.ledgerSnapshot().size());
    }
    @Test void newKeyCausesNewEffect() {
        var service = new RefundService();
        service.issueRefund("synthetic-key-0001",REQUEST);
        service.issueRefund("synthetic-key-0002",REQUEST);
        assertEquals(2,service.ledgerSnapshot().size());
    }
    @Test void rejectsRealOrders() {
        assertThrows(IllegalArgumentException.class,
            () -> new RefundRequest("REAL-ORDER",2500,"USD","full_order"));
    }
}
