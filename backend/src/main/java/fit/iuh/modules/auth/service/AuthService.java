package fit.iuh.modules.auth.service;

import fit.iuh.common.service.S3StorageService;
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
import fit.iuh.modules.session.entity.Resume;
import fit.iuh.modules.session.repository.ResumeRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;
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
import java.time.LocalDateTime;
import java.util.UUID;

/**
 * Business logic for user registration, authentication, and profile management.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AuthService {

    private final UserRepository userRepository;
    private final ResumeRepository resumeRepository;
    private final S3StorageService s3StorageService;
    private final PasswordEncoder passwordEncoder;
    private final JwtService jwtService;
    private final AuthenticationManager authenticationManager;

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

    public AuthResponse login(LoginRequest request) {
        Authentication auth = authenticationManager.authenticate(
                new UsernamePasswordAuthenticationToken(request.email(), request.password())
        );

        User user = (User) auth.getPrincipal();
        log.info("User logged in: {} ({})", user.getDisplayUsername(), user.getEmail());

        String token = jwtService.generateToken(user);
        return toAuthResponse(token, user);
    }

    @Transactional
    public void changePassword(User user, ChangePasswordRequest request) {
        if (!passwordEncoder.matches(request.currentPassword(), user.getPassword())) {
            throw new BadCredentialsException("Current password is incorrect");
        }

        user.setPassword(passwordEncoder.encode(request.newPassword()));
        userRepository.save(user);
        log.info("Password changed successfully for user: {}", user.getEmail());
    }

    @Transactional
    public User updateProfile(User user, UpdateProfileRequest request) {
        if (request.username() != null && !request.username().isBlank()) {
            user.setUsername(request.username());
        }
        if (request.phoneNumber() != null) {
            user.setPhoneNumber(request.phoneNumber());
        }
        if (request.avatarUrl() != null) {
            user.setAvatarUrl(request.avatarUrl());
        }
        if (request.defaultResumeId() != null) {
            user.setDefaultResumeId(request.defaultResumeId().isBlank()
                    ? null : UUID.fromString(request.defaultResumeId()));
        }

        User updated = userRepository.save(user);
        log.info("Profile updated for user: {}", user.getEmail());
        return updated;
    }

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

    @Transactional
    public Resume uploadAndSetDefaultResume(User user, MultipartFile file) {
        if (file == null || file.isEmpty()) {
            throw new IllegalArgumentException("Resume file is empty");
        }

        String fileName = file.getOriginalFilename() != null ? file.getOriginalFilename() : "cv.pdf";
        String parsedContent = null;
        if (fileName.toLowerCase().endsWith(".pdf")) {
            try (PDDocument document = Loader.loadPDF(file.getBytes())) {
                parsedContent = new PDFTextStripper().getText(document).trim();
            } catch (Exception e) {
                log.warn("[AuthService] Could not extract text from {}: {}", fileName, e.getMessage());
            }
        }

        String fileUrl;
        try {
            String s3Key = "resumes/" + user.getId() + "/" + System.currentTimeMillis() + "_" + fileName;
            fileUrl = s3StorageService.uploadFile(s3Key, file.getBytes(), file.getContentType());
        } catch (Exception e) {
            log.warn("[AuthService] S3 upload skipped or failed: {}", e.getMessage());
            fileUrl = "/uploads/resumes/" + fileName;
        }

        Resume resume = Resume.builder()
                .id(UUID.randomUUID())
                .userId(user.getId())
                .fileName(fileName)
                .fileUrl(fileUrl)
                .rawText(parsedContent)
                .createdAt(LocalDateTime.now())
                .build();

        Resume saved = resumeRepository.save(resume);
        user.setDefaultResumeId(saved.getId());
        userRepository.save(user);

        log.info("Default resume uploaded and set for user {}: resumeId={}", user.getEmail(), saved.getId());
        return saved;
    }

    public AuthResponse toAuthResponse(String token, User user) {
        return new AuthResponse(
                token,
                user.getId(),
                user.getDisplayUsername(),
                user.getEmail(),
                user.getRole() != null ? user.getRole().name() : "USER",
                user.getPhoneNumber(),
                user.getAvatarUrl(),
                user.getDefaultResumeId() != null ? user.getDefaultResumeId().toString() : null
        );
    }
}
