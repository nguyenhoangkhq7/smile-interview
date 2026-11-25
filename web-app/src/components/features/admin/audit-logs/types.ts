export type AuditActionType =
  | 'UPDATE_POLICY'
  | 'FORCE_CLOSE_SESSION'
  | 'RETRY_JOB'
  | 'LOCK_USER'
  | 'UNLOCK_USER'
  | 'RESET_PASSWORD'
  | 'RELEASE_JOB_LEASE';

export type AuditBadgeVariant = 'primary' | 'error' | 'secondary' | 'neutral';

export interface AuditDiffItem {
  field: string;
  oldValue: string;
  newValue: string;
  description?: string;
}

export interface AuditLogRecord {
  id: string;
  recordCode: string;
  time: string;
  date: string;
  adminName: string;
  adminInitials: string;
  adminRole: string;
  adminIp: string;
  adminAvatarBgClass: string;
  action: AuditActionType;
  badgeVariant: AuditBadgeVariant;
  targetType: string;
  targetCode: string;
  summaryText: string;
  diffs: AuditDiffItem[];
  jsonPayload: Record<string, unknown>;
}
