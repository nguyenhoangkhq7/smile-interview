import type { AuditActionType, AuditBadgeVariant, AuditRow } from './types';

const dateFormatter = new Intl.DateTimeFormat('vi-VN', {
  timeZone: 'Asia/Ho_Chi_Minh', day: '2-digit', month: '2-digit', year: 'numeric',
});
const timeFormatter = new Intl.DateTimeFormat('vi-VN', {
  timeZone: 'Asia/Ho_Chi_Minh', hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23',
});
const labels = {
  USER: 'Tài khoản', SKILL_GAP: 'Skill Gap Queue', POLICY: 'Cấu hình AI', STORAGE: 'Lưu trữ',
};
const badges: Partial<Record<AuditActionType, AuditBadgeVariant>> = {
  UPDATE_POLICY: 'primary', RESET_POLICY: 'primary', LOCK_USER: 'error', CLEANUP_STORAGE: 'error',
  RETRY_JOB: 'secondary', RETRY_FAILED_JOBS: 'secondary', RELEASE_JOB_LEASE: 'secondary', PRIORITIZE_JOB: 'secondary',
};

export function displayAuditRow(event: AuditRow) {
  const stamp = new Date(event.occurredAt);
  return {
    time: timeFormatter.format(stamp),
    date: dateFormatter.format(stamp),
    initials: event.actorName.trim().split(/\s+/).slice(0, 2)
      .map((part) => Array.from(part)[0] ?? '').join('').toUpperCase(),
    avatar: parseInt(event.actorId.slice(-1), 16) % 2 ? 'bg-[#ad2c00]' : 'bg-[#186392]',
    badge: badges[event.action] ?? 'neutral',
    target: labels[event.targetType] ?? event.targetType,
  };
}
