CREATE TABLE managed_cv_objects (
    id UUID PRIMARY KEY,
    bucket TEXT NOT NULL,
    etag TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    retired_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ
);

CREATE INDEX idx_managed_cv_pending ON managed_cv_objects(bucket, created_at)
    WHERE etag IS NOT NULL AND deleted_at IS NULL;

-- Decode ASCII escapes before matching the application-generated UUID in a CV URL.
CREATE FUNCTION managed_cv_id(locator TEXT) RETURNS UUID
LANGUAGE plpgsql IMMUTABLE STRICT PARALLEL SAFE AS $$
DECLARE
    normalized TEXT := lower(locator);
BEGIN
    IF strpos(normalized, '%') > 0 THEN
        SELECT string_agg(
            CASE WHEN token ~ '^%[0-9a-f]{2}$' THEN
                CASE WHEN get_byte(decode(substring(token FROM 2), 'hex'), 0) BETWEEN 32 AND 126
                     THEN lower(chr(get_byte(decode(substring(token FROM 2), 'hex'), 0)))
                     ELSE token END
            ELSE token END, '' ORDER BY pos)
        INTO normalized
        FROM regexp_matches(normalized, '(%[0-9a-f]{2}|[^%]+|%)', 'g') WITH ORDINALITY AS pieces(value, pos)
        CROSS JOIN LATERAL (SELECT value[1] AS token) part;
    END IF;
    RETURN substring(normalized FROM 'resumes/managed/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})(?:[?#/]|$)')::uuid;
END;
$$;

CREATE INDEX idx_resume_managed_cv ON resumes (managed_cv_id(file_url));
CREATE INDEX idx_jd_managed_cv ON job_descriptions (managed_cv_id(file_url));
CREATE INDEX idx_avatar_managed_cv ON users (managed_cv_id(avatar_url));
CREATE INDEX idx_study_resource_managed_cv ON study_task_resources (managed_cv_id(url));

CREATE FUNCTION guard_managed_cv_reference() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    target UUID := managed_cv_id(to_jsonb(NEW)->>TG_ARGV[0]);
    retired TIMESTAMPTZ;
BEGIN
    IF target IS NOT NULL THEN
        SELECT retired_at INTO retired FROM managed_cv_objects WHERE id = target FOR UPDATE;
        IF retired IS NOT NULL THEN
            RAISE EXCEPTION 'Managed CV is no longer available' USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER guard_resume_managed_cv BEFORE INSERT OR UPDATE OF file_url ON resumes
    FOR EACH ROW EXECUTE FUNCTION guard_managed_cv_reference('file_url');
CREATE TRIGGER guard_jd_managed_cv BEFORE INSERT OR UPDATE OF file_url ON job_descriptions
    FOR EACH ROW EXECUTE FUNCTION guard_managed_cv_reference('file_url');
CREATE TRIGGER guard_avatar_managed_cv BEFORE INSERT OR UPDATE OF avatar_url ON users
    FOR EACH ROW EXECUTE FUNCTION guard_managed_cv_reference('avatar_url');
CREATE TRIGGER guard_study_resource_managed_cv BEFORE INSERT OR UPDATE OF url ON study_task_resources
    FOR EACH ROW EXECUTE FUNCTION guard_managed_cv_reference('url');
