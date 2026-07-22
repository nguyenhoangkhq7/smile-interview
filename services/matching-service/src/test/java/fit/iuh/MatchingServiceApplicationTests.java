package fit.iuh;

import org.junit.jupiter.api.Disabled;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;

@SpringBootTest
@Disabled("Requires active PostgreSQL & Redis instances")
class MatchingServiceApplicationTests {

    @Test
    void contextLoads() {
    }
}
