package fit.iuh.modules.study.repository;

import fit.iuh.modules.study.dto.StudyPlanDtos.Attachment;
import fit.iuh.modules.study.dto.StudyPlanDtos.ChecklistInput;
import fit.iuh.modules.study.dto.StudyPlanDtos.GapOriginInput;
import fit.iuh.modules.study.dto.StudyPlanDtos.PlanInput;
import fit.iuh.modules.study.dto.StudyPlanDtos.PlanTotals;
import fit.iuh.modules.study.dto.StudyPlanDtos.ResourceInput;
import fit.iuh.modules.study.dto.StudyPlanDtos.TaskInput;
import fit.iuh.modules.study.entity.StudyPlan;
import fit.iuh.modules.study.entity.StudyTask;
import fit.iuh.modules.study.entity.StudyTaskChecklistItem;
import fit.iuh.modules.study.entity.StudyTaskResource;
import lombok.RequiredArgsConstructor;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Objects;
import java.util.Optional;
import java.util.UUID;

@Repository
@RequiredArgsConstructor
public class StudyPlanRepository {
    private static final String RESOURCE_FIELDS = "id, task_id, title, url, file_name, created_at";
    private final JdbcClient jdbc;

    public Optional<StudyPlan> findActive(UUID profileId) {
        return jdbc.sql("SELECT * FROM study_plans WHERE application_profile_id = :profile AND status = 'ACTIVE'")
                .param("profile", profileId).query(StudyPlan.class).optional();
    }

    public List<PlanTotals> totalsForUser(UUID userId) {
        return jdbc.sql("""
                SELECT p.application_profile_id, count(t.id) FILTER (WHERE t.status = 'DONE') AS done,
                    count(t.id) AS total, p.target_completion_percent
                FROM study_plans p JOIN application_profiles a ON a.id = p.application_profile_id
                LEFT JOIN study_tasks t ON t.plan_id = p.id
                WHERE a.user_id = :user AND p.status = 'ACTIVE'
                GROUP BY p.id
                """).param("user", userId).query(PlanTotals.class).list();
    }

    public StudyPlan createPlan(UUID profileId, String title) {
        return jdbc.sql("INSERT INTO study_plans (application_profile_id, title) VALUES (:profile, :title) RETURNING *")
                .param("profile", profileId).param("title", title).query(StudyPlan.class).single();
    }

    public StudyPlan updatePlan(long planId, PlanInput input) {
        return jdbc.sql("""
                UPDATE study_plans SET title = :title, description = :description, target_date = :targetDate,
                    target_completion_percent = :target, source_session_id = :source, updated_at = CURRENT_TIMESTAMP
                WHERE id = :id RETURNING *
                """).param("title", input.title().strip()).param("description", input.description())
                .param("targetDate", input.targetDate()).param("target", input.targetCompletionPercent())
                .param("source", input.sourceSessionId()).param("id", planId).query(StudyPlan.class).single();
    }

    public List<StudyTask> tasks(long planId) {
        return jdbc.sql("SELECT * FROM study_tasks WHERE plan_id = :plan ORDER BY sort_order, id")
                .param("plan", planId).query(StudyTask.class).list();
    }

    public List<StudyTaskChecklistItem> checklist(long planId) {
        return jdbc.sql("""
                SELECT c.* FROM study_task_checklist_items c JOIN study_tasks t ON t.id = c.task_id
                WHERE t.plan_id = :plan ORDER BY c.sort_order, c.id
                """).param("plan", planId).query(StudyTaskChecklistItem.class).list();
    }

    public List<StudyTaskResource> resources(long planId) {
        return jdbc.sql("""
                SELECT r.id, r.task_id, r.title, r.url, r.file_name, r.created_at
                FROM study_task_resources r JOIN study_tasks t ON t.id = r.task_id
                WHERE t.plan_id = :plan ORDER BY r.id
                """).param("plan", planId).query(StudyTaskResource.class).list();
    }

    public boolean hasTask(long planId, long taskId) {
        return jdbc.sql("SELECT EXISTS(SELECT 1 FROM study_tasks WHERE plan_id = :plan AND id = :task)")
                .param("plan", planId).param("task", taskId).query(Boolean.class).single();
    }

    public StudyTask createTask(long planId, TaskInput input, Long parentTaskId, GapOriginInput gapOrigin) {
        return taskFields("""
                INSERT INTO study_tasks (plan_id, parent_task_id, title, skill_id, notes, status, sort_order, completed_at,
                    gap_source_skill_id, gap_source_session_id, gap_source_attempt_number)
                VALUES (:plan, :parent, :title, :skill, :notes, :status, :sort,
                    CASE WHEN :status = 'DONE' THEN CURRENT_TIMESTAMP END,
                    :gapSkill, :gapSession, :gapAttempt)
                RETURNING *
                """, input).param("plan", planId).param("parent", parentTaskId)
                .param("gapSkill", gapOrigin == null ? null : gapOrigin.skillId())
                .param("gapSession", gapOrigin == null ? null : gapOrigin.sessionId())
                .param("gapAttempt", gapOrigin == null ? null : gapOrigin.attemptNumber())
                .query(StudyTask.class).single();
    }

    public Optional<StudyTask> updateTask(long planId, long taskId, TaskInput input) {
        return taskFields("""
                UPDATE study_tasks SET title = :title, skill_id = :skill, notes = :notes, status = :status,
                    sort_order = :sort, updated_at = CURRENT_TIMESTAMP,
                    completed_at = CASE WHEN :status = 'DONE' THEN COALESCE(completed_at, CURRENT_TIMESTAMP) END
                WHERE plan_id = :plan AND id = :task RETURNING *
                """, input).param("plan", planId).param("task", taskId).query(StudyTask.class).optional();
    }

    public boolean updateTaskParent(long planId, long taskId, Long parentTaskId, String status) {
        return jdbc.sql("""
                UPDATE study_tasks SET parent_task_id = :parent,
                    status = COALESCE(:status, status), updated_at = CURRENT_TIMESTAMP,
                    completed_at = CASE WHEN :status = 'DONE' THEN COALESCE(completed_at, CURRENT_TIMESTAMP)
                                        WHEN :status IN ('TODO', 'IN_PROGRESS') THEN NULL ELSE completed_at END
                WHERE plan_id = :plan AND id = :task
                """)
                .param("parent", parentTaskId).param("status", status).param("plan", planId).param("task", taskId).update() == 1;
    }

    private JdbcClient.StatementSpec taskFields(String sql, TaskInput input) {
        return jdbc.sql(sql).param("title", input.title().strip()).param("skill", input.skillId())
                .param("notes", input.notes()).param("status", input.status())
                .param("sort", Objects.requireNonNullElse(input.sortOrder(), 0));
    }

    public void moveTask(long planId, long taskId, String status, int sortOrder) {
        jdbc.sql("""
                UPDATE study_tasks SET status = :status, sort_order = :sort, updated_at = CURRENT_TIMESTAMP,
                    completed_at = CASE WHEN :status = 'DONE' THEN COALESCE(completed_at, CURRENT_TIMESTAMP) END
                WHERE plan_id = :plan AND id = :task
                """).param("plan", planId).param("task", taskId).param("status", status).param("sort", sortOrder).update();
    }

    public boolean deleteTask(long planId, long taskId) {
        return jdbc.sql("DELETE FROM study_tasks WHERE plan_id = :plan AND id = :task")
                .param("plan", planId).param("task", taskId).update() == 1;
    }

    public StudyTaskChecklistItem createChecklistItem(long taskId, ChecklistInput input) {
        return checklistFields("""
                INSERT INTO study_task_checklist_items (task_id, content, is_completed, sort_order, completed_at)
                VALUES (:task, :content, :completed, :sort, CASE WHEN :completed THEN CURRENT_TIMESTAMP END)
                RETURNING *
                """, taskId, input).query(StudyTaskChecklistItem.class).single();
    }

    public Optional<StudyTaskChecklistItem> updateChecklistItem(long taskId, long itemId, ChecklistInput input) {
        return checklistFields("""
                UPDATE study_task_checklist_items SET content = :content, is_completed = :completed,
                    sort_order = :sort, updated_at = CURRENT_TIMESTAMP,
                    completed_at = CASE WHEN :completed THEN COALESCE(completed_at, CURRENT_TIMESTAMP) END
                WHERE task_id = :task AND id = :id RETURNING *
                """, taskId, input).param("id", itemId).query(StudyTaskChecklistItem.class).optional();
    }

    private JdbcClient.StatementSpec checklistFields(String sql, long taskId, ChecklistInput input) {
        return jdbc.sql(sql).param("task", taskId).param("content", input.content().strip())
                .param("completed", Boolean.TRUE.equals(input.isCompleted()))
                .param("sort", Objects.requireNonNullElse(input.sortOrder(), 0));
    }

    public boolean deleteChecklistItem(long taskId, long itemId) {
        return jdbc.sql("DELETE FROM study_task_checklist_items WHERE task_id = :task AND id = :id")
                .param("task", taskId).param("id", itemId).update() == 1;
    }

    public StudyTaskResource createResource(long taskId, String title, String url, String fileName, byte[] fileData) {
        return jdbc.sql("""
                INSERT INTO study_task_resources (task_id, title, url, file_name, file_data)
                VALUES (:task, :title, :url, :fileName, :fileData)
                RETURNING
                """ + RESOURCE_FIELDS).param("task", taskId).param("title", title).param("url", url)
                .param("fileName", fileName).param("fileData", fileData).query(StudyTaskResource.class).single();
    }

    public Optional<StudyTaskResource> updateLink(long taskId, long resourceId, ResourceInput input) {
        return jdbc.sql("""
                UPDATE study_task_resources SET title = :title, url = :url
                WHERE task_id = :task AND id = :id AND url IS NOT NULL RETURNING
                """ + RESOURCE_FIELDS).param("task", taskId).param("id", resourceId)
                .param("title", input.title().strip()).param("url", input.url().strip()).query(StudyTaskResource.class).optional();
    }

    public boolean deleteResource(long taskId, long resourceId) {
        return jdbc.sql("DELETE FROM study_task_resources WHERE task_id = :task AND id = :id")
                .param("task", taskId).param("id", resourceId).update() == 1;
    }

    public Optional<Attachment> attachment(long planId, long taskId, long resourceId) {
        return jdbc.sql("""
                SELECT r.file_name, r.file_data FROM study_task_resources r JOIN study_tasks t ON t.id = r.task_id
                WHERE t.plan_id = :plan AND r.task_id = :task AND r.id = :id AND r.file_data IS NOT NULL
                """).param("plan", planId).param("task", taskId).param("id", resourceId).query(Attachment.class).optional();
    }
}
