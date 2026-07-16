ALTER TABLE evaluation_criteria ADD COLUMN IF NOT EXISTS question_type VARCHAR(50) DEFAULT 'technical';

-- Update default question types for existing default criteria
UPDATE evaluation_criteria SET question_type = 'coding' WHERE criteria_name IN (
    'Data Structures & Algorithms',
    'C/C++ Systems Programming'
);

UPDATE evaluation_criteria SET question_type = 'behavioural' WHERE criteria_name IN (
    'Agile & SDLC Practices',
    'Testing Fundamentals'
);

UPDATE evaluation_criteria SET question_type = 'system_design' WHERE criteria_name IN (
    'iOS Memory Management & Swift',
    'OWASP Top 10 & AppSec',
    'LLM RAG Pipelines & Vectors',
    'Spark & Kafka Streaming'
);
