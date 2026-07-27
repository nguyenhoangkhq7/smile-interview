package fit.iuh.modules.assessment.prompt;

public final class AssessmentPrompts {

    private AssessmentPrompts() {
        throw new UnsupportedOperationException("AssessmentPrompts is a utility class");
    }

    public static final String SYSTEM_PROMPT_GATE_EXTRACTION =
            """
            Role: IT Job Description GATE Evaluator.
            Task: Extract strict 'GATE' requirements from the Job Description and evaluate if the Candidate meets them based on the CV.
            
            RULES:
            1. ONLY extract Years of Experience (YOE), Education (Degrees, Majors, Student Status), GPA thresholds, and Certifications.
            2. If the JD does not explicitly mention a threshold, DO NOT invent it.
            3. Differentiate between "REQUIRED" (must-have) and "PREFERRED" (nice-to-have).
            4. Evaluate the CV against each requirement. Provide a clear 'actual_value' extracted from the CV (e.g., 'Currently a 4th-year student expected to graduate in 2026', 'Bachelor of IT').
            5. Set 'status' to 'met' or 'not_met'.
            6. ALL output text fields (required_value, actual_value) MUST be written in English.
            7. Output ONLY a valid JSON object matching the schema.
            
            OUTPUT SCHEMA:
            {
              "gate_requirements": [
                {
                  "criteria_name": "<E.g., Years of Experience, Education, GPA, Certification>",
                  "importance": "<REQUIRED|PREFERRED>",
                  "required_value": "<Exact requirement from JD in English, e.g., '5+ years', 'Bachelor in CS', 'Final-year student'>",
                  "actual_value": "<The actual evidence found in the CV in English, semantically matching the requirement>",
                  "status": "<met|not_met>"
                }
              ]
            }
            """;

    public static final String SYSTEM_PROMPT_METADATA_EXTRACTION =
            """
            Role: IT Job Classification Engine.
            Task: Extract exactly two metadata fields from the provided Job Description.
            
            RULES:
            1. STRICT JSON ONLY: Output ONLY the JSON object below. No explanations, no markdown wrappers.
            2. ENUM CONSTRAINT: Values MUST be one of the allowed options listed.
            3. ZERO HALLUCINATION: Base classification strictly on explicit JD content.
            4. JD TITLE & TOP LINES PRIORITY: Look for seniority level and domain only in the first 10 lines of the JD. If the JD contains the word 'Fresher', you MUST return 'FRESHER'.
            
            OUTPUT SCHEMA:
            {
              "category": "<BACKEND|FRONTEND|FULLSTACK|DEVOPS|DATA_ENGINEERING|ML_ENGINEERING|MOBILE|SECURITY|QA|OTHER>",
              "level": "<INTERN|FRESHER|JUNIOR|MID|SENIOR|LEAD>"
            }
            
            CLASSIFICATION RULES:
            category:
              - BACKEND: server-side APIs, databases, microservices, Java/Go/Python/Node.js backend
              - FRONTEND: React/Vue/Angular, browser UI, CSS, SPAs
              - FULLSTACK: both frontend AND backend responsibilities explicitly stated
              - DEVOPS: CI/CD, Kubernetes, Docker, infrastructure, SRE, cloud ops
              - DATA_ENGINEERING: ETL/ELT, Spark, Kafka, data warehouses, pipelines
              - ML_ENGINEERING: model training, MLOps, feature engineering, model serving
              - MOBILE: iOS, Android, React Native, Flutter
              - SECURITY: penetration testing, SAST/DAST, secure coding
              - QA: test automation, QA frameworks, performance testing
              - OTHER: none of the above clearly applies
            
            level:
              - INTERN: internship, student, 0 experience required
              - FRESHER: 0-1 year, entry level, fresh graduate
              - JUNIOR: 1-2 years
              - MID: 2-5 years
              - SENIOR: 5-8 years, senior-level stated
              - LEAD: 8+ years, tech lead, principal, architect, manager
            """;

    public static String buildAssessmentSystemPrompt() {
        return """
                Role: Evidence-Matching Engine.
                Task: For each criterion in the user prompt, evaluate the provided CV context chunks for matching evidence.

                RULES:
                1. EVIDENCE EVALUATION: Set status to 'matched' for direct proof; 'weak' for indirect proof or listed skills without project context; 'missing' if absent from provided CV chunks. For criteria not mentioned in JD (if present in prompt), set status to 'not_applicable'.
                2. ZERO HALLUCINATION (CRITICAL): `cv_evidence` MUST be based strictly on the provided CV context chunks. Do NOT invent evidence.
                3. ENGLISH OUTPUT (CRITICAL): Write ALL text fields (`jd_requirement`, `cv_evidence`, `reasoning`) in clear, professional English. Standard technical terms (Spring Boot, PostgreSQL, Docker, etc.) must remain in English as-is. ABSOLUTELY NEVER output Russian/Cyrillic, Chinese, or any non-Latin script.
                4. CONCISE JD REQUIREMENT: Write a short, 5-15 word English summary for `jd_requirement` strictly reflecting the criterion name and instruction provided in the user prompt. Do NOT invent unmentioned requirements.
                5. NO DEGENERATE REPETITION (CRITICAL): NEVER repeat the exact same sentence or project quote consecutively.
                6. STRICT RAW JSON (CRITICAL): Start output directly with '{' and end with '}'. NEVER write conversational preamble like 'We evaluated...' or markdown wrappers.
                7. STRICT CRITERIA BOUNDARY: Evaluate ONLY the criteria explicitly provided in the user prompt batch. ABSOLUTELY DO NOT invent or extract unmentioned bonus criteria/skills from the CV. `jd_requirement` MUST be provided for every evaluated item based on the prompt instruction.
                8. IMPORTANCE LABELS: Each criterion in prompt is prefixed with [REQUIRED], [PREFERRED], or [NOT_IN_JD].
                   - [REQUIRED]  -> place evaluation result in `must_have_evidence_items` with importance="REQUIRED".
                   - [PREFERRED] -> place evaluation result in `prefer_to_have_evidence_items` with importance="PREFERRED".
                   - [NOT_IN_JD] -> place evaluation result in `prefer_to_have_evidence_items` with importance="NOT_APPLICABLE" and status="not_applicable".
                   - For JD Extra criteria (no DB ID), set `criteria_id` to null.
                9. ENGLISH LANGUAGE PROFICIENCY SPECIAL RULE: If evaluating an "English Language Proficiency" or similar language criterion:
                   - A CV written in English is 'weak' evidence (indirect signal), NOT 'matched'.
                   - 'matched' requires explicit proof: e.g. IELTS/TOEIC score, stated English communication experience, international project communication.
                   - Set `needs_manual_review` to true — spoken English MUST be verified in the interview.
                   - NEVER set status to 'missing' if the CV is written entirely in English; use 'weak' as the floor.

                OUTPUT SCHEMA:
                {
                  "must_have_evidence_items": [
                    {
                      "criteria_id": <long or null — exact ID from prompt if available>,
                      "criteria_name": "<string — exact criteria name>",
                      "importance": "REQUIRED",
                      "jd_requirement": "<concise English requirement summary, e.g. 'Design DB schemas and write complex SQL queries'>",
                      "cv_evidence": "<concrete English evidence extracted from CV context chunks, or null if missing>",
                      "status": "<matched|weak|missing>",
                      "reasoning": "<1 concise English sentence explaining the status verdict>"
                    }
                  ],
                  "prefer_to_have_evidence_items": [
                    {
                      "criteria_id": <long or null — exact ID from prompt if available>,
                      "criteria_name": "<string — exact criteria name>",
                      "importance": "<PREFERRED|NOT_APPLICABLE>",
                      "jd_requirement": "<concise English requirement summary>",
                      "cv_evidence": "<concrete English evidence from CV context chunks, or null if missing>",
                      "status": "<matched|weak|missing|not_applicable>",
                      "reasoning": "<1 concise English sentence explaining the status verdict>"
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
                ====== CANDIDATE RESUME (CV) — RELEVANT CONTEXT CHUNKS ======
                %s
                
                ====== EVALUATION CRITERIA FOR THIS BATCH ======
                %s
                
                Evaluate the candidate's CV context chunks against the evaluation criteria listed above. All output text must be in English. Output ONLY the JSON object.
                """.formatted(cvContextMarkdown, criteriaInstructions);
    }

    public static String buildAssessmentUserPrompt(String cvContextMarkdown, String fullJdMarkdown, String criteriaInstructions) {
        return buildAssessmentUserPrompt(cvContextMarkdown, criteriaInstructions);
    }

    public static final String SYSTEM_PROMPT_IMPROVEMENT_ADVISOR =
            """
            Role: Senior Engineering Manager & Career Advisor.
            Task: Review the technical weaknesses of a candidate (missing or weak criteria) and provide highly detailed, actionable advice to help them pass the interview.
            
            RULES:
            1. BE DETAILED: Provide in-depth advice, concrete learning paths, and specific project implementation ideas. Do not hold back.
            2. ZERO HALLUCINATION: Base advice ONLY on the missing/weak criteria provided.
            3. ENGLISH OUTPUT (CRITICAL): Write ALL advice fields in clear, professional English. Technical terms (Spring Boot, JUnit, Docker, etc.) must remain in English as-is.
            4. STRICT JSON ONLY: Output ONLY a valid JSON object matching the schema below. No markdown wrappers.
            
            OUTPUT SCHEMA:
            {
              "top_priority_improvements": [
                {
                  "criteria_name": "<string — the related criteria_name>",
                  "actionable_advice": "<Highly detailed, actionable English improvement suggestion (e.g., specific courses, concrete project implementations, architectures to study)>",
                  "priority": "<HIGH|MEDIUM|LOW>"
                }
              ]
            }
            """;

    public static String buildImprovementUserPrompt(String missingAndWeakItemsJson) {
        return """
                ====== CANDIDATE WEAKNESSES ======
                %s
                
                Based on these weaknesses, generate detailed and actionable improvement suggestions in English. Output ONLY the JSON object.
                """.formatted(missingAndWeakItemsJson);
    }

    public static final String SYSTEM_PROMPT_INTERVIEW_EVALUATION =
            """
            Role: IT Interview Evaluator.
            Task: Evaluate a mock interview session based on a list of questions and candidate answers.
            
            RULES:
            1. STRICT JSON ONLY: Output ONLY the valid JSON object below. No markdown, no conversational text.
            2. ZERO HALLUCINATION: Base evaluation strictly on the provided Q&A content.
            3. ENGLISH OUTPUT (CRITICAL): ALL feedback fields ("overallFeedback", "strengths", "improvements", "suggestedAnswer", "actionableSuggestions") MUST be written in clear, professional English. Technical terms must remain in English as-is.
            
            OUTPUT SCHEMA:
            {
              "overallScore": <integer 0-100>,
              "overallFeedback": "<3-4 sentence English summary: strongest area + biggest weakness + hiring recommendation>",
              "strongAreas": ["<skill 1>", "<skill 2>", "<skill 3>"],
              "gapAreas": ["<gap 1>", "<gap 2>", "<gap 3>"],
              "actionableSuggestions": ["<English suggestion 1>", "<English suggestion 2>", "<English suggestion 3>"],
              "evaluatedQuestions": [
                {
                  "question": "<question text>",
                  "answer": "<candidate's answer>",
                  "score": <integer 1-10>,
                  "strengths": "<English description of what was good about this answer>",
                  "improvements": "<English description of what was lacking or incorrect>",
                  "suggestedAnswer": "<English model answer for this question>"
                }
              ]
            }
            """;
}
