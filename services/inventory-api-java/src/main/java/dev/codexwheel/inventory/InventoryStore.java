package dev.codexwheel.inventory;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.channels.FileLock;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/** Single-process synthetic inventory. Commit the snapshot before returning success. */
public final class InventoryStore implements AutoCloseable {
    public static final String SKU = "last-item";
    public enum Status { ACTIVE, EXPIRED, RELEASED, CONFIRMED }
    public record Reservation(String id, String buyer, String sku, Status status) {}
    public record Order(String id, String buyer, String reservationId, String sku) {}
    public record Event(int sequence, String type, String reservationId, String buyer, String orderId) {}
    public record Snapshot(int schema, int stock, String sku, List<Reservation> reservations,
                           List<Order> orders, List<Event> events) {
        public Snapshot {
            reservations = List.copyOf(reservations);
            orders = List.copyOf(orders);
            events = List.copyOf(events);
        }
    }
    public static final class Rejected extends RuntimeException {
        private final int status;
        public Rejected(int status, String reason) { super(reason); this.status = status; }
        public int status() { return status; }
    }

    private final Path file;
    private final ObjectMapper mapper;
    private final FileChannel lockChannel;
    private final FileLock fileLock;
    private Snapshot state;

    public InventoryStore(Path file, ObjectMapper mapper) throws IOException {
        this.file = file.toAbsolutePath();
        this.mapper = mapper;
        Files.createDirectories(this.file.getParent());
        lockChannel = FileChannel.open(this.file.resolveSibling(this.file.getFileName()+".lock"),
                StandardOpenOption.CREATE, StandardOpenOption.WRITE);
        FileLock acquired;
        try {
            acquired = lockChannel.tryLock();
            if (acquired == null) throw new IOException("State already owned by another process");
        } catch (IOException | RuntimeException error) { lockChannel.close(); throw error; }
        fileLock = acquired;
        try {
            state = Files.exists(this.file) ? mapper.readValue(this.file.toFile(), Snapshot.class)
                    : new Snapshot(1, 1, SKU, List.of(), List.of(), List.of());
            validate(state);
            if (!Files.exists(this.file)) persist(state);
        } catch (IOException | RuntimeException error) { close(); throw error; }
    }

    public synchronized Snapshot snapshot() { return state; }

    public synchronized Reservation reserve(String id, String buyer, String sku) throws IOException {
        identifier(id); identifier(buyer);
        if (!SKU.equals(sku)) throw new Rejected(400, "unsupported_sku");
        var prior = state.reservations().stream().filter(r -> r.id().equals(id)).findFirst();
        if (prior.isPresent()) {
            if (!prior.get().buyer().equals(buyer)) throw new Rejected(403, "wrong_owner");
            return prior.get(); // Never resurrect an expired/released reservation ID.
        }
        long held = state.reservations().stream().filter(r -> r.status()==Status.ACTIVE || r.status()==Status.CONFIRMED).count();
        if (held >= state.stock()) throw new Rejected(409, "out_of_stock");
        var reservation = new Reservation(id, buyer, sku, Status.ACTIVE);
        var reservations = new ArrayList<>(state.reservations()); reservations.add(reservation);
        commit(reservations, state.orders(), "RESERVED", reservation, null);
        return reservation;
    }

    public synchronized Order confirm(String id, String buyer, String orderId) throws IOException {
        identifier(id); identifier(buyer); identifier(orderId);
        var reservation = owned(id, buyer);
        var duplicate = state.orders().stream().filter(o -> o.id().equals(orderId)).findFirst();
        if (duplicate.isPresent()) {
            var order = duplicate.get();
            if (order.reservationId().equals(id) && order.buyer().equals(buyer)) return order;
            throw new Rejected(409, "order_id_conflict");
        }
        var confirmed = new Reservation(id, buyer, reservation.sku(), Status.CONFIRMED);
        var order = new Order(orderId, buyer, id, reservation.sku());
        var orders = new ArrayList<>(state.orders()); orders.add(order);
        commit(replace(confirmed), orders, "CONFIRMED", confirmed, orderId);
        return order;
    }

    public synchronized Reservation release(String id, String buyer) throws IOException {
        identifier(id); identifier(buyer);
        var reservation = owned(id, buyer);
        if (reservation.status()==Status.RELEASED) return reservation;
        if (reservation.status()!=Status.ACTIVE) throw new Rejected(409, "reservation_not_active");
        var released = new Reservation(id, buyer, reservation.sku(), Status.RELEASED);
        commit(replace(released), state.orders(), "RELEASED", released, null);
        return released;
    }

    /** Explicit evaluator lifecycle event; no claim that wall-clock TTL elapsed. */
    public synchronized Reservation expire(String id) throws IOException {
        identifier(id);
        var reservation = find(id);
        if (reservation.status()==Status.EXPIRED) return reservation;
        if (reservation.status()!=Status.ACTIVE) throw new Rejected(409, "reservation_not_active");
        var expired = new Reservation(id, reservation.buyer(), reservation.sku(), Status.EXPIRED);
        commit(replace(expired), state.orders(), "EXPIRED", expired, null);
        return expired;
    }

    private Reservation owned(String id, String buyer) {
        var reservation = find(id);
        if (!reservation.buyer().equals(buyer)) throw new Rejected(403, "wrong_owner");
        return reservation;
    }
    private Reservation find(String id) {
        return state.reservations().stream().filter(r -> r.id().equals(id)).findFirst()
                .orElseThrow(() -> new Rejected(404, "unknown_reservation"));
    }
    private static void identifier(String value) {
        if (value == null || !value.matches("[A-Za-z0-9_-]{1,64}")) throw new Rejected(400, "invalid_identifier");
    }
    private List<Reservation> replace(Reservation updated) {
        return state.reservations().stream().map(r -> r.id().equals(updated.id()) ? updated : r).toList();
    }
    private void commit(List<Reservation> reservations, List<Order> orders, String type,
                        Reservation reservation, String orderId) throws IOException {
        var events = new ArrayList<>(state.events());
        events.add(new Event(events.size()+1, type, reservation.id(), reservation.buyer(), orderId));
        var next = new Snapshot(1, 1, SKU, reservations, orders, events);
        validate(next);
        persist(next);
        state = next; // Failed persistence must not acknowledge/mutate a committed in-memory state.
    }
    private void persist(Snapshot next) throws IOException {
        var temporary = Files.createTempFile(file.getParent(), "inventory-", ".tmp");
        try {
            byte[] bytes = mapper.writeValueAsBytes(next);
            try (var channel = FileChannel.open(temporary, StandardOpenOption.WRITE)) {
                var buffer = ByteBuffer.wrap(bytes);
                while (buffer.hasRemaining()) channel.write(buffer);
                channel.force(true);
            }
            Files.move(temporary, file, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
        } finally { Files.deleteIfExists(temporary); }
    }
    private static void validate(Snapshot snapshot) throws IOException {
        if (snapshot.schema()!=1 || snapshot.stock()!=1 || !SKU.equals(snapshot.sku())) throw new IOException("Invalid inventory identity");
        Set<String> reservations = new HashSet<>(); Set<String> orders = new HashSet<>(); Set<String> allocated = new HashSet<>();
        for (var reservation : snapshot.reservations()) {
            if (reservation.status()==null || !SKU.equals(reservation.sku()) || !reservations.add(reservation.id())) throw new IOException("Invalid reservation state");
        }
        for (var order : snapshot.orders()) {
            var reservation = snapshot.reservations().stream().filter(r -> r.id().equals(order.reservationId())).findFirst();
            if (!orders.add(order.id()) || !allocated.add(order.reservationId()) || !SKU.equals(order.sku()) || reservation.isEmpty()
                    || reservation.get().status()!=Status.CONFIRMED || !reservation.get().buyer().equals(order.buyer())) throw new IOException("Invalid order allocation");
        }
        long held = snapshot.reservations().stream().filter(r -> r.status()==Status.ACTIVE || r.status()==Status.CONFIRMED).count();
        long confirmed = snapshot.reservations().stream().filter(r -> r.status()==Status.CONFIRMED).count();
        if (held>snapshot.stock() || confirmed!=snapshot.orders().size()) throw new IOException("Inventory conservation failed");
        for (int i=0; i<snapshot.events().size(); i++) if (snapshot.events().get(i).sequence()!=i+1) throw new IOException("Invalid event sequence");
    }
    @Override public void close() throws IOException { try { fileLock.release(); } finally { lockChannel.close(); } }
}
