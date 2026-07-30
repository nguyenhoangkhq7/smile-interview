package fit.iuh.modules.admin.controller;

import fit.iuh.modules.auth.dto.CreateHrUserRequest;
import fit.iuh.modules.auth.dto.CreateHrUserResponse;
import fit.iuh.modules.auth.service.AuthService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Admin controller for user management operations.
 *
 * <p>Exposes endpoints restricted to users with the {@code ROLE_ADMIN} authority.
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/admin/users")
@RequiredArgsConstructor
@PreAuthorize("hasRole('ADMIN')")
public class AdminUserController {

    private final AuthService authService;

    /**
     * Creates a new HR user account.
     *
     * <p>Requires {@code ROLE_ADMIN}. Returns {@code 201 Created} upon successful account creation.
     *
     * @param request the HR account creation payload
     * @return {@code 201 Created} with {@link CreateHrUserResponse} body
     */
    @PostMapping(value = "/hr", consumes = MediaType.APPLICATION_JSON_VALUE, produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<CreateHrUserResponse> createHrUser(@Valid @RequestBody CreateHrUserRequest request) {
        log.info("Admin request to create HR user with username: {}", request.getUsername());
        CreateHrUserResponse response = authService.createHrUser(request);
        return ResponseEntity.status(HttpStatus.CREATED).body(response);
    }
}
