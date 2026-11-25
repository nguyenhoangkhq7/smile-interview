export type QueuePrimaryTabKey = 'skill-gap-jobs' | 'web-push' | 'trash-profiles' | 'storage';

export type QueueJobStatus = 'FAILED' | 'RUNNING' | 'SUCCEEDED' | 'PENDING';

export interface SkillGapJobItem {
  id: string;
  candidateName: string;
  roleTitle: string;
  status: QueueJobStatus;
  statusDetail: string;
  attemptsUsed: number;
  maxAttempts: number;
  availableAt: string;
  leaseExpiresAt: string;
  leaseRemainingText?: string;
  isLeaseExpired?: boolean;
  createdAt: string;
}

export interface QueueKpiStats {
  pendingCount: number;
  pendingLatencyText: string;
  runningCount: number;
  runningCpuLoadText: string;
  succeededCount: number;
  succeededRateText: string;
  failedCount: number;
  failedAlertText: string;
}

export interface StorageSegmentItem {
  id: string;
  label: string;
  sizeGb: number;
  subLabel?: string;
  widthPct: number;
  colorClass: string;
}

export interface StorageOverviewData {
  bucketRegion: string;
  totalUsedGb: number;
  totalCapacityGb: number;
  usedPercentage: number;
  segments: StorageSegmentItem[];
  orphanedFilesCount: number;
  orphanedFilesSizeMb: number;
  lastSyncedText: string;
  retentionDays: number;
}
