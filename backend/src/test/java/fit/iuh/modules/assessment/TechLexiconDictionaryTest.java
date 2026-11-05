package fit.iuh.modules.assessment;

import fit.iuh.modules.assessment.dto.AssessmentResponseDto;
import fit.iuh.modules.assessment.service.EvidenceGroundingValidator;
import fit.iuh.modules.assessment.util.TechLexiconDictionary;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.*;

class TechLexiconDictionaryTest {

    @Test
    @DisplayName("Should resolve synonyms for popular tech acronyms and aliases across multiple domains")
    void testSynonymResolution() {
        // DevOps / Cloud
        Set<String> k8sSynonyms = TechLexiconDictionary.getSynonyms("k8s");
        assertTrue(k8sSynonyms.contains("kubernetes"));
        assertTrue(k8sSynonyms.contains("k8s"));
        assertTrue(k8sSynonyms.contains("kube"));

        Set<String> gcpSynonyms = TechLexiconDictionary.getSynonyms("gcp");
        assertTrue(gcpSynonyms.contains("google cloud"));
        assertTrue(gcpSynonyms.contains("google cloud platform"));

        Set<String> awsSynonyms = TechLexiconDictionary.getSynonyms("aws");
        assertTrue(awsSynonyms.contains("amazon web services"));

        // Languages
        Set<String> golangSynonyms = TechLexiconDictionary.getSynonyms("golang");
        assertTrue(golangSynonyms.contains("go"));
        assertTrue(golangSynonyms.contains("golang"));

        Set<String> tsSynonyms = TechLexiconDictionary.getSynonyms("ts");
        assertTrue(tsSynonyms.contains("typescript"));

        Set<String> jsSynonyms = TechLexiconDictionary.getSynonyms("javascript");
        assertTrue(jsSynonyms.contains("js"));
        assertTrue(jsSynonyms.contains("ecmascript"));
        assertTrue(jsSynonyms.contains("es6"));

        Set<String> cppSynonyms = TechLexiconDictionary.getSynonyms("c++");
        assertTrue(cppSynonyms.contains("cpp"));
        assertTrue(cppSynonyms.contains("c/c++"));

        Set<String> csharpSynonyms = TechLexiconDictionary.getSynonyms("c#");
        assertTrue(csharpSynonyms.contains("csharp"));
        assertTrue(csharpSynonyms.contains(".net"));
        assertTrue(csharpSynonyms.contains("dotnet"));

        // Databases
        Set<String> postgresSynonyms = TechLexiconDictionary.getSynonyms("postgres");
        assertTrue(postgresSynonyms.contains("postgresql"));
        assertTrue(postgresSynonyms.contains("psql"));

        Set<String> mongoSynonyms = TechLexiconDictionary.getSynonyms("mongodb");
        assertTrue(mongoSynonyms.contains("mongo"));

        Set<String> esSynonyms = TechLexiconDictionary.getSynonyms("elasticsearch");
        assertTrue(esSynonyms.contains("es"));
        assertTrue(esSynonyms.contains("elk"));
        assertTrue(esSynonyms.contains("elastic search"));

        // Frontend
        Set<String> reactSynonyms = TechLexiconDictionary.getSynonyms("react");
        assertTrue(reactSynonyms.contains("reactjs"));
        assertTrue(reactSynonyms.contains("react.js"));
        assertTrue(reactSynonyms.contains("react-native"));

        Set<String> nextSynonyms = TechLexiconDictionary.getSynonyms("next.js");
        assertTrue(nextSynonyms.contains("nextjs"));
        assertTrue(nextSynonyms.contains("next"));

        Set<String> tailwindSynonyms = TechLexiconDictionary.getSynonyms("tailwind");
        assertTrue(tailwindSynonyms.contains("tailwindcss"));

        // Backend
        Set<String> springSynonyms = TechLexiconDictionary.getSynonyms("spring boot");
        assertTrue(springSynonyms.contains("spring"));
        assertTrue(springSynonyms.contains("springboot"));
        assertTrue(springSynonyms.contains("spring framework"));

        Set<String> nodeSynonyms = TechLexiconDictionary.getSynonyms("node.js");
        assertTrue(nodeSynonyms.contains("nodejs"));
        assertTrue(nodeSynonyms.contains("node"));

        Set<String> djangoSynonyms = TechLexiconDictionary.getSynonyms("django");
        assertTrue(djangoSynonyms.contains("django rest framework"));
        assertTrue(djangoSynonyms.contains("drf"));

        // AI / ML / GenAI
        Set<String> aiSynonyms = TechLexiconDictionary.getSynonyms("ai");
        assertTrue(aiSynonyms.contains("artificial intelligence"));
        assertTrue(aiSynonyms.contains("machine learning"));
        assertTrue(aiSynonyms.contains("trí tuệ nhân tạo"));
        assertTrue(aiSynonyms.contains("học máy"));

        Set<String> llmSynonyms = TechLexiconDictionary.getSynonyms("llm");
        assertTrue(llmSynonyms.contains("large language models"));
        assertTrue(llmSynonyms.contains("genai"));
        assertTrue(llmSynonyms.contains("generative ai"));
        assertTrue(llmSynonyms.contains("rag"));
        assertTrue(llmSynonyms.contains("langchain"));

        // Big Data
        Set<String> sparkSynonyms = TechLexiconDictionary.getSynonyms("spark");
        assertTrue(sparkSynonyms.contains("apache spark"));
        assertTrue(sparkSynonyms.contains("pyspark"));
    }

    @Test
    @DisplayName("Should canonicalize acronyms and aliases to canonical names")
    void testCanonicalization() {
        assertEquals("kubernetes", TechLexiconDictionary.getCanonical("k8s"));
        assertEquals("postgresql", TechLexiconDictionary.getCanonical("postgres"));
        assertEquals("golang", TechLexiconDictionary.getCanonical("go"));
        assertEquals("google cloud", TechLexiconDictionary.getCanonical("gcp"));
        assertEquals("react", TechLexiconDictionary.getCanonical("reactjs"));
        assertEquals("typescript", TechLexiconDictionary.getCanonical("ts"));
        assertEquals("microservices", TechLexiconDictionary.getCanonical("vi dịch vụ"));
        assertEquals("oop", TechLexiconDictionary.getCanonical("lập trình hướng đối tượng"));
        assertEquals("spring boot", TechLexiconDictionary.getCanonical("springboot"));
        assertEquals("ci/cd", TechLexiconDictionary.getCanonical("cicd"));
        assertEquals("jwt", TechLexiconDictionary.getCanonical("json web token"));
    }

    @Test
    @DisplayName("Should match tech terms when CV contains abbreviations or synonyms")
    void testContainsTechOrSynonym() {
        String cvText = "Engineered microservices deployed on K8s cluster using Postgres database, Go backend, Kafka streaming, and PyTorch ML models.";

        assertTrue(TechLexiconDictionary.containsTechOrSynonym(cvText, "Kubernetes"));
        assertTrue(TechLexiconDictionary.containsTechOrSynonym(cvText, "PostgreSQL"));
        assertTrue(TechLexiconDictionary.containsTechOrSynonym(cvText, "Golang"));
        assertTrue(TechLexiconDictionary.containsTechOrSynonym(cvText, "Microservices"));
        assertTrue(TechLexiconDictionary.containsTechOrSynonym(cvText, "Apache Kafka"));
        assertTrue(TechLexiconDictionary.containsTechOrSynonym(cvText, "Machine Learning"));
        assertTrue(TechLexiconDictionary.containsTechOrSynonym(cvText, "PyTorch"));

        assertFalse(TechLexiconDictionary.containsTechOrSynonym(cvText, "Rust"));
        assertFalse(TechLexiconDictionary.containsTechOrSynonym(cvText, "MongoDB"));
        assertFalse(TechLexiconDictionary.containsTechOrSynonym(cvText, "Flutter"));
    }

    @Test
    @DisplayName("Should recognize bilingual Vietnamese - English tech terms")
    void testBilingualMatching() {
        String cvVietnamese = "Ứng viên có 3 năm kinh nghiệm phát triển hệ thống vi dịch vụ, áp dụng lập trình hướng đối tượng và xử lý ngôn ngữ tự nhiên.";

        assertTrue(TechLexiconDictionary.containsTechOrSynonym(cvVietnamese, "Microservices"));
        assertTrue(TechLexiconDictionary.containsTechOrSynonym(cvVietnamese, "OOP"));
        assertTrue(TechLexiconDictionary.containsTechOrSynonym(cvVietnamese, "NLP"));

        String cvEnglish = "Built high-performance microservices following OOP principles and NLP pipeline using BERT.";
        assertTrue(TechLexiconDictionary.containsTechOrSynonym(cvEnglish, "vi dịch vụ"));
        assertTrue(TechLexiconDictionary.containsTechOrSynonym(cvEnglish, "lập trình hướng đối tượng"));
        assertTrue(TechLexiconDictionary.containsTechOrSynonym(cvEnglish, "xử lý ngôn ngữ tự nhiên"));
    }

    @Test
    @DisplayName("Should identify short technical terms accurately")
    void testShortTermsRecognition() {
        assertTrue(TechLexiconDictionary.isKnownShortTerm("AI"));
        assertTrue(TechLexiconDictionary.isKnownShortTerm("ML"));
        assertTrue(TechLexiconDictionary.isKnownShortTerm("DL"));
        assertTrue(TechLexiconDictionary.isKnownShortTerm("CV"));
        assertTrue(TechLexiconDictionary.isKnownShortTerm("GO"));
        assertTrue(TechLexiconDictionary.isKnownShortTerm("C"));
        assertTrue(TechLexiconDictionary.isKnownShortTerm("R"));
        assertTrue(TechLexiconDictionary.isKnownShortTerm("JS"));
        assertTrue(TechLexiconDictionary.isKnownShortTerm("TS"));
        assertTrue(TechLexiconDictionary.isKnownShortTerm("DB"));
        assertTrue(TechLexiconDictionary.isKnownShortTerm("OS"));
        assertTrue(TechLexiconDictionary.isKnownShortTerm("IP"));
        assertTrue(TechLexiconDictionary.isKnownShortTerm("K8S"));
        assertTrue(TechLexiconDictionary.isKnownShortTerm("AWS"));
        assertTrue(TechLexiconDictionary.isKnownShortTerm("GCP"));
        assertTrue(TechLexiconDictionary.isKnownShortTerm("S3"));
        assertTrue(TechLexiconDictionary.isKnownShortTerm("EC2"));
        assertTrue(TechLexiconDictionary.isKnownShortTerm("RDS"));
        assertTrue(TechLexiconDictionary.isKnownShortTerm("CI"));
        assertTrue(TechLexiconDictionary.isKnownShortTerm("CD"));

        assertFalse(TechLexiconDictionary.isKnownShortTerm("FOO"));
        assertFalse(TechLexiconDictionary.isKnownShortTerm("XYZ"));
        assertFalse(TechLexiconDictionary.isKnownShortTerm("ABC"));
    }

    @Test
    @DisplayName("Should expand token collection with all synonyms")
    void testExpandTokensWithSynonyms() {
        List<String> tokens = List.of("k8s", "postgres", "fastapi");
        Set<String> expanded = TechLexiconDictionary.expandTokensWithSynonyms(tokens);

        assertTrue(expanded.contains("kubernetes"));
        assertTrue(expanded.contains("k8s"));
        assertTrue(expanded.contains("kube"));
        assertTrue(expanded.contains("postgresql"));
        assertTrue(expanded.contains("postgres"));
        assertTrue(expanded.contains("psql"));
        assertTrue(expanded.contains("fastapi"));
        assertTrue(expanded.contains("fast api"));
    }

    @Test
    @DisplayName("EvidenceGroundingValidator should accept evidence when CV has modern acronyms & AI/Cloud tech")
    void testGroundingWithSynonyms() {
        EvidenceGroundingValidator validator = new EvidenceGroundingValidator();
        String cvText = """
                # Senior Fullstack & AI Engineer
                - Architected microservices on AWS EKS using Go, Spring Boot 3.3, and PostgreSQL.
                - Deployed LLM RAG pipelines using LangChain, pgvector, and FastAPI.
                - Configured automated CI/CD with GitHub Actions and Terraform.
                """;

        AssessmentResponseDto.EvidenceItem item = new AssessmentResponseDto.EvidenceItem(
                1L, "Cloud Native Architecture", "REQUIRED", "Experience with Kubernetes, AWS, and PostgreSQL",
                "Ứng viên có kinh nghiệm với Kubernetes (EKS), AWS và PostgreSQL",
                "Architected microservices on AWS EKS using Go, Spring Boot 3.3, and PostgreSQL.",
                "matched", "Excellent match",
                15.0, 15.0, 1.0, null, null, null, null
        );

        AssessmentResponseDto.EvidenceItem validated = validator.validateAndApply(item, cvText, 0.50);

        assertNotNull(validated);
        assertEquals("matched", validated.status(), "Status should remain matched because EKS, Go, Spring Boot match via TechLexiconDictionary");
        assertFalse(Boolean.TRUE.equals(validated.needsManualReview()));

        // Test GenAI & RAG grounding
        AssessmentResponseDto.EvidenceItem itemAi = new AssessmentResponseDto.EvidenceItem(
                2L, "Generative AI & LLM", "REQUIRED", "LLM RAG implementation",
                "Ứng viên xây dựng hệ thống Generative AI và RAG với LangChain và FastAPI",
                "Deployed LLM RAG pipelines using LangChain, pgvector, and FastAPI.",
                "matched", "Strong AI background",
                15.0, 15.0, 1.0, null, null, null, null
        );

        AssessmentResponseDto.EvidenceItem validatedAi = validator.validateAndApply(itemAi, cvText, 0.50);
        assertNotNull(validatedAi);
        assertEquals("matched", validatedAi.status(), "Generative AI / RAG evidence should be successfully grounded");
    }
}
