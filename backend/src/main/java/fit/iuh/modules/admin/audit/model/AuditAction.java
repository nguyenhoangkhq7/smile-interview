package fit.iuh.modules.admin.audit.model;

public enum AuditAction {
    CREATE_ADMIN(Target.USER),
    CHANGE_USER_ROLE(Target.USER),
    LOCK_USER(Target.USER),
    UNLOCK_USER(Target.USER),
    RESET_PASSWORD(Target.USER),
    RETRY_JOB(Target.SKILL_GAP),
    RETRY_FAILED_JOBS(Target.SKILL_GAP),
    RELEASE_JOB_LEASE(Target.SKILL_GAP),
    PRIORITIZE_JOB(Target.SKILL_GAP),
    UPDATE_POLICY(Target.POLICY),
    RESET_POLICY(Target.POLICY),
    REQUEST_STORAGE_CLEANUP(Target.STORAGE),
    CLEANUP_STORAGE(Target.STORAGE);

    public enum Target {
        USER("USR"), SKILL_GAP("JOB"), POLICY("POL"), STORAGE("STO");

        private final String prefix;

        Target(String prefix) { this.prefix = prefix; }

        public String code(String id) { return "#" + prefix + "-" + id; }
    }

    private final Target target;

    AuditAction(Target target) { this.target = target; }

    public Target target() { return target; }
}
