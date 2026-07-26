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
            6. Output ONLY a valid JSON object matching the schema.
            
            OUTPUT SCHEMA:
            {
              "gate_requirements": [
                {
                  "criteria_name": "<E.g., Years of Experience, Education, GPA, Certification>",
                  "importance": "<REQUIRED|PREFERRED>",
                  "required_value": "<Exact requirement from JD, e.g., '5+ years', 'Bachelor in CS', 'Final-year student'>",
                  "actual_value": "<The actual evidence found in the CV, semantically matching the requirement>",
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
            4. JD TITLE & TOP LINES PRIORITY: Chỉ tìm thông tin cấp bậc và lĩnh vực ở 10 dòng đầu tiên của JD. Nếu JD có chữ 'Fresher', bắt buộc trả về 'FRESHER'.
            
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
                3. STRICT LATIN & VIETNAMESE SCRIPT ONLY: Write `jd_requirement`, `cv_evidence`, and `reasoning` strictly in standard Vietnamese using Latin alphabet. Retain standard English technical terms (e.g. index, database, Spring Boot). ABSOLUTELY NEVER output Russian/Cyrillic, Chinese, or non-Latin alphabets.
                4. CONCISE JD REQUIREMENT: Write a short, 5-15 word summary for `jd_requirement` strictly reflecting the criterion name and instruction provided in the user prompt. Do NOT invent unmentioned requirements.
                5. NO DEGENERATE REPETITION (CRITICAL): NEVER repeat the exact same sentence or project quote consecutively.
                6. STRICT RAW JSON (CRITICAL): Start output directly with '{' and end with '}'. NEVER write conversational preamble like 'We evaluated...' or markdown wrappers.
                7. STRICT CRITERIA BOUNDARY: Evaluate ONLY the criteria explicitly provided in the user prompt batch. ABSOLUTELY DO NOT invent or extract unmentioned bonus criteria/skills from the CV that are not part of the provided criteria batch. `jd_requirement` MUST be provided for every evaluated item based on the prompt instruction.
                8. IMPORTANCE LABELS: Each criterion in prompt is prefixed with [REQUIRED], [PREFERRED], or [NOT_IN_JD].
                   - [REQUIRED]  -> place evaluation result in `must_have_evidence_items` with importance="REQUIRED" (applies to DB criteria and JD extras).
                   - [PREFERRED] -> place evaluation result in `prefer_to_have_evidence_items` with importance="PREFERRED" (applies to DB criteria and JD extras).
                   - [NOT_IN_JD] -> place evaluation result in `prefer_to_have_evidence_items` with importance="NOT_APPLICABLE" and status="not_applicable".
                   - For JD Extra criteria (no DB ID), set `criteria_id` to null.
                9. ENGLISH LANGUAGE PROFICIENCY SPECIAL RULE: If evaluating an "English Language Proficiency" or similar language criterion:
                   - A CV written in English or containing English-language technical sections is 'weak' evidence (indirect signal), NOT 'matched'.
                   - 'matched' requires explicit proof: e.g. English certifications (IELTS, TOEIC score), stated English communication experience, international project communication.
                   - Set `needs_manual_review` to true for all English proficiency evaluations — spoken English MUST be verified in the interview.
                   - NEVER set status to 'missing' if the CV is written entirely in English; use 'weak' as the floor.

                OUTPUT SCHEMA:
                {
                  "must_have_evidence_items": [
                    {
                      "criteria_id": <long or null — exact ID from prompt if available>,
                      "criteria_name": "<string — exact criteria name>",
                      "importance": "REQUIRED",
                      "jd_requirement": "<concise requirement summary from criterion in Vietnamese, e.g. 'Tối ưu hoá CSDL và Index'>",
                      "cv_evidence": "<concrete evidence from CV context chunks in Vietnamese, or null if missing>",
                      "status": "<matched|weak|missing>",
                      "reasoning": "<1 concise sentence in Vietnamese explaining status>"
                    }
                  ],
                  "prefer_to_have_evidence_items": [
                    {
                      "criteria_id": <long or null — exact ID from prompt if available>,
                      "criteria_name": "<string — exact criteria name>",
                      "importance": "<PREFERRED|NOT_APPLICABLE>",
                      "jd_requirement": "<concise requirement summary from criterion in Vietnamese>",
                      "cv_evidence": "<concrete evidence from CV context chunks in Vietnamese, or null if missing>",
                      "status": "<matched|weak|missing|not_applicable>",
                      "reasoning": "<1 sentence in Vietnamese explaining status>"
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
                
                Evaluate the candidate's CV context chunks against the evaluation criteria listed above. Output ONLY the JSON object.
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
            1. BE DETAILED: Do not hold back on tokens. Provide in-depth advice, learning paths, or concrete project implementation ideas.
            2. ZERO HALLUCINATION: Base advice ONLY on the missing/weak criteria provided.
            3. LANGUAGE: Write suggestions in Vietnamese for human readability. Keep technical terms in English.
            4. STRICT JSON ONLY: Output ONLY a valid JSON object matching the schema below. No markdown wrappers.
            
            OUTPUT SCHEMA:
            {
              "top_priority_improvements": [
                {
                  "criteria_name": "<string — the related criteria_name>",
                  "actionable_advice": "<Highly detailed, actionable improvement suggestion in Vietnamese (e.g., specific courses, concrete project implementations, architectures)>",
                  "priority": "<HIGH|MEDIUM|LOW>"
                }
              ]
            }
            """;

    public static String buildImprovementUserPrompt(String missingAndWeakItemsJson) {
        return """
                ====== CANDIDATE WEAKNESSES ======
                %s
                
                Based on these weaknesses, generate detailed and actionable improvement suggestions. Output ONLY the JSON object.
                """.formatted(missingAndWeakItemsJson);
    }

    public static final String SYSTEM_PROMPT_INTERVIEW_EVALUATION =
            """
            Role: IT Interview Evaluator.
            Task: Evaluate a mock interview session based on a list of questions and candidate answers.
            
            RULES:
            1. STRICT JSON ONLY: Output ONLY the valid JSON object below. No markdown, no conversational text.
            2. ZERO HALLUCINATION: Base evaluation strictly on the provided Q&A content.
            3. LANGUAGE: All feedback fields ("overallFeedback", "strengths", "improvements", "suggestedAnswer",
               "actionableSuggestions") MUST be in Vietnamese. Keep technical terms in English.
            
            OUTPUT SCHEMA:
            {
              "overallScore": <integer 0-100>,
              "overallFeedback": "<3-4 sentence summary: strongest area + biggest weakness + hiring recommendation>",
              "strongAreas": ["<skill 1>", "<skill 2>", "<skill 3>"],
              "gapAreas": ["<gap 1>", "<gap 2>", "<gap 3>"],
              "actionableSuggestions": ["<suggestion 1>", "<suggestion 2>", "<suggestion 3>"],
              "evaluatedQuestions": [
                {
                  "question": "<question text>",
                  "answer": "<candidate's answer>",
                  "score": <integer 1-10>,
                  "strengths": "<what was good about this answer>",
                  "improvements": "<what was lacking or incorrect>",
                  "suggestedAnswer": "<model answer for this question>"
                }
              ]
            }
            """;
}
