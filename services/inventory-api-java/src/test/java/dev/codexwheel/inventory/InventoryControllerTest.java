package dev.codexwheel.inventory;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

class InventoryControllerTest {
    @TempDir Path directory;
    private static final String TOKEN = "test-only-evaluator-token-32-characters";
    @Test void evaluatorRequiresTokenAndDoesNotMutateOnDenial() throws Exception {
        try (var store = new InventoryStore(directory.resolve("state.json"), new ObjectMapper())) {
            store.reserve("rA", "A", InventoryStore.SKU);
            var mvc = MockMvcBuilders.standaloneSetup(new InventoryController(store, TOKEN)).build();
            mvc.perform(get("/internal/evaluator/state")).andExpect(status().isForbidden());
            mvc.perform(post("/internal/evaluator/trigger-expiry").contentType("application/json")
                    .content("{\"reservationId\":\"rA\"}")).andExpect(status().isForbidden());
            mvc.perform(get("/internal/evaluator/state").header("X-Evaluator-Token", "wrong")).andExpect(status().isForbidden());
            mvc.perform(get("/internal/evaluator/state").header("X-Evaluator-Token", TOKEN))
                    .andExpect(status().isOk()).andExpect(jsonPath("$.reservations[0].status").value("ACTIVE"));
            mvc.perform(post("/internal/evaluator/trigger-expiry").header("X-Evaluator-Token", TOKEN)
                    .contentType("application/json").content("{\"reservationId\":\"rA\"}"))
                    .andExpect(status().isOk()).andExpect(jsonPath("$.status").value("EXPIRED"));
        }
    }
    @Test void missingConfigurationDisablesEvaluatorEndpoints() throws Exception {
        try (var store = new InventoryStore(directory.resolve("state.json"), new ObjectMapper())) {
            var mvc = MockMvcBuilders.standaloneSetup(new InventoryController(store, "")).build();
            mvc.perform(get("/internal/evaluator/state").header("X-Evaluator-Token", TOKEN)).andExpect(status().isForbidden());
        }
    }
    @Test void checkoutResponseRequiresConfirmedAllocation() throws Exception {
        try (var store = new InventoryStore(directory.resolve("state.json"), new ObjectMapper())) {
            var mvc = MockMvcBuilders.standaloneSetup(new InventoryController(store, TOKEN)).build();
            mvc.perform(post("/reservations").contentType("application/json")
                    .content("{\"reservationId\":\"rA\",\"buyer\":\"A\",\"sku\":\"last-item\"}"))
                    .andExpect(status().isOk()).andExpect(jsonPath("$.status").value("ACTIVE"));
            store.expire("rA");
            mvc.perform(post("/reservations/rA/confirm").contentType("application/json")
                    .content("{\"buyer\":\"A\",\"orderId\":\"orderA\"}"))
                    .andExpect(status().isConflict()).andExpect(jsonPath("$.error").value("reservation_not_active"));
            mvc.perform(get("/internal/evaluator/state").header("X-Evaluator-Token", TOKEN))
                    .andExpect(status().isOk()).andExpect(jsonPath("$.orders.length()").value(0));
        }
    }
}
