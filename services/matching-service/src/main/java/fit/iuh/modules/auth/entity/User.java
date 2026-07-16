package fit.iuh.modules.auth.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.userdetails.UserDetails;

import java.time.LocalDateTime;
import java.util.Collection;
import java.util.List;
import java.util.UUID;

/**
 * JPA entity for the {@code users} table.
 * Implements {@link UserDetails} so Spring Security can use it directly.
 */
@Entity
@Table(name = "users")
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class User implements UserDetails {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "id", updatable = false, nullable = false)
    private UUID id;

    @Column(name = "username", nullable = false)
    private String username;

    @Column(name = "email", unique = true, nullable = false)
    private String email;

    /**
     * Mapped to the {@code password_hash} column in the DB.
     */
    @Column(name = "password_hash", nullable = false)
    private String password;

    @Column(name = "role", nullable = false)
    private String role;

    @Column(name = "phone_number")
    private String phoneNumber;

    @Column(name = "avatar_url")
    private String avatarUrl;

    /**
     * Reference to the user's default resume (FK to resumes table).
     * Stored as a plain String — no JPA join to avoid cross-module coupling.
     */
    @Column(name = "default_resume_id")
    private String defaultResumeId;

    @Column(name = "created_at", updatable = false)
    private LocalDateTime createdAt;

    // ----------------------------------------------------------------
    // Lifecycle
    // ----------------------------------------------------------------

    @PrePersist
    protected void onCreate() {
        if (createdAt == null) {
            createdAt = LocalDateTime.now();
        }
    }

    // ----------------------------------------------------------------
    // UserDetails implementation
    // ----------------------------------------------------------------

    @Override
    public Collection<? extends GrantedAuthority> getAuthorities() {
        return List.of(new SimpleGrantedAuthority("ROLE_" + role));
    }

    /** Returns the BCrypt-hashed password (stored in {@code password_hash}). */
    @Override
    public String getPassword() {
        return password;
    }

    /** Returns the email; used as the principal name for authentication. */
    @Override
    public String getUsername() {
        return email;
    }

    @Override
    public boolean isAccountNonExpired() {
        return true;
    }

    @Override
    public boolean isAccountNonLocked() {
        return true;
    }

    @Override
    public boolean isCredentialsNonExpired() {
        return true;
    }

    @Override
    public boolean isEnabled() {
        return true;
    }

    /**
     * Convenience method — returns the display username (not the email principal).
     */
    public String getDisplayUsername() {
        return username;
    }
}
