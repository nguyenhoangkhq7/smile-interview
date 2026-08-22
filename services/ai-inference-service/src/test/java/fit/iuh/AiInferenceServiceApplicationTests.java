package fit.iuh;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;

@SpringBootTest(properties = {
        "grpc.server.in-process-name=test",
        "grpc.server.port=-1"
})
class AiInferenceServiceApplicationTests {

    @Test
    void contextLoads() {
    }

}
