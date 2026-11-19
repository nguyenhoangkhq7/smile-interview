package fit.iuh.modules.application;

import jakarta.persistence.LockModeType;
import org.springframework.data.jpa.repository.*;
import org.springframework.data.repository.query.Param;
import org.springframework.transaction.annotation.Transactional;
import java.util.*;

public interface ApplicationProfileRepository extends JpaRepository<ApplicationProfile, UUID> {
    List<ApplicationProfile> findByUserIdOrderByCreatedAtDesc(UUID userId);
    List<ApplicationProfile> findByUserIdAndDeletedAtIsNullOrderByCreatedAtDesc(UUID userId);
    List<ApplicationProfile> findByUserIdAndDeletedAtIsNotNullOrderByDeletedAtDesc(UUID userId);

    @Query("select p from ApplicationProfile p where p.deletedAt <= :cutoff")
    List<ApplicationProfile> findExpired(@Param("cutoff") java.time.LocalDateTime cutoff);

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select p from ApplicationProfile p where p.id = :id")
    Optional<ApplicationProfile> lockById(@Param("id") UUID id);

    @Modifying(clearAutomatically = true, flushAutomatically = true)
    @Transactional
    @Query("delete from ApplicationProfile p where p.id in :ids")
    void deleteByIds(@Param("ids") Collection<UUID> ids);

    @Modifying(clearAutomatically = true, flushAutomatically = true)
    @Transactional
    @Query("update ApplicationProfile p set p.blueprintJson = :blueprintJson where p.id = :id and p.blueprintJson is null")
    int savePrewarmedBlueprintIfAbsent(@Param("id") UUID id, @Param("blueprintJson") String blueprintJson);
}
