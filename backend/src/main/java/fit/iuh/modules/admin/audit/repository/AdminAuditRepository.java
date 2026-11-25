package fit.iuh.modules.admin.audit.repository;

import fit.iuh.modules.admin.audit.dto.AdminAuditDtos.*;
import fit.iuh.modules.admin.audit.model.AuditAction;
import fit.iuh.modules.admin.audit.model.AuditAction.Target;
import lombok.RequiredArgsConstructor;
import org.springframework.jdbc.core.PreparedStatementCallback;
import org.springframework.jdbc.core.namedparam.MapSqlParameterSource;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.stereotype.Repository;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import java.util.function.Consumer;

@Repository
@RequiredArgsConstructor
public class AdminAuditRepository {
    private static final ZoneId AUDIT_ZONE = ZoneId.of("Asia/Ho_Chi_Minh");
    private static final String ORDER = " ORDER BY occurred_at DESC, id DESC";
    private static final String ROW = """
            SELECT id, occurred_at, actor_id, actor_name, action, target_type, target_code, summary
            FROM admin_audit_log""";
    private final NamedParameterJdbcTemplate jdbc;

    public void insert(UUID actorId, AuditAction action, String id, String peer, String summary,
                       String changes, String details) {
        var params = new MapSqlParameterSource().addValue("actor", actorId)
                .addValue("peer", peer).addValue("action", action.name())
                .addValue("type", action.target().name()).addValue("code", action.target().code(id))
                .addValue("summary", summary).addValue("changes", changes).addValue("details", details);
        int inserted = jdbc.update("""
                INSERT INTO admin_audit_log(actor_id, actor_name, peer_address, action, target_type,
                                            target_code, summary, changes, details)
                SELECT id, username, :peer, :action, :type, :code, :summary,
                       CAST(:changes AS jsonb), CAST(:details AS jsonb)
                FROM users WHERE id = :actor
                """, params);
        if (inserted != 1) throw new IllegalStateException("Cannot identify audit actor");
    }

    public long count(Filter filter) {
        var query = query(filter);
        return jdbc.queryForObject("SELECT count(*) FROM admin_audit_log" + query.where(), query.params(), Long.class);
    }

    public List<Row> page(Filter filter, long offset, int size) {
        var query = query(filter);
        return jdbc.query(ROW + query.where() + ORDER + " LIMIT :size OFFSET :offset",
                query.params().addValue("size", size).addValue("offset", offset), (rs, index) -> row(rs));
    }

    public Optional<StoredDetail> detail(long id) {
        return jdbc.query("SELECT * FROM admin_audit_log WHERE id = :id",
                new MapSqlParameterSource("id", id),
                (rs, index) -> new StoredDetail(row(rs), rs.getString("peer_address"),
                        rs.getString("changes"), rs.getString("details"))).stream().findFirst();
    }

    public Stats stats() {
        return jdbc.queryForObject("""
                SELECT count(*) AS total, count(*) FILTER (
                    WHERE occurred_at >= date_trunc('day', now(), 'Asia/Ho_Chi_Minh')
                    AND occurred_at < date_trunc('day', now(), 'Asia/Ho_Chi_Minh') + interval '24 hours'
                ) AS today, count(DISTINCT actor_id) AS admins
                FROM admin_audit_log
                """, new MapSqlParameterSource(), (rs, index) -> new Stats(rs.getLong(1), rs.getLong(2), rs.getLong(3)));
    }

    public List<Actor> actors() {
        return jdbc.query("""
                SELECT actor_id, actor_name FROM (
                    SELECT DISTINCT ON (actor_id) actor_id, actor_name
                    FROM admin_audit_log ORDER BY actor_id, occurred_at DESC, id DESC
                ) recent ORDER BY lower(actor_name), actor_id
                """, new MapSqlParameterSource(), (rs, index) -> new Actor(rs.getObject(1, UUID.class), rs.getString(2)));
    }

    public void export(Filter filter, Consumer<Row> consume) {
        var query = query(filter);
        jdbc.execute(ROW + query.where() + ORDER, query.params(),
                (PreparedStatementCallback<Void>) statement -> {
                    statement.setFetchSize(500);
                    try (var results = statement.executeQuery()) {
                        while (results.next()) consume.accept(row(results));
                    }
                    return null;
                });
    }

    private static Row row(ResultSet rs) throws SQLException {
        return new Row(rs.getString("id"), rs.getObject("occurred_at", OffsetDateTime.class).toInstant(),
                rs.getObject("actor_id", UUID.class), rs.getString("actor_name"),
                AuditAction.valueOf(rs.getString("action")), Target.valueOf(rs.getString("target_type")),
                rs.getString("target_code"), rs.getString("summary"));
    }

    private static Query query(Filter filter) {
        var params = new MapSqlParameterSource();
        var where = new ArrayList<String>();
        if (filter.actorId() != null) {
            where.add("actor_id = :actor");
            params.addValue("actor", filter.actorId());
        }
        if (filter.action() != null) {
            where.add("action = :action");
            params.addValue("action", filter.action().name());
        }
        if (filter.from() != null) {
            where.add("occurred_at >= :from");
            params.addValue("from", filter.from().atStartOfDay(AUDIT_ZONE).toOffsetDateTime());
        }
        if (filter.to() != null) {
            where.add("occurred_at < :toExclusive");
            params.addValue("toExclusive", filter.to().plusDays(1).atStartOfDay(AUDIT_ZONE).toOffsetDateTime());
        }
        if (!filter.search().isBlank()) {
            where.add("""
                    (strpos(lower(target_code), lower(:search)) > 0
                     OR strpos(lower(summary), lower(:search)) > 0
                     OR strpos(lower(actor_name), lower(:search)) > 0
                     OR strpos(lower(action), lower(:search)) > 0
                     OR strpos(lower(details ->> 'reason'), lower(:search)) > 0)
                    """);
            params.addValue("search", filter.search().strip());
        }
        return new Query(where.isEmpty() ? "" : " WHERE " + String.join(" AND ", where), params);
    }

    private record Query(String where, MapSqlParameterSource params) {}
    public record StoredDetail(Row event, String peerAddress, String changes, String details) {}
}
