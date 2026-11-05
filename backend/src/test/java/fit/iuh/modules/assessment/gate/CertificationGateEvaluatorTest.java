package fit.iuh.modules.assessment.gate;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

class CertificationGateEvaluatorTest {

    private CertificationGateEvaluator evaluator;

    @BeforeEach
    void setUp() {
        evaluator = new CertificationGateEvaluator();
    }

    @Test
    @DisplayName("Check supported criteria names for certification gates")
    void testSupports() {
        assertTrue(evaluator.supports("AWS Certification"));
        assertTrue(evaluator.supports("Chứng chỉ ngoại ngữ IELTS"));
        assertTrue(evaluator.supports("Professional Certificate in Java"));
        assertTrue(evaluator.supports("Yêu cầu chứng chỉ PMP"));
        assertFalse(evaluator.supports("Years of Experience"));
        assertFalse(evaluator.supports("Degree Qualification"));
    }

    @Test
    @DisplayName("Evaluate AWS certification when CV has AWS Certified Developer")
    void testAwsCertificationFound() {
        String cvContent = """
                # Nguyen Van A
                ## Certifications
                - AWS Certified Solutions Architect Associate (2023)
                - Oracle Certified Professional: Java SE 11
                """;

        var result = evaluator.evaluate("AWS Certification", "AWS Certified Solutions Architect", cvContent);
        assertTrue(result.evaluated());
        assertTrue(result.passed());
        assertTrue(result.cvEvidence().contains("AWS"));
    }

    @Test
    @DisplayName("Evaluate AWS certification when CV does not have AWS")
    void testAwsCertificationNotFound() {
        String cvContent = """
                # Le Van B
                ## Experience
                3 years Java backend developer with Spring Boot.
                """;

        var result = evaluator.evaluate("AWS Certification", "AWS Certified Solutions Architect", cvContent);
        assertTrue(result.evaluated());
        assertFalse(result.passed());
    }

    @Test
    @DisplayName("Evaluate IELTS language certificate")
    void testIeltsCertification() {
        String cvWithIelts = "Language: English (IELTS 7.5), Vietnamese (Native)";
        var resultPass = evaluator.evaluate("Chứng chỉ IELTS", "IELTS 6.5+", cvWithIelts);
        assertTrue(resultPass.passed());

        String cvWithoutIelts = "Language: English basic communication";
        var resultFail = evaluator.evaluate("Chứng chỉ IELTS", "IELTS 6.5+", cvWithoutIelts);
        assertFalse(resultFail.passed());
    }
}
