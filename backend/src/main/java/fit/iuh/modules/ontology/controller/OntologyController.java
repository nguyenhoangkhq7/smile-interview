package fit.iuh.modules.ontology.controller;

import fit.iuh.modules.ontology.dto.GraphMatchResult;
import fit.iuh.modules.ontology.dto.SkillRelationDto;
import fit.iuh.modules.ontology.repository.SkillOntologyRepository;
import fit.iuh.modules.ontology.service.SkillKnowledgeGraphService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;
import java.util.Set;

@RestController
@RequestMapping("/api/v1/ontology")
@RequiredArgsConstructor
public class OntologyController {

    private final SkillKnowledgeGraphService graphService;
    private final SkillOntologyRepository ontologyRepository;

    @GetMapping("/match")
    public ResponseEntity<GraphMatchResult> matchSkills(
            @RequestParam("required") String requiredSkill,
            @RequestParam("candidate") String candidateEvidence) {
        GraphMatchResult result = graphService.matchSkills(requiredSkill, candidateEvidence);
        return ResponseEntity.ok(result);
    }

    @GetMapping("/graph")
    public ResponseEntity<Map<String, List<SkillRelationDto>>> getFullGraph() {
        return ResponseEntity.ok(ontologyRepository.getFullGraph());
    }

    @GetMapping("/nodes")
    public ResponseEntity<Set<String>> getAllNodes() {
        return ResponseEntity.ok(ontologyRepository.getAllSkillNodes());
    }

    @PostMapping("/relation")
    public ResponseEntity<String> addRelation(@RequestBody SkillRelationDto relation) {
        ontologyRepository.addRelation(relation);
        return ResponseEntity.ok("Relation added successfully: " + relation.source() + " -> " + relation.target());
    }
}
