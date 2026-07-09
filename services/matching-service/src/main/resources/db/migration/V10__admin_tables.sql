-- ============================================================
-- V10: Admin Control Center Tables
-- Adds two new tables to support dynamic Admin configuration:
--   1. level_distribution_rules  — replaces hardcoded switch-case in DifficultyDistributor
--   2. system_settings           — key-value store for global numeric coefficients
--                                  (e.g., MATCH_SCORE_PIVOT, STATUS_WEAK_COEFF)
-- ============================================================

-- Table: level_distribution_rules
-- Each row defines the base percentage split for one SeniorityLevel.
-- Replaces the hardcoded switch-case in DifficultyDistributor.calculateCategoryDistribution()
CREATE TABLE IF NOT EXISTS level_distribution_rules (
    id                BIGSERIAL        PRIMARY KEY,
    level             VARCHAR(20)      NOT NULL UNIQUE
                          CHECK (level IN ('INTERN','FRESHER','JUNIOR','MID','SENIOR','LEAD')),
    behavioral_pct    DOUBLE PRECISION NOT NULL CHECK (behavioral_pct    >= 0),
    technical_pct     DOUBLE PRECISION NOT NULL CHECK (technical_pct     >= 0),
    coding_pct        DOUBLE PRECISION NOT NULL CHECK (coding_pct        >= 0),
    system_design_pct DOUBLE PRECISION NOT NULL CHECK (system_design_pct >= 0)
);

COMMENT ON TABLE  level_distribution_rules                   IS 'Base question-category percentage distributions per seniority level; replaces DifficultyDistributor hardcoded switch-case';
COMMENT ON COLUMN level_distribution_rules.level             IS 'Maps to SeniorityLevel enum; UNIQUE constraint ensures one row per level';
COMMENT ON COLUMN level_distribution_rules.behavioral_pct    IS 'Base % of behavioral questions (0–100). Values do not need to sum to 100 — normalised at runtime.';
COMMENT ON COLUMN level_distribution_rules.technical_pct     IS 'Base % of technical questions (0–100)';
COMMENT ON COLUMN level_distribution_rules.coding_pct        IS 'Base % of coding questions (0–100)';
COMMENT ON COLUMN level_distribution_rules.system_design_pct IS 'Base % of system-design questions (0–100)';

-- Table: system_settings
-- Generic key-value store for numeric/string global configuration.
-- Consumers read values at runtime with a safe fallback default.
CREATE TABLE IF NOT EXISTS system_settings (
    setting_key   VARCHAR(100) PRIMARY KEY,
    setting_value VARCHAR(500) NOT NULL
);

COMMENT ON TABLE  system_settings               IS 'Global key-value configuration store; replaces magic numbers in DifficultyDistributor and ScoringService';
COMMENT ON COLUMN system_settings.setting_key   IS 'Unique config key (e.g., MATCH_SCORE_PIVOT, STATUS_WEAK_COEFF)';
COMMENT ON COLUMN system_settings.setting_value IS 'String-encoded value — callers cast to Double/Int as needed';
