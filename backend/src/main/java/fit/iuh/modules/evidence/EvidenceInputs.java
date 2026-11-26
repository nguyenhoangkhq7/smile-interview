package fit.iuh.modules.evidence;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.JsonNodeFactory;
import com.fasterxml.jackson.databind.node.ObjectNode;
import fit.iuh.modules.session.entity.Session;
import fit.iuh.modules.skillgap.client.SkillGapClient;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;
import java.util.Objects;
import java.util.regex.Pattern;

/** Resolves the C2 contract once, before the immutable interview snapshot is created. */
@Component @RequiredArgsConstructor
public class EvidenceInputs {
    private static final List<String> INTERVIEW_FIELDS = List.of(
            "jd_skill_id", "required_proficiency", "importance_weight",
            "priority", "job_tasks", "cv_evidence_spans");
    private static final List<String> PERSONALIZATION_FIELDS = List.of(
            "jd_skill_name", "matched_cv_skill_name", "semantic_alignment", "context_job");
    private static final List<String> RETIRED_OBJECTIVE_FIELDS = List.of(
            "required_proficiency", "extension_criterion_ids", "inferred",
            "rubric_version", "rubric_fingerprint");
    private static final List<String> RETIRED_SUITABLE_MODE_FIELDS = List.of("rationale");
    private static final Pattern WHITESPACE = Pattern.compile("\\s+", Pattern.UNICODE_CHARACTER_CLASS);
    private static final Pattern WORDS = Pattern.compile("\\S+", Pattern.UNICODE_CHARACTER_CLASS);

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

    public JsonNode interviewSkills(JsonNode skills) {
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

    static ObjectNode verificationSources(Session session, JsonNode skills) {
        var profile = session.getApplicationProfile();
        var resume = session.getResume();
        var job = session.getJobDescription();
        var cv = DocumentText.from(profile != null ? profile.getCvText() : resume == null ? null : resume.getRawText());
        var jd = DocumentText.from(profile != null ? profile.getJdText() : job == null ? null : job.getRawText());
        var sources = JsonNodeFactory.instance.objectNode();
        var cvSources = sources.putObject("cv");
        var jdSources = sources.putObject("jd");
        for (JsonNode skill : skills) {
            addVerifiedSpans(cvSources, skill.path("cv_evidence_spans"), cv);
            addVerifiedSpans(jdSources, skill.path("jd_evidence_spans"), jd);
            for (JsonNode task : skill.path("job_tasks")) {
                addVerifiedSpans(jdSources, task.path("evidence_spans"), jd);
            }
        }
        return sources;
    }

    private static void addVerifiedSpans(ObjectNode result, JsonNode spans, DocumentText document) {
        for (JsonNode span : spans) {
            if (!span.isTextual() || result.has(span.textValue())) continue;
            var excerpt = document.excerpt(span.textValue());
            if (excerpt != null) result.put(span.textValue(), excerpt);
        }
    }

    private record DocumentText(String original, String collapsed, int[] offsets) {
        static DocumentText from(String text) {
            String original = Objects.requireNonNullElse(text, "");
            var collapsed = new StringBuilder(original.length());
            int[] offsets = new int[original.length()];
            var words = WORDS.matcher(original);
            while (words.find()) {
                if (!collapsed.isEmpty()) collapsed.append(' ');
                for (int index = words.start(); index < words.end(); index++) {
                    offsets[collapsed.length()] = index;
                    collapsed.append(original.charAt(index));
                }
            }
            return new DocumentText(original, collapsed.toString(), offsets);
        }

        String excerpt(String span) {
            String needle = WHITESPACE.matcher(span).replaceAll(" ").strip();
            if (needle.isEmpty()) return null;
            if (original.contains(span)) return span;
            int start = collapsed.indexOf(needle);
            if (start < 0) return null;
            return original.substring(offsets[start], offsets[start + needle.length() - 1] + 1);
        }
    }

    public JsonNode enrichPersonalization(JsonNode baseSkills, Session session) {
        if (!(baseSkills instanceof ArrayNode) || session == null) return baseSkills;
        String rawJson = session.getApplicationProfile() != null
                ? session.getApplicationProfile().getSkillGapJson()
                : session.getSkillGapJson();
        if (rawJson == null || rawJson.isBlank()) return baseSkills;
        return enrichPersonalization(baseSkills, json.read(rawJson));
    }

    public JsonNode enrichPersonalization(JsonNode baseSkills, JsonNode rawSkills) {
        if (!(baseSkills instanceof ArrayNode array) || rawSkills == null || !rawSkills.isArray()) {
            return baseSkills;
        }
        var bySkillId = new java.util.HashMap<String, JsonNode>();
        for (JsonNode raw : rawSkills) {
            String id = raw.path("jd_skill_id").asText("");
            if (!id.isEmpty()) bySkillId.put(id, raw);
        }
        ArrayNode copy = array.deepCopy();
        for (JsonNode item : copy) {
            if (!(item instanceof ObjectNode target)) continue;
            JsonNode raw = bySkillId.get(target.path("jd_skill_id").asText(""));
            if (raw == null) continue;
            for (String field : PERSONALIZATION_FIELDS) {
                if (raw.hasNonNull(field)) target.set(field, raw.get(field));
            }
        }
        return copy;
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
