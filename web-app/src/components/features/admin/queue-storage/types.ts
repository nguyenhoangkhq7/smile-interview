export type QueueJobStatus = 'FAILED' | 'RUNNING' | 'SUCCEEDED' | 'PENDING';

export interface SkillGapJobItem {
  id: string;
  candidateName: string;
  roleTitle: string | null;
  sessionId: string;
  status: QueueJobStatus;
  attempts: number;
  createdAt: string;
  availableAt: string;
  claimedAt: string | null;
  leaseUntil: string | null;
  claimToken: string | null;
  finishedAt: string | null;
  failureCode: string | null;
  prioritized: boolean;
}

export interface QueueKpiStats {
  pendingCount: number;
  runningCount: number;
  succeededCount: number;
  failedCount: number;
}

export interface AdminQueuePage {
  jobs: SkillGapJobItem[];
  stats: QueueKpiStats;
  page: number;
  size: number;
  total: number;
  maxAttempts: number;
}

export interface QueueJobDetail {
  job: SkillGapJobItem;
  skillCount: number | null;
  matchingScore: number | null;
  degraded: boolean | null;
}

export interface StorageOverviewData {
  totalBytes: number;
  quotaBytes: number | null;
  segments: { code: string; bytes: number }[];
  s3Available: boolean;
  complete: boolean;
  orphans: { ids: string[]; bytes: number; minimumAgeHours: number } | null;
  cleanupBatchSize: number;
  measuredAt: string;
}

export interface StorageCleanupResult {
  deleted: number;
  skipped: number;
  failed: number;
}
