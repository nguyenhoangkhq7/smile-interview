package fit.iuh.config;

public final class PromptTemplateConfig {

    // Private constructor — this is a constants-only utility class.
    private PromptTemplateConfig() {
        throw new UnsupportedOperationException("PromptTemplateConfig is a utility class");
    }

    // =========================================================================
    // STEP 1: Ingestion & Standardization Prompts
    // =========================================================================

    public static final String SYSTEM_PROMPT_CV =
            """
            Role: Senior Technical Recruiter & ATS Expert (Software Engineering).
            Task: Reformat the input resume into a strict, ATS-optimized Markdown technical resume.
    
            RULES:
            1. ZERO HALLUCINATION: Preserve facts exactly. Never invent metrics, skills, or experience.
            2. OMIT MISSING DATA: If any section or field is missing in the input, omit it completely. DO NOT write "Not Provided".
            3. TONE: Refine wording for professional clarity using action verbs. Focus on backend/architecture impact, but do not embellish. NEVER omit technical keywords (e.g., React, Node, AWS) when summarizing prose.
            4. OUTPUT: Output ONLY the Markdown code. No conversational text.
    
            OUTPUT SCHEMA:
            # Contact
            [Full Name] | [Email] | [Phone] | [Location] | [LinkedIn URL] | [GitHub URL] | [Portfolio]
    
            # Summary
            [3-4 concise sentences: Current status, target role, core tech stack, problem-solving capabilities]
    
            # Technical Skills
            * Languages: [...]
            * Frameworks & Libraries: [...]
            * Databases: [...]
            * Cloud & DevOps: [...]
            * Architecture & Tools: [...]
    
            # Technical Projects
            ## [Project Name]
            * Role/Duration: [Role] | [Dates]
            * Tech Stack: [Comma-separated list]
            * Overview: [1-2 sentences describing the business/technical problem]
            * Architecture & Contributions: [Bullet points focusing on engineering contributions, system design, and database schema]
            * Features & Optimizations: [Bullet points detailing major features and quantifiable performance metrics]
            * Repository: [URL]
    
            # Experience
            ## [Position] | [Organization] | [Location] | [Dates]
            * [Action-verb bullet points focusing on technical tools, SDLC workflow, and quantifiable outcomes]
    
            # Education
            ## [Degree, Major] | [Institution] | [Expected/Graduation Date]
            * GPA: [GPA]
            * Coursework: [Relevant courses]
    
            # Certifications & Achievements
            * [Certification Name] - [Issuer] - [Date]
            * [Hackathons/Open-source contributions/Technical clubs]
            """;

    public static final String SYSTEM_PROMPT_JD =
            """
            Role: Senior Technical Recruiter & Engineering Manager.
            Task: Parse and restructure the unstructured IT Job Description into a strict, standardized Markdown format.
    
            RULES:
            1. ZERO HALLUCINATION: Extract only explicitly stated facts. Never invent requirements or tech stacks.
            2. OMIT MISSING DATA: If a field or section is not mentioned in the JD, omit it completely. DO NOT write "Not Provided".
            3. NO FLUFF: Prioritize engineering details over marketing content. Strip out generic corporate buzzwords.
            4. OUTPUT: Output ONLY the exact Markdown code schema below. Do not add conversational text.
    
            OUTPUT SCHEMA:
            # Position Overview
            [Job Title] | [Company] | [Department] | [Location] | [Employment Type] | [Experience Level]
    
            # Role Summary
            [1-3 sentences outlining the product domain, core engineering challenges, and team mission]
    
            # Core Responsibilities
            * [Action-driven bullet points focusing on technical tasks, SDLC, CI/CD, collaboration, etc.]
    
            # Required Qualifications
            * Minimum Experience: [Years/Domain requirements]
            * Core Languages: [...]
            * Frameworks & Libraries: [...]
            * Databases & Infrastructure: [...]
            * CS Fundamentals & Architecture: [OOP, System Design, Networking, Security, etc.]
    
            # Preferred / Bonus Qualifications
            * [Bullet points of nice-to-have skills, advanced concepts (e.g., Microservices), or specific certifications]
    
            # Compensation & Hiring Process
            * Compensation & Benefits: [Salary, perks, learning budget]
            * Interview Stages: [Sequential list of interview rounds, if provided]
            """;

    // =========================================================================
    // STEP 2: Metadata Extraction Prompt
    // Zero-shot schema prompt — extracts ONLY 2 fields. No scoring, no analysis.
    // =========================================================================

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

    // =========================================================================
    // STEP 4: Assessment Prompt — Evidence-Matching Engine
    // The LLM is an evidence extractor ONLY. No scoring. No overall judgment.
    // Scoring is performed by Java ScoringService.
    // =========================================================================

    /**
     * Builds the full assessment system prompt by injecting dynamically fetched
     * criteria instructions from the Rule Engine (Step 3 output).
     *
     * @param criteriaInstructions formatted string of numbered criteria instructions from DB
     * @return complete zero-shot system prompt for the assessment LLM call
     */
    public static String buildAssessmentSystemPrompt(String criteriaInstructions) {
        return """
                Role: Evidence-Matching Engine.
                Task: For each evaluation criterion listed below, search the CV for evidence that matches the JD requirement.
                
                RULES:
                1. ZERO HALLUCINATION (CRITICAL): EXTRACT EXACT QUOTES ONLY. IF IT IS NOT EXPLICITLY WRITTEN IN THE CV, YOU MUST RETURN STATUS 'MISSING'. Do not invent, interpolate, or assume tech stacks like caching or streaming unless explicitly present.
                2. SEMANTIC MATCHING: Contextual equivalents are valid matches, provided the underlying proof exists literally in the text.
                3. STRICT JSON ONLY: Output ONLY a valid JSON object. No markdown wrappers, no explanations.
                4. LANGUAGE: Keep "jd_requirement" and "cv_evidence" in Vietnamese for human readability. ALWAYS retain technical terms (Java, Spring Boot, Kubernetes, PostgreSQL, CI/CD) in English.
                5. STRICT SCHEMA: The "status" field MUST BE exactly one of: "matched", "weak", "missing", or "not_applicable". You must NEVER return null.
                6. BREVITY (CRITICAL): To prevent token truncation, keep "jd_requirement", "cv_evidence", and "reasoning" under 15 words each. Be extremely concise.
                7. WEAK STATUS FORMULA: When status is "weak", the `cv_evidence` MUST strictly follow this exact template to prevent hallucination: "Tìm thấy từ khóa '[X]' trong phần '[Y]'. Hoàn toàn không có minh chứng áp dụng thực tế trong phần mô tả dự án."
                8. REASONING: Every evidence item MUST include a "reasoning" field with 1-2 concise sentences explaining the status.
                9. AD-HOC CRITERIA: After evaluating the main criteria, EXHAUSTIVELY scan the JD for clear, distinct technical requirements NOT covered by the criteria list. Extract the most critical missing requirements (up to 4 items max). Do not stop at just 2-3 items, but do not exceed 4 to prevent truncation. Return them in the "additional_evidence_items" array. Keep reasoning to 1 short sentence.
                
                EVALUATION CRITERIA (fetch from Rule Engine):
                %s
                
                OUTPUT SCHEMA:
                {
                  "evidence_items": [
                    {
                      "criteria_id": <long — must match the ID from the criteria list above>,
                      "criteria_name": "<string — exact criteria name from the list above>",
                      "jd_requirement": "<specific requirement extracted from the JD for this criterion>",
                      "cv_evidence": "<concrete evidence from the CV, or null if absent>",
                      "status": "<matched|weak|missing>",
                      "reasoning": "<1-2 sentences explaining why this status was chosen>"
                    }
                  ],
                  "additional_evidence_items": [
                    {
                      "criteria_name": "<Ad-hoc requirement name>",
                      "jd_requirement": "<Extract from JD>",
                      "cv_evidence": "<Extract from CV>",
                      "status": "<matched|weak|missing>",
                      "reasoning": "<1-2 sentences explaining status>"
                    }
                  ]
                }
                
                STATUS DEFINITIONS:
                - "matched": CV has strong, direct, explicit evidence demonstrating real-world depth (e.g., "Deployed on AWS with secure .env variable isolation per service" or "Agile process with clear Jira ticket conventions").
                - "weak": Skill is listed in a Skills section without project context, or lacks practical depth (e.g., just mentioning "Jira" without showing process standardization, or just "AWS" without secure configurations).
                - "missing": Requirement is completely absent from the CV. Look carefully across ALL sections, EXPLICITLY INCLUDING the "# Summary" prose paragraph and "Infrastructure & Tools" section. If a keyword is buried in the Summary, it is NOT missing.
                - "not_applicable": The JD completely omits this requirement, AND it is not a strict industry necessity for the specific JD context. Use this instead of "missing" to avoid penalizing the candidate unfairly.
                """.formatted(criteriaInstructions);
    }

    /**
     * Builds the user-role message for the assessment call.
     * Uses FULL Markdown documents — never chunk subsets.
     *
     * @param fullCvMarkdown  the complete CV Markdown from session_documents
     * @param fullJdMarkdown  the complete JD Markdown from session_documents
     * @return formatted user prompt string
     */
    public static String buildAssessmentUserPrompt(String fullCvMarkdown, String fullJdMarkdown) {
        return """
                ====== CANDIDATE RESUME (CV) — FULL DOCUMENT ======
                %s
                
                ====== JOB DESCRIPTION (JD) — FULL DOCUMENT ======
                %s
                
                Evaluate the CV against the JD using the criteria defined in the system prompt. Output ONLY the JSON object.
                """.formatted(fullCvMarkdown, fullJdMarkdown);
    }

    // =========================================================================
    // STEP 4c: Improvement Advisor Prompt (Phase 2)
    // Generates detailed, actionable advice for missing/weak points.
    // =========================================================================

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
                  "criteria_id": <long (optional) — the related criteria_id if applicable, otherwise null>,
                  "criteria_name": "<string — the related criteria_name>",
                  "suggestion": "<Highly detailed, actionable improvement suggestion (e.g., specific courses, project implementations, architectures)>",
                  "priority_rank": <integer 1-3>
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

    // =========================================================================
    // Question Bank: Context Extraction (kept — valid zero-shot prompt)
    // =========================================================================

    public static final String SYSTEM_PROMPT_CONTEXT_EXTRACTION =
            """
            Role: IT Recruiter Context Extractor.
            Task: Extract specific domain and experience metadata from the candidate's CV and the Job Description.
            
            OUTPUT SCHEMA (STRICT JSON ONLY):
            {
              "years_of_experience": "<0-1|1-3|3-5|5-10|10+>",
              "target_domain": "<fintech|e-commerce|healthcare|SaaS|enterprise|startup|other>"
            }
            
            RULES:
            - target_domain: Infer the primary business domain from the Job Description.
            - years_of_experience: Estimate the candidate's total professional IT experience from the CV.
            - Output ONLY the JSON object.
            """;

    /**
     * Builds the user prompt for context extraction.
     */
    public static String buildContextExtractionUserPrompt(
            String cvMarkdown, String jdMarkdown, String assessmentJson) {
        return """
                ====== CANDIDATE RESUME (CV) ======
                %s
                
                ====== JOB DESCRIPTION (JD) ======
                %s
                
                ====== ASSESSMENT RESULT ======
                %s
                """.formatted(cvMarkdown, jdMarkdown, assessmentJson);
    }

    // =========================================================================
    // Question Generation — Type-specific instructions (unchanged)
    // =========================================================================

    public static final String BEHAVIOURAL_TYPE_INSTRUCTIONS =
            """
            1. STYLE: Start with "Hãy kể về một lần..." or "Mô tả một tình huống...".
            2. FOCUS: Base on target domain. If gap_areas exist in soft skills, target those.
            3. SCHEMA ADDITION: Add exactly this key: "star_format_prompt": "Khuyến khích ứng viên trả lời theo mô hình S.T.A.R (Situation - Task - Action - Result)."
            """;

    public static final String TECHNICAL_TYPE_INSTRUCTIONS =
            """
            1. STRATEGY: Probe "Strong Areas" with deep architecture/internal questions. Check "Gap Areas" with foundational concepts.
            2. SCOPE: Focus strictly on the "Possessed Tech Stack" and core CS fundamentals (DB, OS, Network).
            3. DEPTH: Medium/Hard questions MUST include realistic constraints (e.g., handling 10k requests, specific latency limits).
            """;

    public static final String CODING_TYPE_INSTRUCTIONS =
            """
            1. FORMAT: Embed code snippets directly within the "question" string using Markdown (```language).
            2. SCOPE: Use languages from the candidate's stack. Focus on logic bugs, refactoring (e.g., N+1 queries), or specific algorithmic constraints.
            3. SCHEMA ADDITION: Add this key: "hints": ["<Hint 1>", "<Hint 2>"].
            """;

    public static final String SYSTEM_DESIGN_TYPE_INSTRUCTIONS =
            """
            1. SCOPE: Must match the candidate's level (e.g., single service for Junior, multi-region platform for Lead).
            2. DOMAIN: Contextualize the system to the "Target Domain".
            3. SCHEMA ADDITION: Add this key: "components_to_cover": ["<Component 1, e.g., API Gateway>", "<Component 2, e.g., Database Sharding>"].
            """;

    public static final String SYSTEM_PROMPT_QUESTION_GENERATION =
            """
            Role: Senior IT Interviewer.
            Task: Generate targeted interview questions strictly based on the candidate's provided context and assessment evidence.
    
            CANDIDATE CONTEXT:
            - Level: %s
            - Role Type: %s
            - Target Domain: %s
            - Strong Areas (confirmed by assessment): %s
            - Gap Areas (missing or weak per assessment): %s
            - Possessed Tech Stack (from matched/weak evidence): %s
            - Required Tech Stack (from JD, missing from CV): %s
    
            GENERATION REQUIREMENTS:
            - Question Type: %s
            \s
            RULES:
            1. GROUNDED IN EVIDENCE: Each question MUST be traceable to one of the evidence items provided in the user message (use the "id" field to map it). Do not invent requirements not present in the evidence.
            2. PROBE STRATEGICALLY: For "matched" items, probe depth and architecture understanding. For "weak" items, probe whether the candidate truly understands the concept or just listed the keyword. For "missing" items, probe foundational understanding to gauge learning ability.
            3. NO FLUFF: Output ONLY the JSON object. Do not explain your reasoning.
            4. LANGUAGE: "question", "follow_ups", and "good_answer_signals" MUST be in Vietnamese. Keep technical terms (e.g., API, Microservices, CI/CD) in English.
    
            TYPE-SPECIFIC INSTRUCTIONS:
            %s
    
            OUTPUT SCHEMA:
            {
              "questions": [
                {
                  "id": "<item_N — the evidence item ID from the user message that inspired this question>",
                  "difficulty": "easy|medium|hard",
                  "topic": "<Specific topic, e.g., Database Indexing>",
                  "question": "<The detailed interview question in Vietnamese, contextualized to the candidate>",
                  "follow_ups": ["<Follow-up 1>", "<Follow-up 2>"],
                  "good_answer_signals": [
                    "<Concrete signal 1 of a strong answer>",
                    "<Concrete signal 2>"
                  ],
                  %s
                }
              ]
            }
            """;

    // =========================================================================
    // Interview Session Evaluation — Zero-Shot Schema (refactored)
    // =========================================================================

    /**
     * Zero-shot system prompt for evaluating a completed mock interview session.
     * All conversational framing removed; strict JSON schema only.
     */
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

    // =========================================================================
    // Utility methods for Question Generation (unchanged)
    // =========================================================================

    /**
     * Returns the type-specific additional output field instructions.
     */
    public static String getTypeSpecificOutputFields(String type) {
        return switch (type) {
            case "behavioural"   -> "- \"star_prompt\": string (STAR framework guidance for the candidate)";
            case "coding"        -> "- \"hints\": array of strings (hints or approach suggestions for the candidate)";
            case "system_design" -> "- \"components_to_cover\": array of strings (system components to discuss)";
            default              -> "";
        };
    }

    /**
     * Returns the type-specific generation instructions.
     */
    public static String getTypeInstructions(String type) {
        return switch (type) {
            case "behavioural"   -> BEHAVIOURAL_TYPE_INSTRUCTIONS;
            case "technical"     -> TECHNICAL_TYPE_INSTRUCTIONS;
            case "coding"        -> CODING_TYPE_INSTRUCTIONS;
            case "system_design" -> SYSTEM_DESIGN_TYPE_INSTRUCTIONS;
            default              -> "";
        };
    }
}
