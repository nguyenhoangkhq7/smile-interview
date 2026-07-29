package fit.iuh.modules.ontology.service;

import fit.iuh.modules.ontology.dto.GraphMatchResult;
import fit.iuh.modules.ontology.dto.SkillRelationDto;
import fit.iuh.modules.ontology.repository.SkillOntologyRepository;
import fit.iuh.modules.ontology.service.impl.SkillKnowledgeGraphServiceImpl;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;
import org.springframework.core.io.ResourceLoader;

import java.util.List;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.when;

class SkillKnowledgeGraphServiceTest {

    private SkillOntologyRepository ontologyRepository;
    private SkillKnowledgeGraphService graphService;

    @BeforeEach
    void setUp() {
        ontologyRepository = new SkillOntologyRepository(Mockito.mock(ResourceLoader.class), Mockito.mock(com.fasterxml.jackson.databind.ObjectMapper.class));

        // Manually seed sample relations
        ontologyRepository.addRelation(new SkillRelationDto("React", "Frontend Framework", "IS_A", 0.95));
        ontologyRepository.addRelation(new SkillRelationDto("React.js", "React", "EQUIVALENT_TO", 1.00));
        ontologyRepository.addRelation(new SkillRelationDto("Next.js", "React", "REQUIRES", 0.90));
        ontologyRepository.addRelation(new SkillRelationDto("PostgreSQL", "Relational Database", "IS_A", 0.95));

        graphService = new SkillKnowledgeGraphServiceImpl(ontologyRepository);
    }

    @Test
    @DisplayName("Should return 1.0 score for direct text match")
    void testDirectMatch() {
        GraphMatchResult result = graphService.matchSkills("React", "Candidate has extensive experience with React in production.");
        assertEquals(1.0, result.similarityScore(), 0.001);
        assertEquals("MATCHED", result.matchStatus());
        assertEquals("Direct Text Match", result.relationPath());
    }

    @Test
    @DisplayName("Should deduce IS_A relationship correctly: React satisfies Frontend Framework")
    void testHierarchicalMatch() {
        GraphMatchResult result = graphService.matchSkills("Frontend Framework", "Candidate built UI components using React.js.");
        assertTrue(result.similarityScore() >= 0.90, "Expected similarity score >= 0.90");
        assertEquals("MATCHED", result.matchStatus());
        assertTrue(result.relationPath().contains("IS_A"), "Path should contain IS_A relation");
    }

    @Test
    @DisplayName("Should deduce dependency REQUIRES relationship correctly: Next.js implies React")
    void testDependencyMatch() {
        GraphMatchResult result = graphService.matchSkills("React", "Candidate developed web applications with Next.js.");
        assertTrue(result.similarityScore() >= 0.85, "Expected similarity score >= 0.85");
        assertEquals("MATCHED", result.matchStatus());
    }

    @Test
    @DisplayName("Should return 0.0 score for completely unrelated skills")
    void testUnrelatedSkills() {
        GraphMatchResult result = graphService.matchSkills("Relational Database", "Candidate has experience with React.");
        assertEquals(0.0, result.similarityScore(), 0.001);
        assertEquals("MISSING", result.matchStatus());
    }

    @Test
    @DisplayName("Should return related outgoing skills")
    void testGetRelatedSkills() {
        List<String> related = graphService.getRelatedSkills("React");
        assertNotNull(related);
        assertTrue(related.contains("Frontend Framework"));
    }
}
