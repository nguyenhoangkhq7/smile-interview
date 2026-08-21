-- ============================================================
-- V12: Seed system settings for 4-level status scoring (matched, partial, weak, missing)
-- ============================================================

INSERT INTO system_settings (setting_key, setting_value, description, updated_at)
VALUES ('STATUS_MATCHED_COEFF', '1.0',
        'Score coefficient for "matched" status (100% full match with strong direct proof).',
        NOW())
ON CONFLICT (setting_key) DO NOTHING;

INSERT INTO system_settings (setting_key, setting_value, description, updated_at)
VALUES ('STATUS_PARTIAL_COEFF', '0.65',
        'Score coefficient for "partial" status (65% moderate match, candidate has hands-on experience but lacks depth or sub-requirements).',
        NOW())
ON CONFLICT (setting_key) DO NOTHING;

INSERT INTO system_settings (setting_key, setting_value, description, updated_at)
VALUES ('STATUS_WEAK_COEFF', '0.30',
        'Score coefficient for "weak" status (30% basic introductory / keyword listed without detailed project context).',
        NOW())
ON CONFLICT (setting_key) DO NOTHING;

INSERT INTO system_settings (setting_key, setting_value, description, updated_at)
VALUES ('STATUS_MISSING_COEFF', '0.0',
        'Score coefficient for "missing" status (0% absent requirement).',
        NOW())
ON CONFLICT (setting_key) DO NOTHING;

INSERT INTO system_settings (setting_key, setting_value, description, updated_at)
VALUES ('PARTIAL_COEFF_INTERN_FRESHER', '0.75',
        'Score coefficient for "partial" status for INTERN and FRESHER candidates (more lenient grading for entry-level candidates).',
        NOW())
ON CONFLICT (setting_key) DO NOTHING;

INSERT INTO system_settings (setting_key, setting_value, description, updated_at)
VALUES ('PARTIAL_COEFF_SENIOR_LEAD', '0.50',
        'Score coefficient for "partial" status for SENIOR and LEAD candidates (stricter grading for leadership positions).',
        NOW())
ON CONFLICT (setting_key) DO NOTHING;
