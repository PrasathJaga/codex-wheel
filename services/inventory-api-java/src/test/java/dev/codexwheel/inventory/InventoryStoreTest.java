package dev.codexwheel.inventory;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Executors;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;

class InventoryStoreTest {
    @TempDir Path directory;
    private InventoryStore open() throws IOException { return new InventoryStore(directory.resolve("state.json"), new ObjectMapper()); }
    private void rejected(int status, String reason, org.junit.jupiter.api.function.Executable operation) {
        var error = assertThrows(InventoryStore.Rejected.class, operation);
        assertEquals(status, error.status()); assertEquals(reason, error.getMessage());
    }
    @Test void reserveAndConfirmConservesStock() throws Exception {
        try (var store = open()) {
            store.reserve("rA", "A", InventoryStore.SKU);
            var order = store.confirm("rA", "A", "orderA");
            assertEquals("rA", order.reservationId());
            assertEquals(InventoryStore.Status.CONFIRMED, store.snapshot().reservations().getFirst().status());
            rejected(409, "out_of_stock", () -> store.reserve("rB", "B", InventoryStore.SKU));
            assertEquals(1, store.snapshot().orders().size());
        }
    }
    @Test void duplicateReserveAndConfirmHaveNoExtraEffects() throws Exception {
        try (var store = open()) {
            var reservation = store.reserve("rA", "A", InventoryStore.SKU);
            assertEquals(reservation, store.reserve("rA", "A", InventoryStore.SKU));
            var order = store.confirm("rA", "A", "orderA");
            assertEquals(order, store.confirm("rA", "A", "orderA"));
            assertEquals(2, store.snapshot().events().size());
            rejected(409, "reservation_not_active", () -> store.confirm("rA", "A", "differentOrder"));
        }
    }
    @Test void expiredBuyerCannotConfirmAfterReallocation() throws Exception {
        try (var store = open()) {
            store.reserve("rA", "A", InventoryStore.SKU); store.expire("rA");
            store.reserve("rB", "B", InventoryStore.SKU);
            var before = store.snapshot();
            rejected(409, "reservation_not_active", () -> store.confirm("rA", "A", "orderA"));
            assertEquals(before, store.snapshot());
            store.confirm("rB", "B", "orderB");
            assertEquals(List.of("orderB"), store.snapshot().orders().stream().map(InventoryStore.Order::id).toList());
            assertEquals(List.of("RESERVED", "EXPIRED", "RESERVED", "CONFIRMED"),
                    store.snapshot().events().stream().map(InventoryStore.Event::type).toList());
        }
    }
    @Test void reserveDoesNotResurrectExpiredId() throws Exception {
        try (var store = open()) {
            store.reserve("rA", "A", InventoryStore.SKU); store.expire("rA");
            assertEquals(InventoryStore.Status.EXPIRED, store.reserve("rA", "A", InventoryStore.SKU).status());
            assertEquals(2, store.snapshot().events().size());
        }
    }
    @Test void releaseFreesStockAndIsIdempotent() throws Exception {
        try (var store = open()) {
            store.reserve("rA", "A", InventoryStore.SKU);
            var release = store.release("rA", "A");
            assertEquals(release, store.release("rA", "A"));
            rejected(409, "reservation_not_active", () -> store.confirm("rA", "A", "orderA"));
            store.reserve("rB", "B", InventoryStore.SKU); store.confirm("rB", "B", "orderB");
        }
    }
    @Test void ownersCannotBeMixed() throws Exception {
        try (var store = open()) {
            store.reserve("rA", "A", InventoryStore.SKU); var before = store.snapshot();
            rejected(403, "wrong_owner", () -> store.reserve("rA", "B", InventoryStore.SKU));
            rejected(403, "wrong_owner", () -> store.confirm("rA", "B", "orderB"));
            rejected(403, "wrong_owner", () -> store.release("rA", "B"));
            assertEquals(before, store.snapshot());
        }
    }
    @Test void confirmedAllocationCannotBeExpiredOrReleased() throws Exception {
        try (var store = open()) {
            store.reserve("rA", "A", InventoryStore.SKU); store.confirm("rA", "A", "orderA");
            rejected(409, "reservation_not_active", () -> store.expire("rA"));
            rejected(409, "reservation_not_active", () -> store.release("rA", "A"));
        }
    }
    @Test void expiryIsIdempotentButCannotExpireReleasedReservation() throws Exception {
        try (var store = open()) {
            store.reserve("rA", "A", InventoryStore.SKU); var expired = store.expire("rA");
            assertEquals(expired, store.expire("rA"));
            store.reserve("rB", "B", InventoryStore.SKU); store.release("rB", "B");
            rejected(409, "reservation_not_active", () -> store.expire("rB"));
        }
    }
    @Test void unknownAndMalformedRequestsHaveNoEffects() throws Exception {
        try (var store = open()) {
            rejected(404, "unknown_reservation", () -> store.expire("missing"));
            rejected(404, "unknown_reservation", () -> store.confirm("missing", "A", "orderA"));
            rejected(400, "invalid_identifier", () -> store.reserve("../r", "A", InventoryStore.SKU));
            rejected(400, "invalid_identifier", () -> store.reserve("r", null, InventoryStore.SKU));
            rejected(400, "unsupported_sku", () -> store.reserve("r", "A", "other"));
            assertEquals(0, store.snapshot().events().size());
        }
    }
    @Test void stateAndIdempotencySurviveGracefulRestart() throws Exception {
        InventoryStore.Snapshot expected;
        try (var store = open()) {
            store.reserve("rA", "A", InventoryStore.SKU); store.expire("rA");
            store.reserve("rB", "B", InventoryStore.SKU); store.confirm("rB", "B", "orderB");
            expected = store.snapshot();
        }
        try (var store = open()) {
            assertEquals(expected, store.snapshot()); store.confirm("rB", "B", "orderB");
            rejected(409, "reservation_not_active", () -> store.confirm("rA", "A", "orderA"));
            assertEquals(expected, store.snapshot());
        }
    }
    @Test void competingReservationsHaveExactlyOneWinner() throws Exception {
        try (var store = open(); var pool = Executors.newFixedThreadPool(2)) {
            var start = new CountDownLatch(1);
            var futures = List.of("A", "B").stream().map(buyer -> pool.submit(() -> {
                start.await();
                try { store.reserve("r"+buyer, buyer, InventoryStore.SKU); return true; }
                catch (InventoryStore.Rejected error) { assertEquals("out_of_stock", error.getMessage()); return false; }
            })).toList();
            start.countDown(); int winners = 0;
            for (var future : futures) if (future.get()) winners++;
            assertEquals(1, winners); assertEquals(1, store.snapshot().reservations().size());
        }
    }
    @Test void competingConfirmationsCannotCreateTwoOrders() throws Exception {
        try (var store = open(); var pool = Executors.newFixedThreadPool(2)) {
            store.reserve("rA", "A", InventoryStore.SKU); var start = new CountDownLatch(1);
            var futures = List.of("order1", "order2").stream().map(order -> pool.submit(() -> {
                start.await();
                try { store.confirm("rA", "A", order); return true; }
                catch (InventoryStore.Rejected error) { assertEquals("reservation_not_active", error.getMessage()); return false; }
            })).toList();
            start.countDown(); int winners = 0;
            for (var future : futures) if (future.get()) winners++;
            assertEquals(1, winners); assertEquals(1, store.snapshot().orders().size());
        }
    }
    @Test void corruptStateFailsClosed() throws Exception {
        try (var ignored = open()) { }
        Files.writeString(directory.resolve("state.json"), "{broken");
        assertThrows(IOException.class, this::open);
    }
    @Test void invalidConservationFailsClosedOnRestart() throws Exception {
        var invalid = new InventoryStore.Snapshot(1, 1, InventoryStore.SKU,
                List.of(new InventoryStore.Reservation("rA", "A", InventoryStore.SKU, InventoryStore.Status.ACTIVE),
                        new InventoryStore.Reservation("rB", "B", InventoryStore.SKU, InventoryStore.Status.ACTIVE)), List.of(), List.of());
        new ObjectMapper().writeValue(directory.resolve("state.json").toFile(), invalid);
        assertThrows(IOException.class, this::open);
    }
    @Test void anotherWriterCannotOpenSameState() throws Exception {
        try (var ignored = open()) { assertThrows(Exception.class, this::open); }
        try (var store = open()) { assertEquals(0, store.snapshot().orders().size()); }
    }
}
