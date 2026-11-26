package fit.iuh.modules.admin.users.model;

import fit.iuh.modules.admin.users.dto.AdminUserDtos.Status;
import fit.iuh.modules.auth.entity.Role;

import java.util.Locale;

public record UserCatalogFilter(String search, Role role, Status status) {
    public UserCatalogFilter {
        search = search == null ? "" : search.strip().toLowerCase(Locale.ROOT);
    }
}
