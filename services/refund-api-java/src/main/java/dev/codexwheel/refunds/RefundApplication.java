package dev.codexwheel.refunds;

import dev.codexwheel.refunds.domain.RefundService;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;

@SpringBootApplication
public class RefundApplication {
    public static void main(String[] args) { SpringApplication.run(RefundApplication.class, args); }
    @Bean public RefundService refundService() { return new RefundService(); }
}
