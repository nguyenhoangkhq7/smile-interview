package fit.iuh.modules.ontology.repository;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.modules.ontology.dto.SkillRelationDto;
import jakarta.annotation.PostConstruct;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.io.Resource;
import org.springframework.core.io.ResourceLoader;
import org.springframework.stereotype.Repository;

import java.io.InputStream;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

@Slf4j
@Repository
@RequiredArgsConstructor
public class SkillOntologyRepository {

    private final ResourceLoader resourceLoader;
    private final ObjectMapper objectMapper;

    // Adjacency List: SourceSkill (lowercase) -> List of outgoing edges
    private final Map<String, List<SkillRelationDto>> graph = new ConcurrentHashMap<>();
    private final Set<String> allSkillNodes = ConcurrentHashMap.newKeySet();

    @PostConstruct
    public void initGraph() {
        try {
            Resource resource = resourceLoader.getResource("classpath:ontology/skill_graph.json");
            if (resource.exists()) {
                try (InputStream inputStream = resource.getInputStream()) {
                    List<SkillRelationDto> relations = objectMapper.readValue(
                            inputStream, new TypeReference<List<SkillRelationDto>>() {}
                    );
                    for (SkillRelationDto rel : relations) {
                        addRelation(rel);
                    }
                    log.info("[OntologyRepo] Loaded {} skill ontology relations into graph (total {} unique skill nodes).",
                            relations.size(), allSkillNodes.size());
                }
            } else {
                log.warn("[OntologyRepo] skill_graph.json not found on classpath — initializing empty ontology graph.");
            }
        } catch (Exception e) {
            log.error("[OntologyRepo] Failed to load skill_graph.json: {}", e.getMessage(), e);
        }
    }

    public void addRelation(SkillRelationDto rel) {
        if (rel == null || rel.source() == null || rel.target() == null) return;

        String srcLower = rel.source().trim().toLowerCase();
        String tgtLower = rel.target().trim().toLowerCase();

        allSkillNodes.add(rel.source().trim());
        allSkillNodes.add(rel.target().trim());

        graph.computeIfAbsent(srcLower, k -> new ArrayList<>()).add(rel);

        // For EQUIVALENT_TO relations, automatically add reverse edge for bi-directional lookup
        if ("EQUIVALENT_TO".equalsIgnoreCase(rel.relation())) {
            SkillRelationDto reverseRel = new SkillRelationDto(rel.target(), rel.source(), "EQUIVALENT_TO", rel.weight());
            graph.computeIfAbsent(tgtLower, k -> new ArrayList<>()).add(reverseRel);
        }
    }

    public List<SkillRelationDto> getOutgoingEdges(String skillName) {
        if (skillName == null) return Collections.emptyList();
        return graph.getOrDefault(skillName.trim().toLowerCase(), Collections.emptyList());
    }

    public Map<String, List<SkillRelationDto>> getFullGraph() {
        return Collections.unmodifiableMap(graph);
    }

    public Set<String> getAllSkillNodes() {
        return Collections.unmodifiableSet(allSkillNodes);
    }
}
