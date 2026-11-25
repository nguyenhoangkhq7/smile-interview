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
}
