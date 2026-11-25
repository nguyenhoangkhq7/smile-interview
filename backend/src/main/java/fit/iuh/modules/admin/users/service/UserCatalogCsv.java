package fit.iuh.modules.admin.users.service;

import fit.iuh.modules.admin.users.dto.AdminUserDtos.Summary;

import java.util.List;

import static fit.iuh.common.CsvCell.text;

final class UserCatalogCsv {
    private UserCatalogCsv() {}

    static String format(List<Summary> rows) {
        StringBuilder csv = new StringBuilder("\uFEFFID,Họ tên,Email,Số điện thoại,Vai trò,Trạng thái,Ngày tham gia,Hồ sơ,Phiên\r\n");
        for (Summary user : rows) {
            csv.append(String.join(",", text(user.id().toString()), text(user.fullName()), text(user.email()),
                    text(user.phone()), text(user.role().name()), text(user.status().name()),
                    text(user.joinedAt().toString()), Long.toString(user.profilesCount()),
                    Long.toString(user.sessionsCount()))).append("\r\n");
        }
        return csv.toString();
    }
}
