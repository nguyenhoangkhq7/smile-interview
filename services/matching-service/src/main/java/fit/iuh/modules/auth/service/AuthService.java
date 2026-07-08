package fit.iuh.modules.auth.service;

import fit.iuh.modules.auth.dto.AuthResponse;
import fit.iuh.modules.auth.dto.ChangePasswordRequest;
import fit.iuh.modules.auth.dto.LoginRequest;
import fit.iuh.modules.auth.dto.RegisterRequest;
import fit.iuh.modules.auth.dto.UpdateProfileRequest;
import fit.iuh.modules.auth.entity.User;
import fit.iuh.modules.auth.repository.UserRepository;
import fit.iuh.modules.auth.security.JwtService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;
import java.util.UUID;

/**
 * Business logic for user registration, authentication, and profile management.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AuthService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtService jwtService;
    private final AuthenticationManager authenticationManager;

    // ----------------------------------------------------------------
    // Register
    // ----------------------------------------------------------------

    /**
     * Registers a new user.
     * The role is always forced to {@code "USER"} — ADMIN accounts must be
     * seeded directly in the database; they cannot be created via this API.
     *
     * @param request the registration payload
     * @return {@link AuthResponse} with a JWT and user details
     * @throws IllegalArgumentException if the email is already taken
     */
    @Transactional
    public AuthResponse register(RegisterRequest request) {
        if (userRepository.existsByEmail(request.email())) {
            throw new IllegalArgumentException(
                    "Email address is already registered: " + request.email());
        }

        User user = User.builder()
                .username(request.username())
                .email(request.email())
                .password(passwordEncoder.encode(request.password()))
                .role("USER")   // ← always forced; client cannot escalate to ADMIN
                .build();

        User saved = userRepository.save(user);
        log.info("New user registered: {} ({})", saved.getDisplayUsername(), saved.getEmail());

        String token = jwtService.generateToken(saved);
        return toAuthResponse(token, saved);
    }

    // ----------------------------------------------------------------
    // Login
    // ----------------------------------------------------------------

    /**
     * Authenticates an existing user via email + password.
     *
     * @param request the login payload
     * @return {@link AuthResponse} with a fresh JWT
     * @throws org.springframework.security.core.AuthenticationException on bad credentials
     */
    public AuthResponse login(LoginRequest request) {
        Authentication auth = authenticationManager.authenticate(
                new UsernamePasswordAuthenticationToken(request.email(), request.password())
        );

        User user = (User) auth.getPrincipal();
        log.info("User logged in: {} ({})", user.getDisplayUsername(), user.getEmail());

        String token = jwtService.generateToken(user);
        return toAuthResponse(token, user);
    }

    // ----------------------------------------------------------------
    // Change Password
    // ----------------------------------------------------------------

    /**
     * Changes the password for the currently authenticated user.
     *
     * <ol>
     *   <li>Verifies {@code currentPassword} against the stored BCrypt hash.</li>
     *   <li>Ensures {@code newPassword} equals {@code confirmPassword}.</li>
     *   <li>Hashes the new password and persists it.</li>
     * </ol>
     *
     * @param user    the currently authenticated user (from SecurityContext)
     * @param request the change-password payload
     * @throws BadCredentialsException  if {@code currentPassword} is wrong
     * @throws IllegalArgumentException if {@code newPassword} ≠ {@code confirmPassword}
     */
    @Transactional
    public void changePassword(User user, ChangePasswordRequest request) {
        if (!passwordEncoder.matches(request.currentPassword(), user.getPassword())) {
            throw new BadCredentialsException("Mật khẩu hiện tại không đúng.");
        }

        if (!request.newPassword().equals(request.confirmPassword())) {
            throw new IllegalArgumentException("Mật khẩu mới và xác nhận mật khẩu không khớp.");
        }

        user.setPassword(passwordEncoder.encode(request.newPassword()));
        userRepository.save(user);
        log.info("Password changed for user: {}", user.getEmail());
    }

    // ----------------------------------------------------------------
    // Profile Management
    // ----------------------------------------------------------------

    /**
     * Updates personal information for the user (username, phoneNumber, avatarUrl).
     */
    @Transactional
    public User updateProfile(User user, UpdateProfileRequest request) {
        user.setUsername(request.username());
        user.setPhoneNumber(request.phoneNumber());
        if (request.avatarUrl() != null && !request.avatarUrl().isBlank()) {
            user.setAvatarUrl(request.avatarUrl());
        }
        User updated = userRepository.save(user);
        log.info("Profile updated for user: {}", user.getEmail());
        return updated;
    }

    /**
     * Handles file upload for the user avatar, saves it locally, and updates user avatar URL.
     */
    @Transactional
    public User uploadAvatar(User user, MultipartFile file) {
        if (file == null || file.isEmpty()) {
            throw new IllegalArgumentException("Tệp tải lên không được để trống.");
        }

        // Validate image format
        String originalFilename = file.getOriginalFilename();
        String extension = "";
        if (originalFilename != null && originalFilename.contains(".")) {
            extension = originalFilename.substring(originalFilename.lastIndexOf(".")).toLowerCase();
        }

        if (!extension.equals(".jpg") && !extension.equals(".jpeg") && 
            !extension.equals(".png") && !extension.equals(".webp") && !extension.equals(".gif")) {
            throw new IllegalArgumentException("Định dạng ảnh không hợp lệ. Chỉ hỗ trợ JPG, PNG, WebP hoặc GIF.");
        }

        try {
            // Ensure target directory exists
            Path uploadDir = Paths.get("uploads/avatars");
            if (!Files.exists(uploadDir)) {
                Files.createDirectories(uploadDir);
            }

            // Generate unique file name
            String uniqueName = user.getId().toString() + "-" + System.currentTimeMillis() + extension;
            Path targetPath = uploadDir.resolve(uniqueName);

            // Copy file to directory
            Files.copy(file.getInputStream(), targetPath, StandardCopyOption.REPLACE_EXISTING);

            // Set the public URL path
            String publicUrl = "/api/auth/avatars/" + uniqueName;
            user.setAvatarUrl(publicUrl);

            User updated = userRepository.save(user);
            log.info("Avatar updated for user: {} -> {}", user.getEmail(), publicUrl);
            return updated;
        } catch (IOException e) {
            log.error("Failed to store avatar file: ", e);
            throw new RuntimeException("Lỗi hệ thống khi tải ảnh lên. Vui lòng thử lại sau.");
        }
    }

    // ----------------------------------------------------------------
    // Helper
    // ----------------------------------------------------------------

    public AuthResponse toAuthResponse(String token, User user) {
        return new AuthResponse(
                token,
                user.getId(),
                user.getDisplayUsername(),
                user.getEmail(),
                user.getRole(),
                user.getPhoneNumber(),
                user.getAvatarUrl(),
                user.getDefaultResumeId()
        );
    }
}
