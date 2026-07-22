package fit.iuh.modules.assessment;

import fit.iuh.modules.assessment.dto.AssessmentResponseDto.EvidenceItem;
import fit.iuh.modules.assessment.service.EvidenceGroundingValidator;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

class EvidenceGroundingValidatorTest {

    private EvidenceGroundingValidator validator;

    private static final String SAMPLE_CV_MARKDOWN = """
            # Nguyen Van A | Backend Developer
            
            ## Technical Skills
            * Languages: Java 21, SQL, Python
            * Frameworks: Spring Boot 3.3, Hibernate, WebFlux
            * Cloud & DevOps: Docker, Kubernetes, AWS S3, CI/CD GitHub Actions
            
            ## Experience
            ### Senior Backend Engineer | Tech Corp | 2022 - Present
            * Designed and implemented high-throughput microservices using Spring Boot 3.3 and Java 21.
            * Optimized database query performance on PostgreSQL with custom indexes, reducing query latency by 40%.
            * Deployed services on AWS Kubernetes EKS cluster with Automated CI/CD pipelines.
            """;

    @BeforeEach
    void setUp() {
        validator = new EvidenceGroundingValidator();
    }

    @Test
    @DisplayName("High Grounding Match — Exact quote from CV should keep 'matched' status and score >= 0.75")
    void testHighGroundingMatch() {
        String span = "Designed and implemented high-throughput microservices using Spring Boot 3.3 and Java 21";
        EvidenceItem item = new EvidenceItem(
                1L, "Tech Stack Alignment", "REQUIRED", "Java 21 & Spring Boot",
                "Has Java 21 & Spring Boot 3.3", "matched",
                "Found in CV", null, null, span, null, null, null, null
        );

        EvidenceItem result = validator.validateAndApply(item, SAMPLE_CV_MARKDOWN, 0.75);

        assertNotNull(result);
        assertEquals("matched", result.status());
        assertNotNull(result.groundingScore());
        assertTrue(result.groundingScore() >= 0.75, "Grounding score should be >= 0.75 for exact quote match");
    }

    @Test
    @DisplayName("Hallucinated Evidence — Grounding score below threshold should downgrade 'matched' to 'weak'")
    void testHallucinatedMatchedDowngradedToWeak() {
        String hallucinatedSpan = "Developed quantum computing algorithms with IBM Qiskit and Rust in production";
        EvidenceItem item = new EvidenceItem(
                2L, "Quantum Tech Stack", "REQUIRED", "Quantum computing with Qiskit",
                "Used Qiskit in production", "matched",
                "Hallucinated evidence", null, null, hallucinatedSpan, null, null, null, null
        );

        EvidenceItem result = validator.validateAndApply(item, SAMPLE_CV_MARKDOWN, 0.75);

        assertNotNull(result);
        assertEquals("weak", result.status(), "Status 'matched' should be downgraded to 'weak' when hallucinated");
        assertTrue(result.groundingScore() < 0.75, "Grounding score should be < 0.75 for hallucinated span");
    }

    @Test
    @DisplayName("Hallucinated Evidence — Grounding score below threshold should downgrade 'weak' to 'missing'")
    void testHallucinatedWeakDowngradedToMissing() {
        String hallucinatedSpan = "Scrum Master certified by Scrum Alliance with 5 years agile coaching";
        EvidenceItem item = new EvidenceItem(
                3L, "Scrum Coaching", "REQUIRED", "Scrum Master Certification",
                "Mentioned agile coaching", "weak",
                "Hallucinated evidence", null, null, hallucinatedSpan, null, null, null, null
        );

        EvidenceItem result = validator.validateAndApply(item, SAMPLE_CV_MARKDOWN, 0.75);

        assertNotNull(result);
        assertEquals("missing", result.status(), "Status 'weak' should be downgraded to 'missing' when hallucinated");
    }

    @Test
    @DisplayName("Missing Status — Missing status does not require a source_span and keeps 1.0 grounding score")
    void testMissingStatusNoSpanRequired() {
        EvidenceItem item = new EvidenceItem(
                4L, "Golang Experience", "REQUIRED", "Golang 1.22 requirement",
                null, "missing",
                "Requirement completely absent", null, null, null, null, null, null, null
        );

        EvidenceItem result = validator.validateAndApply(item, SAMPLE_CV_MARKDOWN, 0.75);

        assertNotNull(result);
        assertEquals("missing", result.status());
        assertEquals(1.0, result.groundingScore(), "Missing status should have score 1.0");
    }
}
