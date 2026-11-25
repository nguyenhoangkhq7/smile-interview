package fit.iuh.modules.admin.users.service;

import fit.iuh.modules.admin.audit.dto.AdminAuditDtos.Change;
import fit.iuh.modules.admin.audit.service.AdminAuditService;
import fit.iuh.modules.admin.users.dto.AdminUserDtos.*;
import fit.iuh.modules.admin.users.model.UserCatalogFilter;
import fit.iuh.modules.admin.users.repository.AdminUserReadRepository;
import fit.iuh.modules.auth.dto.PasswordSetupDtos.Link;
import fit.iuh.modules.auth.entity.Role;
import fit.iuh.modules.auth.entity.User;
import fit.iuh.modules.auth.repository.UserRepository;
import fit.iuh.modules.auth.service.PasswordSetupService;
import lombok.RequiredArgsConstructor;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Isolation;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.time.Instant;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;

import static fit.iuh.modules.admin.audit.model.AuditAction.*;

@Service
@RequiredArgsConstructor
public class AdminUsersService {
    private final AdminUserReadRepository read;
    private final UserRepository users;
    private final JdbcTemplate jdbc;
    private final PasswordEncoder encoder;
    private final PasswordSetupService passwordSetup;
    private final AdminAuditService audit;

    @Transactional(readOnly = true, isolation = Isolation.REPEATABLE_READ)
    public Page list(UUID actor, UserCatalogFilter filter, int page, int size) {
        long total = read.count(filter);
        int lastPage = (int) Math.min(Integer.MAX_VALUE, Math.max(1, (total + size - 1) / size));
        int selected = Math.min(page, lastPage);
        return new Page(read.page(filter, actor, selected, size), total, selected, size, read.stats());
    }

    @Transactional(readOnly = true, isolation = Isolation.REPEATABLE_READ)
    public Detail detail(UUID actor, UUID id) {
        var summary = read.summary(id, actor).orElseThrow(AdminUsersService::missing);
        return new Detail(summary, read.recentInterviews(id), read.recentProfiles(id), read.activePlans(id));
    }

    @Transactional(readOnly = true)
    public String export(UUID actor, UserCatalogFilter filter) {
        return UserCatalogCsv.format(read.export(filter, actor));
    }

    @Transactional
    public Link create(UUID actor, Create request) {
        authorizeMutation(actor);
        String email = request.email().strip().toLowerCase(Locale.ROOT);
        if (users.existsByEmailIgnoreCase(email)) throw duplicate();
        User created = User.builder().username(request.fullName().strip()).email(email)
                .password(encoder.encode(UUID.randomUUID().toString())).role(Role.ADMIN).build();
        try {
            users.saveAndFlush(created);
        } catch (DataIntegrityViolationException ex) {
            throw duplicate();
        }
        var link = passwordSetup.issue(created.getId());
        audit.record(actor, CREATE_ADMIN, created.getId(), "Tạo tài khoản quản trị viên.",
                List.of(new Change("role", "—", Role.ADMIN.name())), Map.of());
        return link;
    }

    @Transactional
    public void changeStatus(UUID actor, UUID id, ChangeStatus request) {
        User target = target(actor, id);
        boolean lock = request.status() == Status.LOCKED;
        if (lock == !target.isAccountNonLocked()) return;
        target.setLockedAt(lock ? Instant.now() : null);
        target.setLockReason(lock && request.reason() != null ? request.reason().strip() : null);
        revokeCredentials(target);
        String reason = target.getLockReason();
        audit.record(actor, lock ? LOCK_USER : UNLOCK_USER, id, lock ? "Khóa tài khoản." : "Mở khóa tài khoản.",
                List.of(new Change("status", lock ? "ACTIVE" : "LOCKED", lock ? "LOCKED" : "ACTIVE")),
                reason == null || reason.isBlank() ? Map.of() : Map.of("reason", reason));
    }

    @Transactional
    public Link resetPassword(UUID actor, UUID id) {
        var link = passwordSetup.issue(target(actor, id).getId());
        audit.record(actor, RESET_PASSWORD, id, "Tạo liên kết đặt lại mật khẩu.");
        return link;
    }

    private User target(UUID actor, UUID id) {
        authorizeMutation(actor);
        if (actor.equals(id)) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Không thể tự khóa hoặc đặt lại mật khẩu tại đây.");
        }
        return users.findForUpdate(id).orElseThrow(AdminUsersService::missing);
    }

    private void authorizeMutation(UUID actor) {
        // Serialize admin mutations so two admins cannot concurrently disable each other's access.
        jdbc.execute("SELECT pg_advisory_xact_lock(68412704)");
        var current = users.findById(actor).orElseThrow(AdminUsersService::missing);
        if (current.getRole() != Role.ADMIN || !current.isAccountNonLocked()) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Quyền quản trị đã thay đổi.");
        }
    }

    private void revokeCredentials(User target) {
        target.setTokenVersion(target.getTokenVersion() + 1);
        jdbc.update("DELETE FROM user_password_setup_tokens WHERE user_id = ?", target.getId());
    }

    private static ResponseStatusException duplicate() {
        return new ResponseStatusException(HttpStatus.CONFLICT, "Email đã được sử dụng.");
    }

    private static ResponseStatusException missing() {
        return new ResponseStatusException(HttpStatus.NOT_FOUND, "Không tìm thấy tài khoản.");
    }
}
