package fit.iuh.modules.auth.repository;

import fit.iuh.modules.auth.entity.User;
import org.springframework.data.jpa.repository.JpaRepository;
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
}
