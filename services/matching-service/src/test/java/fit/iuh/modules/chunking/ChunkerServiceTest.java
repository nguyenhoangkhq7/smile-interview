package fit.iuh.modules.chunking;

import fit.iuh.modules.chunking.entity.DocumentChunk;
import fit.iuh.modules.chunking.service.ChunkerService;
import fit.iuh.modules.chunking.service.impl.ChunkerServiceImpl;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

class ChunkerServiceTest {

    private ChunkerService chunkerService;

    @BeforeEach
    void setUp() {
        chunkerService = new ChunkerServiceImpl();
    }

    @Test
    void testChunkCvMarkdownWithStructureAwareDomainChunking() {
        String cvMarkdown = """
                # Contact
                Nguyen Van A | email@example.com | Hanoi

                # Summary
                Experienced Senior Backend Engineer with 5 years in Java and Spring Boot microservices.

                # Technical Skills
                * Languages: Java, Python, TypeScript
                * Frameworks: Spring Boot, ExpressJS
                * Databases: PostgreSQL, Redis, MongoDB
                * DevOps: Docker, Kubernetes, CI/CD

                # Technical Projects
                ## E-Commerce Platform
                * Role/Duration: Senior Backend Lead | 2022 - Present
                * Tech Stack: Java, Spring Boot, PostgreSQL, Redis, Docker, JWT
                * Overview: High-throughput e-commerce platform processing 10k orders daily.
                * Architecture & Contributions:
                  - Implemented JWT authentication and OAuth2 login with token blacklist.
                  - Optimized database query performance using PostgreSQL indexing and Redis caching.
                * Features & Optimizations:
                  - Reduced API latency by 40% using Redis caching.
                  - Containerized microservices using Docker and CI/CD pipelines.
                """;

        List<DocumentChunk> chunks = chunkerService.chunk(cvMarkdown, "session-123", "cv");

        assertNotNull(chunks);
        assertFalse(chunks.isEmpty());

        // Check flat sections exist
        boolean hasSummary = chunks.stream().anyMatch(c -> c.getContent().contains("Summary"));
        boolean hasSkills = chunks.stream().anyMatch(c -> c.getContent().contains("Technical Skills"));
        assertTrue(hasSummary, "Should create summary flat chunk");
        assertTrue(hasSkills, "Should create skills flat chunk");

        // Check project overview parent chunk
        DocumentChunk parentProj = chunks.stream()
                .filter(c -> "project_overview".equals(c.getChunkType()))
                .findFirst()
                .orElse(null);

        assertNotNull(parentProj, "Should create parent project overview chunk");
        assertEquals("session-123", parentProj.getSessionId());
        assertNull(parentProj.getParentId(), "Parent chunk should have null parentId");

        // Check domain child chunks linked to parent
        List<DocumentChunk> childChunks = chunks.stream()
                .filter(c -> "domain_child".equals(c.getChunkType()))
                .toList();

        assertFalse(childChunks.isEmpty(), "Should create child domain chunks for project");
        for (DocumentChunk child : childChunks) {
            assertEquals(parentProj.getId(), child.getParentId(), "Child chunk parentId must match parent project overview ID");
            assertNotNull(child.getDomain(), "Child chunk must have domain tags");
        }
    }
}
