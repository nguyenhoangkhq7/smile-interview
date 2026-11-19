package fit.iuh.modules.evidence;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import fit.iuh.modules.session.entity.Session;
import fit.iuh.modules.skillgap.client.SkillGapClient;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;

/** Resolves the C2 contract once, before the immutable interview snapshot is created. */
@Component @RequiredArgsConstructor
public class EvidenceInputs {
    private static final List<String> INTERVIEW_FIELDS = List.of(
            "jd_skill_id", "required_proficiency", "importance_weight",
            "priority", "job_tasks", "cv_evidence_spans");
    private static final List<String> RETIRED_OBJECTIVE_FIELDS = List.of(
            "required_proficiency", "extension_criterion_ids", "inferred",
            "rubric_version", "rubric_fingerprint");
    private static final List<String> RETIRED_SUITABLE_MODE_FIELDS = List.of("rationale");

    private final SkillGapClient gaps;
    private final EvidenceJson json;

    public JsonNode skills(Session session) {
        if (session.getApplicationProfile() != null) {
            return interviewSkills(json.read(session.getApplicationProfile().getSkillGapJson()));
        }
        String cached = session.getSkillGapJson();
        if (cached != null && !cached.isBlank()) {
            JsonNode skills = json.read(cached);
            if (hasTaskContract(skills)) return interviewSkills(skills);
        }
        if (session.getResume() == null || session.getJobDescription() == null) {
            throw new ResponseStatusException(HttpStatus.UNPROCESSABLE_ENTITY,
                    "CV and JD are required to prepare the evidence interview; clone with the original documents");
        }
        var result = gaps.analyzeGap(session.getId(), session.getResume().getRawText(), session.getJobDescription().getRawText());
        if (result == null || result.skills() == null || result.skills().isEmpty()) {
            throw new ResponseStatusException(HttpStatus.UNPROCESSABLE_ENTITY, "No JD skills available for interview");
        }
        return interviewSkills(json.tree(result.skills()));
    }

    private JsonNode interviewSkills(JsonNode skills) {
        var result = (ArrayNode) json.read("[]");
        for (JsonNode skill : skills) {
            var selected = result.addObject();
            for (String field : INTERVIEW_FIELDS) {
                if (skill.hasNonNull(field)) selected.set(field, skill.get(field));
            }
            var legacySpans = skill.path("jd_evidence_spans");
            if (skill.path("job_tasks").isEmpty() && legacySpans.isArray() && !legacySpans.isEmpty()) {
                selected.set("jd_evidence_spans", legacySpans);
            }
        }
        return result;
    }

    public static JsonNode leanBlueprint(JsonNode blueprint) {
        if (!(blueprint instanceof ObjectNode root)) return blueprint;
        ObjectNode normalized = root.deepCopy();
        JsonNode objectives = normalized.path("objectives");
        if (!objectives.isArray()) return normalized;
        for (JsonNode objective : objectives) {
            if (objective instanceof ObjectNode obj) stripRetiredObjectiveFields(obj);
        }
        return normalized;
    }

    private static void stripRetiredObjectiveFields(ObjectNode objective) {
        RETIRED_OBJECTIVE_FIELDS.forEach(objective::remove);
        JsonNode modes = objective.path("suitable_modes");
        if (!modes.isArray()) return;
        for (JsonNode mode : modes) {
            if (mode instanceof ObjectNode modeObj) RETIRED_SUITABLE_MODE_FIELDS.forEach(modeObj::remove);
        }
    }

    public static boolean hasTaskContract(JsonNode skills) {
        if (!skills.isArray() || skills.isEmpty()) return false;
        for (JsonNode skill : skills) {
            if (!skill.path("job_tasks").isArray()
                    || (skill.hasNonNull("jd_evidence_spans") && !skill.get("jd_evidence_spans").isArray())
                    || !skill.path("importance_weight").isNumber()) return false;
        }
        return true;
    }
}
