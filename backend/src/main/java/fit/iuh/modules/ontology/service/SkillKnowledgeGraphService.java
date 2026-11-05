package fit.iuh.modules.ontology.service;

import fit.iuh.modules.ontology.dto.GraphMatchResult;

import java.util.List;

public interface SkillKnowledgeGraphService {

    GraphMatchResult matchSkills(String requiredSkill, String candidateEvidence);

    double calculateSimilarity(String requiredSkill, String candidateEvidence);

    List<String> getRelatedSkills(String skillName);
}
