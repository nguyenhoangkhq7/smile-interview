package fit.iuh.modules.assessment.prompt;

public final class AssessmentPrompts {

    private AssessmentPrompts() {
        throw new UnsupportedOperationException("AssessmentPrompts is a utility class");
    }

    public static final String SYSTEM_PROMPT_PRE_FILTER_CRITERIA =
            """
            Role: IT Job Criteria Pre-Filter.
            Task: Return matched database criteria IDs for the Job Description (JD).
            STRICT JSON OUTPUT: {"matched_ids": [<long>]}
            RULES:
            1. Include framework/architecture criteria for explicitly required tech (e.g., Spring Boot -> Backend Frameworks).
            2. Include quality principles (SOLID, Design Patterns) for "Clean Code"/"Maintainable Code".
            3. Output ONLY JSON with "matched_ids".
            """;

    public static final String SYSTEM_PROMPT_CONSOLIDATED_JD_PREPARATION =
            """
            Role: Job Description Parser & Criteria Classifier.
            Task: Analyze JD and numbered DB criteria list in a SINGLE pass.
            STRICT JSON OUTPUT:
            {
              "category": "<BACKEND|FRONTEND|FULLSTACK|DEVOPS|DATA_ENGINEERING|AI_ML|MOBILE|SECURITY|QA_TESTING|OTHER>",
              "level": "<INTERN|FRESHER|JUNIOR|MID|SENIOR|LEAD>",
              "gate_requirements": [{"criteria_name": "<YOE|Education|GPA|Certification>", "importance": "<REQUIRED|PREFERRED>", "required_value": "<English text>"}],
              "classified": [{"criteria_id": <long>, "importance": "<required|preferred|not_in_jd>"}],
              "jd_extras": [{"name": "<skill>", "importance": "<required|preferred>", "prompt_instruction": "<English sentence>"}]
            }
            RULES:
            1. CATEGORY: BACKEND (APIs/Java/Go/Node), FRONTEND (React/Vue/CSS), FULLSTACK (both), DEVOPS (CI/CD/Docker/K8s), DATA_ENGINEERING (ETL/Spark/Pipelines), AI_ML (ML/LLM/Models), MOBILE (iOS/Android/Flutter), SECURITY (SAST/DAST), QA_TESTING (Automation/QA), OTHER.
            2. LEVEL: Check title/first 10 lines. INTERN (0 exp/student), FRESHER (0-1 yr/fresh grad), JUNIOR (1-2 yrs), MID (2-5 yrs), SENIOR (5-8 yrs), LEAD (8+ yrs/Lead/Architect).
            3. GATES: Extract YOE, Education, GPA, Certifications explicitly in JD. Return [] if none.
            4. CLASSIFIED: 'required' (mandatory), 'preferred' (nice-to-have), 'not_in_jd' (absent). For INTERN/FRESHER, heavy DevOps/Cloud = 'preferred'.
            5. EXTRA SKILLS: List unique JD skills NOT in DB criteria list.
            """;

    public static String buildConsolidatedJdPreparationPrompt(String jdMarkdown, String numberedCriteriaList) {
        return """
                ====== DATABASE CRITERIA LIST ======
                %s

                ====== JOB DESCRIPTION ======
                %s

                Perform consolidated analysis. Output STRICT JSON ONLY matching schema.
                """.formatted(numberedCriteriaList != null ? numberedCriteriaList : "None", jdMarkdown != null ? jdMarkdown : "");
    }

    public static final String SYSTEM_PROMPT_GATE_EXTRACTION =
            """
            Role: IT JD Gate Evaluator.
            Task: Extract GATE requirements from JD and evaluate against candidate CV.
            STRICT JSON OUTPUT:
            {
              "gate_requirements": [
                {"criteria_name": "<YOE|Education|GPA|Certification>", "importance": "<REQUIRED|PREFERRED>", "required_value": "<English>", "actual_value": "<English>", "status": "<met|not_met>"}
              ]
            }
            RULES:
            1. Only YOE, Education, GPA, Certifications. Do NOT invent missing thresholds.
            2. Differentiate REQUIRED vs PREFERRED.
            3. All text fields in English. Output STRICT JSON ONLY.
            """;

    public static final String SYSTEM_PROMPT_METADATA_EXTRACTION =
            """
            Role: IT Job Classifier.
            Task: Extract category and level from Job Description (first 10 lines priority).
            STRICT JSON OUTPUT:
            {
              "category": "<BACKEND|FRONTEND|FULLSTACK|DEVOPS|DATA_ENGINEERING|AI_ML|MOBILE|SECURITY|QA_TESTING|OTHER>",
              "level": "<INTERN|FRESHER|JUNIOR|MID|SENIOR|LEAD>"
            }
            """;

    public static final String SYSTEM_PROMPT_CRITERIA_CLASSIFICATION =
            """
            Role: JD Criteria Classifier & Extra Skill Extractor.
            STRICT JSON OUTPUT:
            {
              "classified": [{"criteria_id": <long>, "importance": "<required|preferred|not_in_jd>"}],
              "jd_extras": [{"name": "<skill>", "importance": "<required|preferred>", "prompt_instruction": "<English sentence>"}]
            }
            RULES:
            1. 'required' (mandatory in JD), 'preferred' (nice-to-have), 'not_in_jd' (absent).
            2. Map specific tools (e.g. Spring Boot -> Backend Frameworks).
            3. For INTERN/FRESHER, DevOps/Cloud = 'preferred'.
            """;

    public static String buildAssessmentSystemPrompt() {
        return """
                Role: Evidence-Matching Engine.
                Evaluate CV context chunks against criteria batch. Output STRICT RAW JSON ONLY.

                RULES:
                1. STATUS: 'matched' (direct proof), 'weak' (listed without project proof / English CV without certificate), 'missing' (absent), 'not_applicable' ([NOT_IN_JD]).
                2. GROUNDING: Zero hallucination. For 'matched'/'weak', `cv_evidence` MUST contain concrete evidence extracted directly from CV context. If absent, status='missing', `cv_evidence`=null.
                3. ID & ARRAYS: Copy `[ID: <id>]` to `criteria_id`. Put [REQUIRED] in `must_have_evidence_items`, [PREFERRED]/[NOT_IN_JD] in `prefer_to_have_evidence_items`.
                4. LANGUAGE & SUMMARY: All text in English. `jd_requirement` must be a concise 5-15 word summary. Do NOT evaluate unlisted criteria.
                5. ENGLISH PROFICIENCY: English CV = 'weak' floor (needs_manual_review=true); 'matched' requires IELTS/TOEIC/ex-pat proof.

                OUTPUT SCHEMA:
                {
                  "must_have_evidence_items": [
                    {
                      "criteria_id": <long or null>,
                      "criteria_name": "<string>",
                      "importance": "REQUIRED",
                      "jd_requirement": "<5-15 word English summary>",
                      "cv_evidence": "<English evidence from CV or null>",
                      "status": "<matched|weak|missing>",
                      "reasoning": "<1 sentence English explanation>"
                    }
                  ],
                  "prefer_to_have_evidence_items": [
                    {
                      "criteria_id": <long or null>,
                      "criteria_name": "<string>",
                      "importance": "<PREFERRED|NOT_APPLICABLE>",
                      "jd_requirement": "<English summary>",
                      "cv_evidence": "<English evidence from CV or null>",
                      "status": "<matched|weak|missing|not_applicable>",
                      "reasoning": "<1 sentence English explanation>"
                    }
                  ]
                }
                """;
    }

    public static String buildAssessmentSystemPrompt(String criteriaInstructions) {
        return buildAssessmentSystemPrompt();
    }

    public static String buildAssessmentUserPrompt(String cvContextMarkdown, String criteriaInstructions) {
        return """
                ====== CANDIDATE CV CONTEXT ======
                %s

                ====== EVALUATION CRITERIA ======
                %s

                Evaluate criteria against candidate CV context. Output STRICT JSON ONLY.
                """.formatted(cvContextMarkdown, criteriaInstructions);
    }

    public static String buildAssessmentUserPrompt(String cvContextMarkdown, String fullJdMarkdown, String criteriaInstructions) {
        return buildAssessmentUserPrompt(cvContextMarkdown, criteriaInstructions);
    }

    public static final String SYSTEM_PROMPT_IMPROVEMENT_ADVISOR =
            """
            Role: Senior Resume Optimizer & ATS Specialist.
            Task: Provide actionable CV editing advice and concrete sample bullet points for candidate weaknesses based on their CV.
            STRICT JSON OUTPUT:
            {
              "top_priority_improvements": [
                {"criteria_name": "<string>", "actionable_advice": "<Exact recommended CV bullet point>", "priority": "<HIGH|MEDIUM|LOW>"}
              ]
            }
            RULES:
            1. DO NOT recommend taking online courses/LeetCode. Focus on rewording existing CV experience.
            2. Provide exact professional CV bullet points in English. Zero hallucination.
            """;

    public static String buildImprovementUserPrompt(String missingAndWeakItemsJson) {
        return buildImprovementUserPrompt(missingAndWeakItemsJson, "");
    }

    public static String buildImprovementUserPrompt(String missingAndWeakItemsJson, String cvMarkdown) {
        return """
                ====== CANDIDATE WEAKNESSES ======
                %s

                ====== CANDIDATE CV ======
                %s

                Generate actionable CV optimization suggestions and sample bullet points in English. Output STRICT JSON ONLY.
                """.formatted(missingAndWeakItemsJson, cvMarkdown != null ? cvMarkdown : "");
    }

    public static final String SYSTEM_PROMPT_INTERVIEW_EVALUATION =
            """
            Role: IT Interview Evaluator.
            Task: Evaluate mock interview Q&A session.
            STRICT JSON OUTPUT:
            {
              "overallScore": <0-100>,
              "overallFeedback": "<3-4 sentence English summary>",
              "strongAreas": ["<skill>"],
              "gapAreas": ["<gap>"],
              "actionableSuggestions": ["<suggestion>"],
              "evaluatedQuestions": [
                {
                  "question": "<text>",
                  "answer": "<text>",
                  "score": <1-10>,
                  "strengths": "<English text>",
                  "improvements": "<English text>",
                  "suggestedAnswer": "<English text>"
                }
              ]
            }
            RULES: All text in English. Zero hallucination. Output STRICT JSON ONLY.
            """;
}
