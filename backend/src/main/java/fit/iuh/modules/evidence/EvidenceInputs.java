package fit.iuh.modules.evidence;

import com.fasterxml.jackson.databind.JsonNode;
import fit.iuh.modules.session.entity.Session;
import fit.iuh.modules.skillgap.client.SkillGapClient;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ResponseStatusException;

/** Resolves the C2 contract once, before the immutable interview snapshot is created. */
@Component @RequiredArgsConstructor
public class EvidenceInputs {
    private final SkillGapClient gaps;
    private final EvidenceJson json;

    public JsonNode skills(Session session) {
        if (session.getApplicationProfile() != null) {
            return json.read(session.getApplicationProfile().getSkillGapJson());
        }
        String cached = session.getSkillGapJson();
        if (cached != null && !cached.isBlank()) {
            JsonNode skills = json.read(cached);
            if (hasTaskContract(skills)) return skills;
        }
        if (session.getResume() == null || session.getJobDescription() == null) {
            throw new ResponseStatusException(HttpStatus.UNPROCESSABLE_ENTITY,
                    "CV and JD are required to prepare the evidence interview; clone with the original documents");
        }
        var result = gaps.analyzeGap(session.getId(), session.getResume().getRawText(), session.getJobDescription().getRawText());
        if (result == null || result.skills() == null || result.skills().isEmpty()) {
            throw new ResponseStatusException(HttpStatus.UNPROCESSABLE_ENTITY, "No JD skills available for interview");
        }
        return json.tree(result.skills());
    }

    public static boolean hasTaskContract(JsonNode skills) {
        if (!skills.isArray() || skills.isEmpty()) return false;
        for (JsonNode skill : skills) {
            if (!skill.path("job_tasks").isArray() || !skill.path("jd_evidence_spans").isArray()
                    || !skill.path("importance_weight").isNumber()) return false;
        }
        return true;
    }
}
