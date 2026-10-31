package dev.codexwheel.inventory;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.nio.file.Path;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;

@SpringBootApplication
public class InventoryApplication {
    public static void main(String[] args) { SpringApplication.run(InventoryApplication.class, args); }

    @Bean(destroyMethod = "close")
    InventoryStore inventoryStore(ObjectMapper mapper,
            @Value("${inventory.state-path}") String path) throws IOException {
        return new InventoryStore(Path.of(path), mapper);
    }
}
