package fit.iuh.modules.auth.repository;

import fit.iuh.modules.auth.entity.User;
import jakarta.persistence.LockModeType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.Optional;
import java.util.UUID;

/**
 * Spring Data JPA repository for {@link User}.
 */
@Repository
public interface UserRepository extends JpaRepository<User, UUID> {

    /**
     * Look up a user by their email address (used as the login principal).
     *
     * @param email the unique email of the user
     * @return an {@link Optional} containing the user if found
     */
    Optional<User> findByEmail(String email);

    /**
     * Check whether a user with the given email already exists.
     *
     * @param email the email to check
     * @return {@code true} if a record exists
     */
    boolean existsByEmail(String email);

    boolean existsByEmailIgnoreCase(String email);

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("SELECT u FROM User u WHERE u.id = :id")
    Optional<User> findForUpdate(@Param("id") UUID id);
}
