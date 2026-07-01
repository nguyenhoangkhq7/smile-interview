package fit.iuh.service.questionbank;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class SemanticCacheKeyGeneratorTest {

    private final SemanticCacheKeyGenerator generator = new SemanticCacheKeyGenerator();

    @Test
    void testStandardizationAndNormalization() {
        // JD requirements with synonym variations and stop words
        String jd1 = "Must have experience with Java 21, Spring Boot framework, and building RESTful APIs.";
        String jd2 = "Proficient in Core Java, Spring Boot, and REST API development.";

        // CV experiences with synonym variations and casing differences
        String cv1 = "Developed backend applications using Java 17 and Spring Boot microservices.";
        String cv2 = "Worked as a Backend Java developer, utilizing SpringBoot to build micro-services.";

        // Generate cache keys
        String key1 = generator.generateKey(jd1, cv1);
        String key2 = generator.generateKey(jd2, cv2);

        // Assert that they resolve to the exact same cache key despite text differences
        assertEquals(key1, key2, "Keys should be identical for semantically equivalent concepts");
    }

    @Test
    void testStopwordsAndSorting() {
        String jd1 = "Docker and Kubernetes";
        String jd2 = "Kubernetes or Docker container";

        String cv1 = "Postgres, MongoDB";
        String cv2 = "mongodb, postgresql";

        String key1 = generator.generateKey(jd1, cv1);
        String key2 = generator.generateKey(jd2, cv2);

        assertEquals(key1, key2, "Keys should be order-independent and ignore stop words");
    }
}
