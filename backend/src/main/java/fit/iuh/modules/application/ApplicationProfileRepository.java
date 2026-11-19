package fit.iuh.modules.application;

import jakarta.persistence.LockModeType;
import org.springframework.data.jpa.repository.*;
import org.springframework.data.repository.query.Param;
import org.springframework.transaction.annotation.Transactional;
import java.util.*;

public interface ApplicationProfileRepository extends JpaRepository<ApplicationProfile, UUID> {
    List<ApplicationProfile> findByUserIdOrderByCreatedAtDesc(UUID userId);

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select p from ApplicationProfile p where p.id = :id")
    Optional<ApplicationProfile> lockById(@Param("id") UUID id);

    @Modifying(clearAutomatically = true, flushAutomatically = true)
    @Transactional
    @Query("update ApplicationProfile p set p.blueprintJson = :blueprintJson where p.id = :id and p.blueprintJson is null")
    int savePrewarmedBlueprintIfAbsent(@Param("id") UUID id, @Param("blueprintJson") String blueprintJson);
}
