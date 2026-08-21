package fit.iuh.modules.assessment;

import fit.iuh.modules.assessment.dto.AssessmentResponseDto;
import fit.iuh.modules.assessment.service.EvidenceGroundingValidator;
import fit.iuh.modules.assessment.util.TechLexiconDictionary;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.Set;

import static org.junit.jupiter.api.Assertions.*;

class TechLexiconDictionaryTest {

    @Test
    @DisplayName("Should resolve synonyms for popular tech acronyms and aliases")
    void testSynonymResolution() {
        Set<String> k8sSynonyms = TechLexiconDictionary.getSynonyms("k8s");
        assertTrue(k8sSynonyms.contains("kubernetes"));
        assertTrue(k8sSynonyms.contains("k8s"));
        assertTrue(k8sSynonyms.contains("kube"));

        Set<String> golangSynonyms = TechLexiconDictionary.getSynonyms("golang");
        assertTrue(golangSynonyms.contains("go"));
        assertTrue(golangSynonyms.contains("golang"));

        Set<String> postgresSynonyms = TechLexiconDictionary.getSynonyms("postgres");
        assertTrue(postgresSynonyms.contains("postgresql"));
        assertTrue(postgresSynonyms.contains("psql"));

        Set<String> gcpSynonyms = TechLexiconDictionary.getSynonyms("gcp");
        assertTrue(gcpSynonyms.contains("google cloud"));
        assertTrue(gcpSynonyms.contains("google cloud platform"));

        Set<String> reactSynonyms = TechLexiconDictionary.getSynonyms("react");
        assertTrue(reactSynonyms.contains("reactjs"));
        assertTrue(reactSynonyms.contains("react.js"));
    }

    @Test
    @DisplayName("Should canonicalize acronyms to canonical names")
    void testCanonicalization() {
        assertEquals("kubernetes", TechLexiconDictionary.getCanonical("k8s"));
        assertEquals("postgresql", TechLexiconDictionary.getCanonical("postgres"));
        assertEquals("golang", TechLexiconDictionary.getCanonical("go"));
        assertEquals("google cloud", TechLexiconDictionary.getCanonical("gcp"));
    }

    @Test
    @DisplayName("Should match tech terms when CV contains abbreviations")
    void testContainsTechOrSynonym() {
        String cvText = "Engineered microservices deployed on K8s cluster using Postgres database and Go backend.";

        assertTrue(TechLexiconDictionary.containsTechOrSynonym(cvText, "Kubernetes"));
        assertTrue(TechLexiconDictionary.containsTechOrSynonym(cvText, "PostgreSQL"));
        assertTrue(TechLexiconDictionary.containsTechOrSynonym(cvText, "Golang"));
        assertTrue(TechLexiconDictionary.containsTechOrSynonym(cvText, "Microservices"));

        assertFalse(TechLexiconDictionary.containsTechOrSynonym(cvText, "Rust"));
        assertFalse(TechLexiconDictionary.containsTechOrSynonym(cvText, "MongoDB"));
    }

    @Test
    @DisplayName("EvidenceGroundingValidator should accept evidence when CV has acronyms")
    void testGroundingWithSynonyms() {
        EvidenceGroundingValidator validator = new EvidenceGroundingValidator();
        String cvText = "# Experience\n- Deployed containerized applications on K8s cluster with Postgres db.";

        AssessmentResponseDto.EvidenceItem item = new AssessmentResponseDto.EvidenceItem(
                1L, "Kubernetes Orchestration", "REQUIRED", "Experience with Kubernetes and PostgreSQL",
                "Ứng viên có kinh nghiệm với Kubernetes và PostgreSQL trong dự án",
                "Deployed containerized applications on K8s cluster with Postgres db.",
                "matched", "Good match",
                15.0, 15.0, 1.0, null, null, null, null
        );

        AssessmentResponseDto.EvidenceItem validated = validator.validateAndApply(item, cvText, 0.50);

        assertNotNull(validated);
        assertEquals("matched", validated.status(), "Status should remain matched because k8s and postgres match Kubernetes and PostgreSQL via TechLexiconDictionary");
        assertFalse(Boolean.TRUE.equals(validated.needsManualReview()));
    }
}
