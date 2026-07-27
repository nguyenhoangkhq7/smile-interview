package fit.iuh.modules.assessment.service.impl;

import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.modules.assessment.dto.ClassifiedCriteriaBundle;
import fit.iuh.modules.assessment.dto.ClassifiedCriteriaBundle.ClassifiedCriteria;
import fit.iuh.modules.assessment.dto.ClassifiedCriteriaBundle.JdExtraCriteria;
import fit.iuh.modules.assessment.service.JdCriteriaClassifierService;
import fit.iuh.modules.assessment.service.LlmCallerService;
import fit.iuh.modules.assessment.util.TextSanitizationUtil;
import fit.iuh.modules.rulengine.repository.JobCriteriaRepository.CriteriaWeightProjection;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.*;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class JdCriteriaClassifierServiceImpl implements JdCriteriaClassifierService {

    private final LlmCallerService llmCallerService;
    private final ObjectMapper objectMapper;

    private static final String SYSTEM_PROMPT_TEMPLATE = """
            Role: Job Description Criteria Classifier & Extractor.
            Task: Given a Job Description (JD), a seniority level, and a numbered list of evaluation criteria from the database, classify each criterion and extract any extra criteria from the JD not covered by the list.

            ===== CLASSIFICATION VALUES =====
            - "required"   : The JD explicitly or strongly implies this criterion as essential/must-have for this role and seniority.
            - "preferred"  : The JD mentions this as nice-to-have, bonus, or optional; OR the criterion is a foundational engineering skill
                             that any software developer is expected to have (OOP, Git, SQL, Testing, Clean Code, Agile) even if not
                             explicitly stated — use "preferred" as the safe default when in doubt.
            - "not_in_jd"  : Use ONLY for criteria that are COMPLETELY UNRELATED to the job domain.
                             This is a LAST RESORT option. Reserve it for cross-domain mismatches only.

            ===== CRITICAL RULE — CONSERVATIVE not_in_jd =====
            You MUST default to "preferred" (NOT "not_in_jd") unless the criterion is COMPLETELY outside the job domain.

            Examples of when NOT to use not_in_jd for a Fullstack Java/React JD:
            - OOP, Design Patterns, SOLID → "preferred" (foundational skill, always relevant)
            - Data Structures & Algorithms → "preferred" (universal CS skill)
            - Database Modeling & SQL → "required" or "preferred" (any fullstack role uses databases)
            - Git / Version Control → "preferred" (every developer uses Git)
            - Unit Testing → "preferred" (good engineering practice, implied by most JDs)
            - CI/CD Fundamentals → "preferred" (mentioned in most modern JDs)
            - Docker → "preferred" or "required" (JD must mention it for "required")
            - Agile / SDLC → "preferred" (standard team practice)
            - HTML & CSS → "preferred" (part of fullstack)
            - Technical Documentation → "preferred" (general engineering skill)

            Examples of VALID not_in_jd (cross-domain mismatch):
            - "Machine Learning / AI Model Training" for a Fullstack CRUD app JD → not_in_jd
            - "Embedded Systems / RTOS" for a web backend JD → not_in_jd
            - "Native Mobile iOS/Android" for a pure web Fullstack JD → not_in_jd
            - "Data Pipeline Engineering (Spark/Kafka)" for a small-team web JD → not_in_jd

            ===== SENIORITY-AWARE RULES =====
            Candidate seniority level: %s
            - INTERN / FRESHER: Heavy DevOps/Cloud (Auto Scaling, Lambda, VPC, Kubernetes, advanced IAM)
              → classify as "preferred" (NOT "required") unless JD explicitly mandates it for fresher applicants.
            - JUNIOR: CI/CD and basic Docker can be "required" if the JD mentions them.
              Advanced cloud architecture (EKS, ECS, Auto Scaling) → "preferred".
            - MID / SENIOR / LEAD: apply standard classification.

            ===== JD EXTRAS RULES =====
            Extract additional skills/requirements explicitly stated in the JD that are NOT covered by any database criterion.
            For each extra provide:
            - "name": concise English or Vietnamese name
            - "importance": "required" or "preferred" based on JD context and seniority rules
            - "prompt_instruction": 1 concise English sentence describing how to evaluate this skill from the CV

            ===== OUTPUT FORMAT (STRICT JSON ONLY — no markdown, no commentary) =====
            {
              "classified": [
                {
                  "criteria_id": <long — exact ID from the numbered list>,
                  "importance": "<required|preferred|not_in_jd>"
                }
              ],
              "jd_extras": [
                {
                  "name": "<string>",
                  "importance": "<required|preferred>",
                  "prompt_instruction": "<string>"
                }
              ]
            }
            """;


    /**
     * Set of criteria names (lowercase substrings) that should never be classified
     * as 'required' for junior seniority levels (INTERN / FRESHER).
     * These are advanced DevOps/Cloud topics that require significant hands-on experience.
     */
    private static final Set<String> HEAVY_DEVOPS_CRITERIA_KEYWORDS = Set.of(
            "auto-scaling", "auto scaling", "autoscaling",
            "lambda", "serverless",
            "kubernetes", "k8s", "eks", "ecs",
            "vpc", "vpc & networking", "vpc networking",
            "iam & security", "aws iam",
            "cost optimization",
            "linux administration", "shell scripting"
    );

    /** Maximum number of criteria per classifier LLM call to prevent context overload. */
    private static final int MAX_CLASSIFIER_BATCH_SIZE = 15;

    @Override
    public ClassifiedCriteriaBundle classify(String jdMarkdown, List<CriteriaWeightProjection> dbCriteria, String seniorityLevel) {
        if (dbCriteria == null || dbCriteria.isEmpty()) {
            return new ClassifiedCriteriaBundle(List.of(), List.of());
        }
        if (jdMarkdown == null || jdMarkdown.isBlank()) {
            List<ClassifiedCriteria> fallbackList = dbCriteria.stream()
                    .map(c -> new ClassifiedCriteria(c.getCriteriaId(), c.getCriteriaName(), c.getPromptInstruction(), c.getWeightPercentage(), "preferred"))
                    .collect(Collectors.toList());
            return new ClassifiedCriteriaBundle(fallbackList, List.of());
        }

        boolean isJuniorOrBelow = seniorityLevel != null &&
                ("INTERN".equalsIgnoreCase(seniorityLevel) || "FRESHER".equalsIgnoreCase(seniorityLevel) ||
                 "JUNIOR".equalsIgnoreCase(seniorityLevel));
        boolean isFresherOrBelow = seniorityLevel != null &&
                ("INTERN".equalsIgnoreCase(seniorityLevel) || "FRESHER".equalsIgnoreCase(seniorityLevel));

        String effectiveSeniorityLabel = seniorityLevel != null ? seniorityLevel.toUpperCase(Locale.ROOT) : "UNSPECIFIED";
        String systemPrompt = String.format(SYSTEM_PROMPT_TEMPLATE, effectiveSeniorityLabel);

        // ── Partition criteria into batches ──────────────────────────────────────
        List<List<CriteriaWeightProjection>> batches = partitionList(dbCriteria, MAX_CLASSIFIER_BATCH_SIZE);
        int totalBatches = batches.size();
        log.info("[JdCriteriaClassifier] Classifying {} criteria in {} batch(es) of max {} (seniority={})",
                dbCriteria.size(), totalBatches, MAX_CLASSIFIER_BATCH_SIZE, effectiveSeniorityLabel);

        // Merged results across all batches
        Map<Long, String> importanceMap = new HashMap<>();
        // Use LinkedHashMap keyed by normalised name to deduplicate jd_extras across batches
        Map<String, JdExtraCriteria> extrasMap = new LinkedHashMap<>();

        // Build a full set of all DB criteria names (lowercase) to prevent LLM from re-extracting
        // as jd_extras any criteria that are already tracked in the database.
        Set<String> allDbCriteriaNames = dbCriteria.stream()
                .map(c -> c.getCriteriaName().toLowerCase(Locale.ROOT).trim())
                .collect(Collectors.toSet());

        // Concise name hint to include in the batch-1 prompt so LLM is aware of all DB criteria.
        String allDbNamesHint = dbCriteria.stream()
                .map(CriteriaWeightProjection::getCriteriaName)
                .collect(Collectors.joining("; "));

        for (int batchIndex = 0; batchIndex < totalBatches; batchIndex++) {
            List<CriteriaWeightProjection> batch = batches.get(batchIndex);
            int maxBatchRetries = 2;
            boolean batchSuccess = false;
            for (int attempt = 1; attempt <= maxBatchRetries; attempt++) {
                try {
                    callClassifierBatch(systemPrompt, jdMarkdown, batch, batchIndex + 1, totalBatches,
                            importanceMap, extrasMap, allDbNamesHint);
                    batchSuccess = true;
                    break;
                } catch (Exception e) {
                    if (attempt < maxBatchRetries) {
                        log.warn("[JdCriteriaClassifier] Batch {}/{} attempt {}/{} failed ({}). Retrying...",
                                batchIndex + 1, totalBatches, attempt, maxBatchRetries, e.getMessage());
                    } else {
                        log.warn("[JdCriteriaClassifier] Batch {}/{} failed after {} attempts ({}). Defaulting batch criteria to 'preferred'.",
                                batchIndex + 1, totalBatches, maxBatchRetries, e.getMessage());
                    }
                }
            }
            if (!batchSuccess) {
                // Safe fallback: mark entire failed batch as preferred so nothing gets dropped
                for (CriteriaWeightProjection c : batch) {
                    importanceMap.putIfAbsent(c.getCriteriaId(), "preferred");
                }
            }
        }

        // Post-processing: remove jd_extras whose name duplicates an existing DB criterion.
        // This is the hard-enforcement guard — the LLM hint above is the soft guard.
        int extrasBefore = extrasMap.size();
        extrasMap.entrySet().removeIf(entry -> isAdHocDuplicateOfDbCriteria(entry.getKey(), allDbCriteriaNames));
        if (extrasMap.size() < extrasBefore) {
            log.info("[JdCriteriaClassifier] Removed {} jd_extras duplicating existing DB criteria (kept {}).",
                    extrasBefore - extrasMap.size(), extrasMap.size());
        }

        // ── Build final classified list with post-processing ─────────────────────
        List<ClassifiedCriteria> classifiedList = new ArrayList<>();
        for (CriteriaWeightProjection c : dbCriteria) {
            // Default to "preferred" (not "required") when LLM didn't classify a criteria.
            // This is safer than "required" — unknown criteria are treated as optional,
            // preventing irrelevant criteria from inflating the must-have score.
            String imp = importanceMap.getOrDefault(c.getCriteriaId(), "preferred");

            // Post-process: downgrade heavy DevOps criteria for junior candidates.
            if ("required".equals(imp) && isFresherOrBelow) {
                String nameLower = c.getCriteriaName().toLowerCase(Locale.ROOT);
                boolean isHeavyDevOps = HEAVY_DEVOPS_CRITERIA_KEYWORDS.stream()
                        .anyMatch(nameLower::contains);
                if (isHeavyDevOps) {
                    log.info("[JdCriteriaClassifier] Downgrading '{}' from required → preferred (heavy DevOps, seniority={})",
                            c.getCriteriaName(), seniorityLevel);
                    imp = "preferred";
                }
            }

            // For JUNIOR level, also downgrade advanced cloud architecture
            if ("required".equals(imp) && isJuniorOrBelow) {
                String nameLower = c.getCriteriaName().toLowerCase(Locale.ROOT);
                if (nameLower.contains("auto-scal") || nameLower.contains("auto scal") ||
                    nameLower.contains("serverless") || nameLower.contains("kubernetes")) {
                    log.info("[JdCriteriaClassifier] Downgrading '{}' from required → preferred (advanced cloud, seniority={})",
                            c.getCriteriaName(), seniorityLevel);
                    imp = "preferred";
                }
            }

            classifiedList.add(new ClassifiedCriteria(
                    c.getCriteriaId(),
                    c.getCriteriaName(),
                    c.getPromptInstruction(),
                    c.getWeightPercentage(),
                    imp
            ));
        }

        List<JdExtraCriteria> extrasList = new ArrayList<>(extrasMap.values());
        log.info("[JdCriteriaClassifier] Done: {} classified, {} jd_extras extracted",
                classifiedList.size(), extrasList.size());
        return new ClassifiedCriteriaBundle(classifiedList, extrasList);
    }

    /**
     * Calls the LLM classifier for a single batch of criteria.
     * Merges results into the provided {@code importanceMap} and {@code extrasMap}.
     */
    private void callClassifierBatch(
            String systemPrompt,
            String jdMarkdown,
            List<CriteriaWeightProjection> batch,
            int batchNum,
            int totalBatches,
            Map<Long, String> importanceMap,
            Map<String, JdExtraCriteria> extrasMap,
            String allDbNamesHint) {

        StringBuilder criteriaListText = new StringBuilder();
        for (CriteriaWeightProjection c : batch) {
            criteriaListText.append(c.getCriteriaId()).append(". ")
                    .append(c.getCriteriaName()).append(": ")
                    .append(c.getPromptInstruction() != null ? c.getPromptInstruction() : "")
                    .append("\n");
        }

        // Only ask for jd_extras in the first batch to avoid duplicates.
        // Subsequent batches only classify; extras from batch 1 cover the full JD.
        // The allDbNamesHint gives LLM awareness of ALL database criteria (across all batches)
        // so it does not re-extract skills already tracked in the database.
        String extrasNote = (batchNum == 1)
                ? ("Classify each criterion AND extract JD extras for skills in the JD that are "
                        + "NOT already covered by the complete database (all batches combined): ["
                        + allDbNamesHint + "]. "
                        + "Do NOT extract extras with the same or similar meaning as any name in that list. "
                        + "jd_extras importance must be \"required\" or \"preferred\" only.")
                : "Classify each criterion ONLY. Set jd_extras to an empty array [].";

        String userPrompt = """
                ====== JOB DESCRIPTION ======
                %s

                ====== DATABASE CRITERIA LIST (batch %d/%d) ======
                %s

                %s Output STRICT JSON ONLY.
                """.formatted(jdMarkdown, batchNum, totalBatches, criteriaListText.toString(), extrasNote);

        log.debug("[JdCriteriaClassifier] Batch {}/{}: calling LLM with {} criteria", batchNum, totalBatches, batch.size());
        String rawLlmResponse = llmCallerService.callLlmBlocking(systemPrompt, userPrompt);
        String jsonContent = TextSanitizationUtil.extractCleanJson(rawLlmResponse);

        try {
            Map<?, ?> parsed = objectMapper.readValue(jsonContent, Map.class);

            if (parsed.containsKey("classified") && parsed.get("classified") instanceof List<?> list) {
                for (Object item : list) {
                    if (item instanceof Map<?, ?> map) {
                        Object idObj = map.get("criteria_id");
                        Object impObj = map.get("importance");
                        if (idObj != null && impObj != null) {
                            try {
                                Long id = Long.valueOf(idObj.toString());
                                String imp = impObj.toString().toLowerCase(Locale.ROOT);
                                importanceMap.put(id, imp);
                            } catch (NumberFormatException ignored) {
                                log.warn("[JdCriteriaClassifier] Batch {}/{}: invalid criteria_id '{}'", batchNum, totalBatches, idObj);
                            }
                        }
                    }
                }
            }

            if (parsed.containsKey("jd_extras") && parsed.get("jd_extras") instanceof List<?> list) {
                for (Object item : list) {
                    if (item instanceof Map<?, ?> map) {
                        Object nameObj = map.get("name");
                        Object impObj = map.get("importance");
                        Object instructionObj = map.get("prompt_instruction");
                        if (nameObj != null && !nameObj.toString().isBlank()) {
                            String name = nameObj.toString().trim();
                            String imp = impObj != null ? impObj.toString().toLowerCase(Locale.ROOT) : "preferred";
                            String instruction = instructionObj != null ? instructionObj.toString().trim() : "Evaluate experience in " + name;
                            // Deduplicate by lowercase name
                            extrasMap.putIfAbsent(name.toLowerCase(Locale.ROOT), new JdExtraCriteria(name, imp, instruction));
                        }
                    }
                }
            }
        } catch (Exception e) {
            // Propagate so the caller's retry loop can attempt again before falling back to 'preferred'.
            throw new RuntimeException("[JdCriteriaClassifier] Failed to parse classifier JSON for batch " + batchNum + "/" + totalBatches + ": " + e.getMessage(), e);
        }
    }

    /**
     * Partitions a list into sub-lists of at most {@code batchSize} elements.
     */
    private static <T> List<List<T>> partitionList(List<T> list, int batchSize) {
        List<List<T>> partitions = new ArrayList<>();
        for (int i = 0; i < list.size(); i += batchSize) {
            partitions.add(list.subList(i, Math.min(i + batchSize, list.size())));
        }
        return partitions;
    }

    /**
     * Returns true if the ad-hoc extra name (already lowercase-trimmed) duplicates
     * an existing DB criterion. Uses exact match and meaningful substring overlap.
     * This prevents jd_extras from re-extracting criteria already tracked in the database.
     */
    private boolean isAdHocDuplicateOfDbCriteria(String adHocNameLower, Set<String> dbNameSet) {
        for (String dbName : dbNameSet) {
            if (dbName.equals(adHocNameLower)) return true;
            // Substring overlap of >= 5 chars is considered a duplicate
            if ((dbName.contains(adHocNameLower) || adHocNameLower.contains(dbName))
                    && Math.min(dbName.length(), adHocNameLower.length()) >= 5) {
                return true;
            }
        }
        return false;
    }
}
