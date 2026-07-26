package fit.iuh.modules.questionbank.prompt;

public final class QuestionBankPrompts {

    private QuestionBankPrompts() {
        throw new UnsupportedOperationException("QuestionBankPrompts is a utility class");
    }

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
            5. GENERAL & REUSABLE QUESTIONS: Both the main "question" and "follow_ups" MUST NOT contain candidate-specific identifying details (such as candidate name, company names, or candidate's specific project names from CV). Instead, formulate general technical questions and follow-ups. For example, instead of "Bạn đã tối ưu Spring Boot trong dự án E-commerce ABC của bạn ra sao?", ask "Bạn đã áp dụng các kỹ thuật nào để tối ưu hóa thời gian startup và memory footprint của một ứng dụng Spring Boot?". This is to ensure the generated questions are cacheable and safe to reuse for other candidates.
    
            TYPE-SPECIFIC INSTRUCTIONS:
            %s
    
            OUTPUT SCHEMA:
            {
              "questions": [
                {
                  "id": "<item_N — the evidence item ID from the user message that inspired this question>",
                  "difficulty": "easy|medium|hard",
                  "topic": "<Specific topic, e.g., Database Indexing>",
                  "question": "<The detailed, generic and reusable interview question in Vietnamese, targeted at the technical criteria, without candidate project names or company names>",
                  "follow_ups": ["<Generic Follow-up 1>", "<Generic Follow-up 2>"],
                  "good_answer_signals": [
                    "<Concrete signal 1 of a strong answer>",
                    "<Concrete signal 2>"
                  ],
                  %s
                }
              ]
            }
            """;

    public static String getTypeSpecificOutputFields(String type) {
        return switch (type) {
            case "behavioural"   -> "- \"star_prompt\": string (STAR framework guidance for the candidate)";
            case "coding"        -> "- \"hints\": array of strings (hints or approach suggestions for the candidate)";
            case "system_design" -> "- \"components_to_cover\": array of strings (system components to discuss)";
            default              -> "";
        };
    }

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
