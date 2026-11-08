package fit.iuh.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;
import org.springframework.validation.annotation.Validated;

@Data
@Validated
@Configuration
@ConfigurationProperties(prefix = "app")
public class AppProperties {

    /** External AI Service (FastAPI) configuration. */
    private Ai ai = new Ai();

    /** JWT security configuration. */
    private Jwt jwt = new Jwt();

    @Data
    public static class Ai {
        private Fastapi fastapi = new Fastapi();

        @Data
        public static class Fastapi {
            private String baseUrl = "http://localhost:8000";
            private int connectTimeoutSeconds = 15;
            private int readTimeoutSeconds = 180;
        }
    }

    @Data
    public static class Jwt {
        private String secret = "c3VwZXJzZWNyZXRrZXlmb3JkZXZlbG9wbWVudGVudmlyb25tZW50MjU2Yml0cw==";
        private long expirationMs = 86400000L;
    }
}
