import dev.codexwheel.refunds.domain.RefundRequest;
import dev.codexwheel.refunds.domain.RefundService;

public final class DomainSmoke {
    public static void main(String[] args) {
        var service = new RefundService();
        var request = new RefundRequest("ORD-SYN-1001",2500,"USD","full_order");
        var first = service.issueRefund("idempotency-abc-0001",request);
        var retry = service.issueRefund("idempotency-abc-0001",request);
        if (!first.effectId().equals(retry.effectId())) throw new AssertionError("Duplicate from same key");
        if (service.ledgerSnapshot().size()!=1) throw new AssertionError("Ledger must have one effect");
        boolean conflict=false;
        try {
            service.issueRefund("idempotency-abc-0001",
                new RefundRequest("ORD-SYN-1001",7500,"USD","full_order"));
        } catch (RefundService.IdempotencyConflictException expected) { conflict=true; }
        if (!conflict) throw new AssertionError("Changed payload must conflict");
        service.issueRefund("idempotency-abc-0002",request);
        if (service.ledgerSnapshot().size()!=2) throw new AssertionError("Separate key must create new effect");
        System.out.println("PASS: idempotency and conflict");
    }
}
