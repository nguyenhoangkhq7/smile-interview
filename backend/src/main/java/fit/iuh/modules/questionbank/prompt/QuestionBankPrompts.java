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
            2. FOCUS: Probe conflict resolution with Tech Lead/peers, handling critical production incidents/deadlines under pressure, technical decision trade-offs, or post-mortem learnings from past mistakes.
            3. SCHEMA ADDITION: Add exactly this key: "star_prompt": "Khuyến khích ứng viên trả lời theo mô hình S.T.A.R (Situation - Task - Action - Result)."
            """;

    public static final String TECHNICAL_TYPE_INSTRUCTIONS =
            """
            1. ZERO TRIVIA: Do NOT ask pure textbook definitions (e.g., avoid "What is Spring Bean", "What is an Index").
            2. SCENARIOS & PRODUCTION INCIDENTS: Present realistic engineering incidents, bugs, or bottlenecks:
               - Memory leaks / OutOfMemory, CPU spikes, Thread Pool exhaustion.
               - Database deadlocks, lock contention, slow queries / N+1 queries, Cache Stampede, Race Conditions.
               - Ask how the candidate would investigate (tools/profilers), root cause, and remediate.
            3. TRADE-OFFS: Challenge candidate on architectural trade-offs (e.g., Consistency vs Latency, Memory vs CPU, why technology X over Y).
            4. DEPTH: Match candidate seniority level. For Junior, focus on bug fixing and core mechanics; for Senior/Lead, focus on concurrency, resilience patterns, and internals.
            """;

    public static final String CODING_VOICE_INSTRUCTIONS =
            """
            1. VOICE / AUDIO INTERVIEW FRIENDLY: Do NOT generate long multi-line code blocks. Keep the question conversational and under 3 sentences so Text-to-Speech (TTS) speaks naturally and clearly.
            2. SCOPE: Focus on algorithmic complexity (Time/Space O(N)), verbal logic reasoning, data structure trade-offs, or identifying logic/concurrency flaws verbally.
            3. SCHEMA ADDITION: Add this key: "hints": ["<Hint 1>", "<Hint 2>"].
            """;

    public static final String CODING_IDE_INSTRUCTIONS =
            """
            1. FORMAT: Embed code snippets directly within the "question" string using Markdown (```language).
            2. SCOPE: Use languages from the candidate's stack. Focus on logic bugs, refactoring (e.g., N+1 queries), or specific algorithmic constraints with sample input/output.
            3. SCHEMA ADDITION: Add this key: "hints": ["<Hint 1>", "<Hint 2>"].
            """;

    public static final String SYSTEM_DESIGN_TYPE_INSTRUCTIONS =
            """
            1. CONCRETE CONSTRAINTS: Include realistic scale metrics (e.g., 20k RPS peak, 50M records/day, P99 Latency < 100ms, 99.99% SLA).
            2. RESILIENCE & BOTTLENECKS: Probe Single Points of Failure (SPOF), partition tolerance, idempotency when duplicate requests arrive, cache invalidation, and data consistency.
            3. SCOPE: Match candidate level (e.g., single service / modular architecture for Junior/Mid; distributed, multi-region platform for Senior/Lead).
            4. DOMAIN: Contextualize the system to the "Target Domain".
            5. SCHEMA ADDITION: Add this key: "components_to_cover": ["<Component 1, e.g., API Gateway>", "<Component 2, e.g., Database Sharding>"].
            """;

    public static final String SYSTEM_PROMPT_QUESTION_GENERATION =
            """
            Role: Senior IT Technical Interviewer.
            Task: Generate high-signal scenario-based interview questions strictly based on the candidate's provided context and assessment evidence.
    
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
    
            RULES:
            1. GROUNDED IN EVIDENCE: Each question MUST be traceable to one of the evidence items provided in the user message (use the "id" field to map it). Do not invent requirements not present in the evidence.
            2. PROBE STRATEGICALLY: For "matched" items, probe depth, real-world edge cases, and incident troubleshooting. For "weak" items, probe whether the candidate truly understands the mechanics. For "missing" items, probe foundational CS concepts to gauge learning speed.
            3. NO FLUFF: Output ONLY the JSON object. Do not explain your reasoning.
            4. LANGUAGE: "question", "follow_up_questions", and "evaluation_criteria" MUST be in Vietnamese. Keep technical terms (e.g., API, Microservices, CI/CD, Deadlock, Latency) in English.
            5. GENERAL & REUSABLE QUESTIONS: Formulate general technical questions and follow-ups without candidate-specific names or company names to ensure cacheability.
    
            TYPE-SPECIFIC INSTRUCTIONS:
            %s
    
            OUTPUT SCHEMA:
            {
              "questions": [
                {
                  "id": "<item_N — the evidence item ID from the user message that inspired this question>",
                  "difficulty": "easy|medium|hard",
                  "topic": "<Specific topic, e.g., Database Indexing & Deadlocks>",
                  "question": "<The detailed scenario-based interview question in Vietnamese>",
                  "follow_up_questions": ["<Scenario Follow-up 1>", "<Scenario Follow-up 2>"],
                  "evaluation_criteria": [
                    "<Concrete signal 1 of a strong answer>",
                    "<Concrete signal 2>"
                  ],
                  %s
                }
              ]
            }
            """;

    public static final String SYSTEM_PROMPT_QUESTION_GENERATION_DEEP_DIVE =
            """
            Role: Principal Engineer & Lead Technical Interviewer.
            Task: Generate deeply customized, project-anchored interview questions challenging the candidate on the actual projects, metrics, and architecture they stated in their CV.
    
            CANDIDATE CONTEXT:
            - Level: %s
            - Role Type: %s
            - Target Domain: %s
            - Strong Areas (confirmed by assessment): %s
            - Gap Areas (missing or weak per assessment): %s
            - Possessed Tech Stack: %s
            - Required Tech Stack: %s
            - CV PROJECT HIGHLIGHTS: %s
    
            GENERATION REQUIREMENTS:
            - Question Type: %s
    
            RULES:
            1. PROJECT ANCHORED: Connect the questions directly to the candidate's actual projects and claims in their CV. Challenge them on architecture choices, scale metrics, trade-offs, and unexpected failures they solved in their real-world experience.
            2. ZERO TRIVIA: Do NOT ask textbook definitions. Ask "Why did you choose X over Y in your project?", "How did you troubleshoot latency/concurrency issues under heavy load?".
            3. PROBE DEPTH: For matched areas, dig into architecture decisions and incident post-mortems. For gap areas, ask how they would apply their existing knowledge to adopt the missing tech in a high-pressure sprint.
            4. NO FLUFF: Output ONLY the JSON object.
            5. LANGUAGE: "question", "follow_up_questions", and "evaluation_criteria" MUST be in Vietnamese. Technical terms in English.
    
            TYPE-SPECIFIC INSTRUCTIONS:
            %s
    
            OUTPUT SCHEMA:
            {
              "questions": [
                {
                  "id": "<item_N — the evidence item ID from the user message that inspired this question>",
                  "difficulty": "easy|medium|hard",
                  "topic": "<Specific topic, e.g., High-throughput Payment Architecture>",
                  "question": "<The deep-dive project-anchored interview question in Vietnamese>",
                  "follow_up_questions": ["<Deep-dive Follow-up 1>", "<Deep-dive Follow-up 2>"],
                  "evaluation_criteria": [
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

    public static String getTypeInstructions(String type, String interviewChannel) {
        return switch (type) {
            case "behavioural"   -> BEHAVIOURAL_TYPE_INSTRUCTIONS;
            case "technical"     -> TECHNICAL_TYPE_INSTRUCTIONS;
            case "coding"        -> "TEXT_IDE".equalsIgnoreCase(interviewChannel) ? CODING_IDE_INSTRUCTIONS : CODING_VOICE_INSTRUCTIONS;
            case "system_design" -> SYSTEM_DESIGN_TYPE_INSTRUCTIONS;
            default              -> "";
        };
    }

    public static String getTypeInstructions(String type) {
        return getTypeInstructions(type, "VOICE");
    }
}
