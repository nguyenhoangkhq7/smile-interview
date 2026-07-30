package fit.iuh.modules.auth.service;

import fit.iuh.modules.auth.dto.AuthResponse;
import fit.iuh.modules.auth.dto.ChangePasswordRequest;
import fit.iuh.modules.auth.dto.CreateHrUserRequest;
import fit.iuh.modules.auth.dto.CreateHrUserResponse;
import fit.iuh.modules.auth.dto.LoginRequest;
import fit.iuh.modules.auth.dto.RegisterRequest;
import fit.iuh.modules.auth.dto.UpdateProfileRequest;
import fit.iuh.modules.auth.entity.Role;
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
     * The role is forced to {@code Role.USER} / {@code Role.CANDIDATE}.
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
                .role(Role.USER)
                .build();

        User saved = userRepository.save(user);
        log.info("New user registered: {} ({})", saved.getDisplayUsername(), saved.getEmail());

        String token = jwtService.generateToken(saved);
        return toAuthResponse(token, saved);
    }

    /**
     * Creates a new HR user account (Admin only).
     *
     * @param request the HR account creation payload
     * @return {@link CreateHrUserResponse} with account creation confirmation
     */
    @Transactional
    public CreateHrUserResponse createHrUser(CreateHrUserRequest request) {
        String targetEmail = (request.getEmail() != null && !request.getEmail().isBlank())
                ? request.getEmail()
                : (request.getUsername().contains("@") ? request.getUsername() : request.getUsername() + "@hr.smile.com");

        if (userRepository.existsByEmail(targetEmail)) {
            throw new IllegalArgumentException("User with email/username already exists: " + targetEmail);
        }

        String displayName = (request.getEvaluatorName() != null && !request.getEvaluatorName().isBlank())
                ? request.getEvaluatorName()
                : request.getUsername();

        User user = User.builder()
                .username(displayName)
                .email(targetEmail)
                .password(passwordEncoder.encode(request.getPassword()))
                .role(Role.HR)
                .build();

        User saved = userRepository.save(user);
        log.info("Admin created new HR user: {} ({}) with ID: {}", saved.getDisplayUsername(), saved.getEmail(), saved.getId());

        return CreateHrUserResponse.builder()
                .id(saved.getId())
                .username(request.getUsername())
                .email(saved.getEmail())
                .evaluatorName(displayName)
                .role(saved.getRole())
                .createdAt(saved.getCreatedAt())
                .message("HR account created successfully.")
                .build();
    }

    // ----------------------------------------------------------------
    // Login
    // ----------------------------------------------------------------

    /**
     * Authenticates an existing user via email + password.
     *
     * @param request the login payload
     * @return {@link AuthResponse} with a fresh JWT
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

    @Transactional
    public void changePassword(User user, ChangePasswordRequest request) {
        if (!passwordEncoder.matches(request.currentPassword(), user.getPassword())) {
            throw new BadCredentialsException("Current password is incorrect");
        }

        user.setPassword(passwordEncoder.encode(request.newPassword()));
        userRepository.save(user);
        log.info("Password changed successfully for user: {}", user.getEmail());
    }

    // ----------------------------------------------------------------
    // Update Profile
    // ----------------------------------------------------------------

    @Transactional
    public User updateProfile(User user, UpdateProfileRequest request) {
        if (request.username() != null && !request.username().isBlank()) {
            user.setUsername(request.username());
        }

        User updated = userRepository.save(user);
        log.info("Profile updated for user: {}", user.getEmail());
        return updated;
    }

    // ----------------------------------------------------------------
    // Upload Avatar
    // ----------------------------------------------------------------

    @Transactional
    public User uploadAvatar(User user, MultipartFile file) {
        if (file.isEmpty()) {
            throw new IllegalArgumentException("Avatar file is empty");
        }

        try {
            String filename = "avatar_" + user.getId() + "_" + System.currentTimeMillis() + ".jpg";
            Path uploadDir = Paths.get("uploads/avatars");
            if (!Files.exists(uploadDir)) {
                Files.createDirectories(uploadDir);
            }
            Path filePath = uploadDir.resolve(filename);
            Files.copy(file.getInputStream(), filePath, StandardCopyOption.REPLACE_EXISTING);

            user.setAvatarUrl("/uploads/avatars/" + filename);
            User updated = userRepository.save(user);
            log.info("Avatar uploaded for user: {}", user.getEmail());
            return updated;
        } catch (IOException e) {
            log.error("Failed to store avatar file", e);
            throw new RuntimeException("Failed to store avatar file", e);
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
                user.getRole() != null ? user.getRole().name() : "USER",
                user.getPhoneNumber(),
                user.getAvatarUrl(),
                user.getDefaultResumeId()
        );
    }
}
