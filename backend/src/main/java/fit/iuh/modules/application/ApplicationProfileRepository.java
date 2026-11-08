package fit.iuh.modules.application;

import jakarta.persistence.LockModeType;
import org.springframework.data.jpa.repository.*;
import org.springframework.data.repository.query.Param;
import java.util.*;

public interface ApplicationProfileRepository extends JpaRepository<ApplicationProfile, UUID> {
    List<ApplicationProfile> findByUserIdOrderByCreatedAtDesc(UUID userId);
    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select p from ApplicationProfile p where p.id = :id")
    Optional<ApplicationProfile> lockById(@Param("id") UUID id);
}
