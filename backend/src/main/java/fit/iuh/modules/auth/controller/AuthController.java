package fit.iuh.modules.auth.controller;

import fit.iuh.modules.auth.dto.AuthResponse;
import fit.iuh.modules.auth.dto.ChangePasswordRequest;
import fit.iuh.modules.auth.dto.LoginRequest;
import fit.iuh.modules.auth.dto.RegisterRequest;
import fit.iuh.modules.auth.dto.UpdateProfileRequest;
import fit.iuh.modules.auth.entity.User;
import fit.iuh.modules.auth.service.AuthService;
import fit.iuh.modules.session.entity.Resume;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.Map;

/**
 * REST controller exposing authentication endpoints under {@code /api/auth}.
 *
 * <ul>
 *   <li>{@code POST /api/auth/register}         — register a new user</li>
 *   <li>{@code POST /api/auth/login}             — authenticate and receive a JWT</li>
 *   <li>{@code GET  /api/auth/me}                — return the currently authenticated user profile</li>
 *   <li>{@code POST /api/auth/change-password}   — change password for authenticated user</li>
 *   <li>{@code PUT  /api/auth/profile}           — update user profile details</li>
 *   <li>{@code POST /api/auth/avatar}            — upload a new profile avatar</li>
 *   <li>{@code POST /api/auth/default-resume}    — upload and set a new default CV</li>
 * </ul>
 */
@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor
public class AuthController {

    private final AuthService authService;

    @PostMapping("/register")
    public ResponseEntity<AuthResponse> register(
            @Valid @RequestBody RegisterRequest request) {

        AuthResponse response = authService.register(request);
        return ResponseEntity.status(HttpStatus.CREATED).body(response);
    }

    @PostMapping("/login")
    public ResponseEntity<AuthResponse> login(
            @Valid @RequestBody LoginRequest request) {

        AuthResponse response = authService.login(request);
        return ResponseEntity.ok(response);
    }

    @GetMapping("/me")
    public ResponseEntity<AuthResponse> me() {
        User user = currentUser();
        return ResponseEntity.ok(authService.toAuthResponse(null, user));
    }

    @PostMapping("/change-password")
    public ResponseEntity<Map<String, String>> changePassword(
            @Valid @RequestBody ChangePasswordRequest request) {

        User user = currentUser();
        authService.changePassword(user, request);
        return ResponseEntity.ok(Map.of("message", "Đổi mật khẩu thành công."));
    }

    @PutMapping("/profile")
    public ResponseEntity<AuthResponse> updateProfile(
            @Valid @RequestBody UpdateProfileRequest request) {

        User user = currentUser();
        User updated = authService.updateProfile(user, request);
        return ResponseEntity.ok(authService.toAuthResponse(null, updated));
    }

    @PostMapping(value = "/avatar", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<AuthResponse> uploadAvatar(
            @RequestParam("file") MultipartFile file) {

        User user = currentUser();
        User updated = authService.uploadAvatar(user, file);
        return ResponseEntity.ok(authService.toAuthResponse(null, updated));
    }

    @PostMapping(value = "/default-resume", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<Map<String, Object>> uploadDefaultResume(
            @RequestParam("file") MultipartFile file) {

        User user = currentUser();
        Resume savedResume = authService.uploadAndSetDefaultResume(user, file);
        return ResponseEntity.ok(Map.of(
                "success", true,
                "defaultResumeId", savedResume.getId().toString(),
                "resume", savedResume
        ));
    }

    private User currentUser() {
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        return (User) authentication.getPrincipal();
    }
}
