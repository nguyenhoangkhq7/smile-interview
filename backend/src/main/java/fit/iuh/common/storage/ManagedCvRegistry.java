package fit.iuh.common.storage;

import lombok.RequiredArgsConstructor;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

import java.util.UUID;

@Repository
@RequiredArgsConstructor
public class ManagedCvRegistry {
    public static final String PREFIX = "resumes/managed/";
    private final JdbcTemplate jdbc;

    // Track successful uploads even if the enclosing CV transaction rolls back later.
    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void recordUpload(UUID id, String bucket, String etag) {
        jdbc.update("INSERT INTO managed_cv_objects(id, bucket, etag) VALUES (?, ?, ?)", id, bucket, etag);
    }
}
