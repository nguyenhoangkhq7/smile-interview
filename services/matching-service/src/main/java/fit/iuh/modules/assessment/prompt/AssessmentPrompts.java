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
            {
              "category": "<BACKEND|FRONTEND|FULLSTACK|DEVOPS|DATA_ENGINEERING|AI_ML|MOBILE|SECURITY|QA_TESTING|OTHER>",
              "accepted_levels": ["<INTERN|FRESHER|JUNIOR|MID|SENIOR|LEAD>"],
              "gate_requirements": [{"criteria_name": "<YOE|Education|GPA|Certification>", "importance": "<REQUIRED|PREFERRED>", "required_value": "<English text>"}],
              "classified": [{"criteria_id": <long>, "importance": "<required|preferred|not_in_jd>"}],
              "jd_extras": [{"name": "<skill>", "importance": "<required|preferred>", "prompt_instruction": "<English sentence>"}]
            }
            RULES:
            1. CATEGORY: BACKEND (APIs/Java/Go/Node), FRONTEND (React/Vue/CSS), FULLSTACK (both), DEVOPS (CI/CD/Docker/K8s), DATA_ENGINEERING (ETL/Spark/Pipelines), AI_ML (ML/LLM/Models), MOBILE (iOS/Android/Flutter), SECURITY (SAST/DAST), QA_TESTING (Automation/QA), OTHER.
            2. LEVEL: Check title/first 10 lines. Return an array of accepted levels. INTERN (0 exp/student), FRESHER (0-1 yr/fresh grad), JUNIOR (1-2 yrs), MID (2-5 yrs), SENIOR (5-8 yrs), LEAD (8+ yrs/Lead/Architect).
            3. GATES: Extract YOE, Education, GPA, Certifications explicitly in JD. Return [] if none. DO NOT extract technical skills, tools, frameworks, system design concepts (e.g. C4 Model), or programming languages as GATES — those MUST be classified as criteria.
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
            1. Only YOE, Education, GPA, Official Certifications. Do NOT extract technical skills, system design (e.g. C4 Model), tools, languages, or general requirements as GATES.
            2. Differentiate REQUIRED vs PREFERRED.
            3. All text fields in English. Output STRICT JSON ONLY.
            """;

    public static final String SYSTEM_PROMPT_METADATA_EXTRACTION =
            """
            Role: IT Job Classifier.
            Task: Extract category and levels from Job Description (first 10 lines priority).
            STRICT JSON OUTPUT:
            {
              "category": "<BACKEND|FRONTEND|FULLSTACK|DEVOPS|DATA_ENGINEERING|AI_ML|MOBILE|SECURITY|QA_TESTING|OTHER>",
              "accepted_levels": ["<INTERN|FRESHER|JUNIOR|MID|SENIOR|LEAD>"]
            }
            """;

    public static final String SYSTEM_PROMPT_CV_LEVEL_EXTRACTION =
            """
            Role: Candidate Seniority Assessor.
            Task: Extract the candidate's actual seniority level based strictly on their total Years of Experience (YOE) and Job Titles in their CV.
            STRICT JSON OUTPUT: {"level": "<INTERN|FRESHER|JUNIOR|MID|SENIOR|LEAD>"}
            RULES:
            - INTERN: 0 exp/student/internships
            - FRESHER: < 1 yr total exp
            - JUNIOR: 1-2 yrs total exp
            - MID: 2-5 yrs total exp
            - SENIOR: 5-8 yrs total exp
            - LEAD: 8+ yrs or explicit Lead/Architect titles
            """;

    public static final String SYSTEM_PROMPT_CRITERIA_CLASSIFICATION =
            """
            Role: JD Criteria Classifier & Extra Skill Extractor.
            STRICT JSON OUTPUT:
            {
              "classified": [{"criteria_id": <long>, "importance": "<required|preferred|not_in_jd>"}],
              "jd_extras": [{"name": "<skill>", "importance": "<required|preferred>", "prompt_instruction": "<English sentence>"}]
            }
            CRITICAL RULES FOR CLASSIFICATION:
            1. 'required': Core requirements explicitly requested or essential in the Job Description.
            2. 'preferred': Optional, nice-to-have, or secondary skills mentioned in JD.
            3. 'not_in_jd': STRICTLY mark any Database Criterion as 'not_in_jd' if it is NOT mentioned, NOT implied, or NOT required in the Job Description! Do NOT assign 'preferred' or 'required' to criteria that are completely absent from the JD.
            4. EXTRA SKILLS (jd_extras): Extract ONLY unique, highly specific technologies explicitly in JD that are NOT ALREADY COVERED by any item in the Database Criteria List above. DO NOT extract duplicate skills (e.g. do NOT extract 'Docker', 'MySQL', 'Agile', 'Git' if Docker/Databases/Agile/Git are in the DB criteria list). Limit to maximum 3-5 distinct extra skills. Default importance to 'preferred'.
            5. SENIORITY: For INTERN/FRESHER candidates, mark heavy DevOps/Cloud criteria as 'preferred'.
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
              "quick_wins": [
                {"criteria_name": "<string>", "actionable_advice": "<Exact recommended CV bullet point>", "priority": "<HIGH|MEDIUM|LOW>"}
              ],
              "skill_gaps": [
                {"criteria_name": "<string>", "actionable_advice": "<Exact recommended CV bullet point>", "priority": "<HIGH|MEDIUM|LOW>"}
              ]
            }
            STRICT CONSTRAINTS FOR ACTIONABLE ADVICE:
            1. ZERO FAKE METRICS: Only use numerical metrics (e.g., 500+ users, 30% latency reduction) if they explicitly appear in the candidate's CV for THAT specific project/technology. NEVER transfer metrics from Project A to Project B.
            2. REWORDING vs LAB PRACTICE:
               - Quick Wins (Technology X exists in CV but weak): Reframe the bullet point using STAR framework (Action Verb + Context + Measured Impact from that project).
               - Skill Gaps (Technology X is missing from CV): Frame as a practice recommendation: "If you have practiced X in a lab/personal project, write: 'Built a lab prototype using X to...'". DO NOT recommend taking online courses/LeetCode.
            3. Provide exact professional CV bullet points in English. Zero hallucination.
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
            Role: IT Senior Technical Interviewer & Evaluator.
            Task: Evaluate candidate's answers in a mock interview session fairly and objectively based on technical correctness, clarity, and completeness.
            STRICT JSON OUTPUT FORMAT:
            {
              "overallScore": <0-100 score>,
              "overallFeedback": "<General evaluation summary in Vietnamese>",
              "strongAreas": ["<candidate strong skill or area>"],
              "gapAreas": ["<gap or weak area>"],
              "actionableSuggestions": ["<practical improvement suggestion>"],
              "evaluatedQuestions": [
                {
                  "question": "<question text>",
                  "answer": "<candidate answer text>",
                  "score": <0-100 score for this turn>,
                  "strengths": "<What candidate answered well in Vietnamese>",
                  "improvements": "<What was missing or needs improvement in Vietnamese>",
                  "suggestedAnswer": "<Sample model answer in Vietnamese>"
                }
              ]
            }
            SCORING & LANGUAGE RULES:
            - Evaluate each question's score on a 0 to 100 scale (not 1 to 10).
            - If candidate provides a good, accurate, or partially correct answer, score appropriately from 60 to 100 based on technical accuracy and depth.
            - Only score 0 if candidate explicitly did not answer or answered completely off-topic.
            - All feedback text (overallFeedback, strengths, improvements, suggestedAnswer) MUST be written in fluent Vietnamese (Tiếng Việt).
            - Output STRICT JSON ONLY.
            """;
}
