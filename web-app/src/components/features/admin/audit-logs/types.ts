export const auditActions = [
  'CREATE_ADMIN', 'CHANGE_USER_ROLE', 'LOCK_USER', 'UNLOCK_USER', 'RESET_PASSWORD',
  'RETRY_JOB', 'RETRY_FAILED_JOBS', 'RELEASE_JOB_LEASE', 'PRIORITIZE_JOB',
  'UPDATE_POLICY', 'RESET_POLICY', 'REQUEST_STORAGE_CLEANUP', 'CLEANUP_STORAGE',
] as const;

export type AuditActionType = typeof auditActions[number];
export type AuditBadgeVariant = 'primary' | 'error' | 'secondary' | 'neutral';
export type AuditDatePreset = 'all' | 'today' | '7d' | '1m' | '2m' | 'day' | 'range';

export interface AuditFilter {
  search: string;
  actorId: string;
  action: '' | AuditActionType;
  datePreset: AuditDatePreset;
  date: string;
  fromDate: string;
  toDate: string;
}

export interface AuditActor { id: string; name: string }
export interface AuditStats { total: number; today: number; admins: number }

export interface AuditRow {
  id: string;
  occurredAt: string;
  actorId: string;
  actorName: string;
  action: AuditActionType;
  targetType: 'USER' | 'SKILL_GAP' | 'POLICY' | 'STORAGE';
  targetCode: string;
  summary: string;
}

export interface AuditPage {
  rows: AuditRow[];
  total: number;
  page: number;
  size: number;
  stats: AuditStats;
  actors: AuditActor[];
}

export interface AuditDetail {
  event: AuditRow;
  peerAddress: string | null;
  changes: { field: string; oldValue: string; newValue: string }[];
  details: Record<string, unknown>;
}
