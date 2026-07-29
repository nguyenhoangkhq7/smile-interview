package fit.iuh.modules.ontology.service.impl;

import fit.iuh.modules.ontology.dto.GraphMatchResult;
import fit.iuh.modules.ontology.dto.SkillRelationDto;
import fit.iuh.modules.ontology.repository.SkillOntologyRepository;
import fit.iuh.modules.ontology.service.SkillKnowledgeGraphService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.*;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

@Slf4j
@Service
@RequiredArgsConstructor
public class SkillKnowledgeGraphServiceImpl implements SkillKnowledgeGraphService {

    private static final int MAX_BFS_DEPTH = 3;
    private final SkillOntologyRepository ontologyRepository;

    @Override
    public GraphMatchResult matchSkills(String requiredSkill, String candidateEvidence) {
        if (requiredSkill == null || requiredSkill.isBlank() || candidateEvidence == null || candidateEvidence.isBlank()) {
            return new GraphMatchResult(requiredSkill, candidateEvidence, null, 0.0, "MISSING", "None", "No input text provided.");
        }

        String reqClean = requiredSkill.trim();

        // 1. Direct String Match / Token Match Check
        if (containsIgnoreCase(candidateEvidence, reqClean)) {
            return new GraphMatchResult(
                    reqClean,
                    candidateEvidence,
                    reqClean,
                    1.0,
                    "MATCHED",
                    "Direct Text Match",
                    "Exact skill term '" + reqClean + "' found directly in candidate evidence."
            );
        }

        // 2. Extract known ontology skill nodes present in candidate evidence
        List<String> candidateTokens = extractOntologySkillsFromText(candidateEvidence);

        double bestScore = 0.0;
        String bestMatchedSkill = null;
        String bestPath = "None";
        String bestExplanation = "No semantic link found on Skill Knowledge Graph.";

        // 3. BFS Traversal for each candidate skill token
        for (String candToken : candidateTokens) {
            BfsSearchResult searchResult = bfsGraphSearch(candToken, reqClean);
            if (searchResult.score > bestScore) {
                bestScore = searchResult.score;
                bestMatchedSkill = candToken;
                bestPath = searchResult.path;
                bestExplanation = String.format("Ontology path: %s (Weight: %.2f)", searchResult.path, searchResult.score);
            }
        }

        String status;
        if (bestScore >= 0.85) {
            status = "MATCHED";
        } else if (bestScore >= 0.40) {
            status = "WEAK";
        } else {
            status = "MISSING";
        }

        log.debug("[OntologyGraph] Requirement='{}' vs Evidence='{}' -> BestMatch='{}', Score={}, Path='{}'",
                reqClean, candidateEvidence, bestMatchedSkill, String.format("%.2f", bestScore), bestPath);

        return new GraphMatchResult(reqClean, candidateEvidence, bestMatchedSkill, bestScore, status, bestPath, bestExplanation);
    }

    @Override
    public double calculateSimilarity(String requiredSkill, String candidateEvidence) {
        return matchSkills(requiredSkill, candidateEvidence).similarityScore();
    }

    @Override
    public List<String> getRelatedSkills(String skillName) {
        if (skillName == null || skillName.isBlank()) return Collections.emptyList();

        Set<String> related = new LinkedHashSet<>();
        List<SkillRelationDto> edges = ontologyRepository.getOutgoingEdges(skillName);
        for (SkillRelationDto edge : edges) {
            related.add(edge.target());
        }
        return new ArrayList<>(related);
    }

    private List<String> extractOntologySkillsFromText(String text) {
        Set<String> found = new LinkedHashSet<>();
        Set<String> allNodes = ontologyRepository.getAllSkillNodes();

        for (String node : allNodes) {
            if (containsIgnoreCase(text, node)) {
                found.add(node);
            }
        }
        return new ArrayList<>(found);
    }

    private boolean containsIgnoreCase(String haystack, String needle) {
        if (haystack == null || needle == null) return false;
        String patternString = "(?i)\\b" + Pattern.quote(needle) + "\\b";
        Pattern pattern = Pattern.compile(patternString);
        return pattern.matcher(haystack).find();
    }

    private record BfsSearchResult(double score, String path) {}

    private BfsSearchResult bfsGraphSearch(String startSkill, String targetSkill) {
        String startLower = startSkill.trim().toLowerCase();
        String targetLower = targetSkill.trim().toLowerCase();

        if (startLower.equals(targetLower)) {
            return new BfsSearchResult(1.0, startSkill + " == " + targetSkill);
        }

        // Queue storing BfsNode (currentSkill, cumulativeScore, depth, pathHistory)
        Queue<BfsNode> queue = new LinkedList<>();
        Set<String> visited = new HashSet<>();

        queue.add(new BfsNode(startSkill, 1.0, 0, startSkill));
        visited.add(startLower);

        double maxScoreFound = 0.0;
        String bestPathFound = "None";

        while (!queue.isEmpty()) {
            BfsNode current = queue.poll();

            if (current.depth >= MAX_BFS_DEPTH) continue;

            List<SkillRelationDto> outgoing = ontologyRepository.getOutgoingEdges(current.skillName);
            for (SkillRelationDto edge : outgoing) {
                String nextNode = edge.target();
                String nextLower = nextNode.toLowerCase();
                double nextScore = current.cumulativeScore * edge.weight();
                String nextPath = current.pathHistory + " -[" + edge.relation() + "]-> " + nextNode;

                if (nextLower.equalsIgnoreCase(targetLower)) {
                    if (nextScore > maxScoreFound) {
                        maxScoreFound = nextScore;
                        bestPathFound = nextPath;
                    }
                }

                if (!visited.contains(nextLower)) {
                    visited.add(nextLower);
                    queue.add(new BfsNode(nextNode, nextScore, current.depth + 1, nextPath));
                }
            }
        }

        return new BfsSearchResult(maxScoreFound, bestPathFound);
    }

    private record BfsNode(String skillName, double cumulativeScore, int depth, String pathHistory) {}
}
