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
                span, span, "matched",
                "Found in CV", null, null, null, null, null, null, null
        );

        EvidenceItem result = validator.validateAndApply(item, SAMPLE_CV_MARKDOWN, 0.75);

        assertNotNull(result);
        assertEquals("matched", result.status());
        assertNotNull(result.groundingScore());
        assertTrue(result.groundingScore() >= 0.75, "Grounding score should be >= 0.75 for exact quote match");
    }

    @Test
    @DisplayName("Hallucinated Evidence — Grounding score below threshold should downgrade 'matched' to 'partial'")
    void testHallucinatedMatchedDowngradedToPartial() {
        String hallucinatedSpan = "Developed quantum computing algorithms with IBM Qiskit and Rust in production";
        EvidenceItem item = new EvidenceItem(
                2L, "Quantum Tech Stack", "REQUIRED", "Quantum computing with Qiskit",
                hallucinatedSpan, hallucinatedSpan, "matched",
                "Hallucinated evidence", null, null, null, null, null, null, null
        );

        EvidenceItem result = validator.validateAndApply(item, SAMPLE_CV_MARKDOWN, 0.75);

        assertNotNull(result);
        assertEquals("partial", result.status(), "Status 'matched' should be downgraded to 'partial' when hallucinated");
        assertTrue(result.groundingScore() < 0.75, "Grounding score should be < 0.75 for hallucinated span");
    }

    @Test
    @DisplayName("Hallucinated Evidence — Grounding score below threshold should downgrade 'partial' to 'weak'")
    void testHallucinatedPartialDowngradedToWeak() {
        String hallucinatedSpan = "Developed quantum computing algorithms with IBM Qiskit and Rust in production";
        EvidenceItem item = new EvidenceItem(
                2L, "Quantum Tech Stack", "REQUIRED", "Quantum computing with Qiskit",
                hallucinatedSpan, hallucinatedSpan, "partial",
                "Hallucinated evidence", null, null, null, null, null, null, null
        );

        EvidenceItem result = validator.validateAndApply(item, SAMPLE_CV_MARKDOWN, 0.75);

        assertNotNull(result);
        assertEquals("weak", result.status(), "Status 'partial' should be downgraded to 'weak' when hallucinated");
    }

    @Test
    @DisplayName("Hallucinated Evidence — Grounding score below threshold should downgrade 'weak' to 'missing'")
    void testHallucinatedWeakDowngradedToMissing() {
        String hallucinatedSpan = "Scrum Master certified by Scrum Alliance with 5 years agile coaching";
        EvidenceItem item = new EvidenceItem(
                3L, "Scrum Coaching", "REQUIRED", "Scrum Master Certification",
                hallucinatedSpan, hallucinatedSpan, "weak",
                "Hallucinated evidence", null, null, null, null, null, null, null
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
                null, null, "missing",
                "Requirement completely absent", null, null, null, null, null, null, null
        );

        EvidenceItem result = validator.validateAndApply(item, SAMPLE_CV_MARKDOWN, 0.75);

        assertNotNull(result);
        assertEquals("missing", result.status());
        assertEquals(1.0, result.groundingScore(), "Missing status should have score 1.0");
    }

    @Test
    @DisplayName("Short & Special Tech Terms — Go, C++, C# in CV should be accurately grounded without false downgrade")
    void testShortAndSpecialTechTermsGrounding() {
        String cvWithSpecialTech = """
                # Developer Profile
                * Core Languages: Go, C++, C#, Java
                * Built high-concurrency microservices using Go and C++ backend.
                """;

        String spanGo = "Built high-concurrency microservices using Go";
        EvidenceItem itemGo = new EvidenceItem(
                5L, "Go Programming", "REQUIRED", "Go microservices",
                spanGo, spanGo, "matched",
                "Found in CV", null, null, null, null, null, null, null
        );
        EvidenceItem resultGo = validator.validateAndApply(itemGo, cvWithSpecialTech, 0.75);
        assertEquals("matched", resultGo.status(), "Go skill should be grounded and remain matched");

        String spanCpp = "C++ backend";
        EvidenceItem itemCpp = new EvidenceItem(
                6L, "C++ Systems", "REQUIRED", "C++ programming",
                spanCpp, spanCpp, "matched",
                "Found in CV", null, null, null, null, null, null, null
        );
        EvidenceItem resultCpp = validator.validateAndApply(itemCpp, cvWithSpecialTech, 0.75);
        assertEquals("matched", resultCpp.status(), "C++ skill should be grounded and remain matched");
    }

    @Test
    @DisplayName("Empty Evidence on Matched Status — Should be downgraded to missing due to lack of proof")
    void testEmptyEvidenceOnMatchedDowngradedToMissing() {
        EvidenceItem item = new EvidenceItem(
                7L, "Microservices Architecture", "REQUIRED", "Microservices design",
                null, null, "matched",
                "Claimed match but no proof", null, null, null, null, null, null, null
        );

        EvidenceItem result = validator.validateAndApply(item, SAMPLE_CV_MARKDOWN, 0.75);

        assertNotNull(result);
        assertEquals("missing", result.status(), "Claimed matched with null evidence must be downgraded to missing");
        assertTrue(result.needsManualReview());
    }

    @Test
    @DisplayName("Vietnamese Evidence with English Quote — Soft skills with quotes should not be falsely downgraded")
    void testVietnameseEvidenceWithQuote() {
        String cvText = """
                # Developer Profile
                * Strong problem solving and team collaboration skills across cross-functional engineering teams.
                """;

        EvidenceItem item = new EvidenceItem(
                8L, "Problem Solving & Teamwork", "REQUIRED", "Team collaboration",
                "Ứng viên có kỹ năng giải quyết vấn đề và làm việc nhóm hiệu quả",
                "team collaboration skills across cross-functional engineering teams",
                "matched",
                "Demonstrated in profile", null, null, null, null, null, null, null
        );

        EvidenceItem result = validator.validateAndApply(item, cvText, 0.75);
        assertNotNull(result);
        assertEquals("matched", result.status(), "Soft skill with English quote from CV should remain matched");
    }
}
