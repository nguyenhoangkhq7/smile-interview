package fit.iuh.modules.auth.controller;

import fit.iuh.modules.auth.dto.AuthResponse;
import fit.iuh.modules.auth.dto.ChangePasswordRequest;
import fit.iuh.modules.auth.dto.LoginRequest;
import fit.iuh.modules.auth.dto.RegisterRequest;
import fit.iuh.modules.auth.entity.User;
import fit.iuh.modules.auth.service.AuthService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import fit.iuh.modules.auth.dto.UpdateProfileRequest;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

/**
 * REST controller exposing authentication endpoints under {@code /api/auth}.
 *
 * <ul>
 *   <li>{@code POST /api/auth/register}         — register a new user</li>
 *   <li>{@code POST /api/auth/login}             — authenticate and receive a JWT</li>
 *   <li>{@code GET  /api/auth/me}                — return the currently authenticated user profile</li>
 *   <li>{@code POST /api/auth/change-password}   — change password for authenticated user</li>
 * </ul>
 */
@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor
public class AuthController {

    private final AuthService authService;

    // ----------------------------------------------------------------
    // POST /api/auth/register
    // ----------------------------------------------------------------

    /**
     * Registers a new account. Role is always forced to {@code "USER"}.
     *
     * @param request validated registration payload
     * @return {@code 201 Created} with an {@link AuthResponse}
     */
    @PostMapping("/register")
    public ResponseEntity<AuthResponse> register(
            @Valid @RequestBody RegisterRequest request) {

        AuthResponse response = authService.register(request);
        return ResponseEntity.status(HttpStatus.CREATED).body(response);
    }

    // ----------------------------------------------------------------
    // POST /api/auth/login
    // ----------------------------------------------------------------

    /**
     * Authenticates an existing user and returns a JWT.
     *
     * @param request validated login payload
     * @return {@code 200 OK} with an {@link AuthResponse}
     */
    @PostMapping("/login")
    public ResponseEntity<AuthResponse> login(
            @Valid @RequestBody LoginRequest request) {

        AuthResponse response = authService.login(request);
        return ResponseEntity.ok(response);
    }

    // ----------------------------------------------------------------
    // GET /api/auth/me
    // ----------------------------------------------------------------

    /**
     * Returns the full profile of the currently authenticated user.
     * Requires a valid Bearer token in the {@code Authorization} header.
     *
     * @return {@code 200 OK} with an {@link AuthResponse} (token field is null)
     */
    @GetMapping("/me")
    public ResponseEntity<AuthResponse> me() {
        User user = currentUser();
        // token is null here — the client already has it
        return ResponseEntity.ok(authService.toAuthResponse(null, user));
    }

    // ----------------------------------------------------------------
    // POST /api/auth/change-password
    // ----------------------------------------------------------------

    /**
     * Changes the password for the currently authenticated user.
     *
     * @param request validated payload containing currentPassword, newPassword, confirmPassword
     * @return {@code 200 OK} with a success message
     */
    @PostMapping("/change-password")
    public ResponseEntity<Map<String, String>> changePassword(
            @Valid @RequestBody ChangePasswordRequest request) {

        User user = currentUser();
        authService.changePassword(user, request);
        return ResponseEntity.ok(Map.of("message", "Đổi mật khẩu thành công."));
    }

    // ----------------------------------------------------------------
    // PUT /api/auth/profile
    // ----------------------------------------------------------------

    /**
     * Updates profile information (username, phoneNumber, avatarUrl) for the currently authenticated user.
     *
     * @param request validated profile details payload
     * @return {@code 200 OK} with the updated {@link AuthResponse}
     */
    @PutMapping("/profile")
    public ResponseEntity<AuthResponse> updateProfile(
            @Valid @RequestBody UpdateProfileRequest request) {

        User user = currentUser();
        User updated = authService.updateProfile(user, request);
        return ResponseEntity.ok(authService.toAuthResponse(null, updated));
    }

    // ----------------------------------------------------------------
    // POST /api/auth/avatar
    // ----------------------------------------------------------------

    /**
     * Uploads and stores a new profile avatar for the currently authenticated user.
     *
     * @param file the MultipartFile image (JPG, PNG, WebP, GIF)
     * @return {@code 200 OK} with the updated {@link AuthResponse}
     */
    @PostMapping(value = "/avatar", consumes = org.springframework.http.MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<AuthResponse> uploadAvatar(
            @RequestParam("file") MultipartFile file) {

        User user = currentUser();
        User updated = authService.uploadAvatar(user, file);
        return ResponseEntity.ok(authService.toAuthResponse(null, updated));
    }

    // ----------------------------------------------------------------
    // Private helpers
    // ----------------------------------------------------------------

    /** Extracts the authenticated {@link User} from the current security context. */
    private User currentUser() {
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        return (User) authentication.getPrincipal();
    }
}
