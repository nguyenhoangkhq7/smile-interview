import {
  QueueKpiStats,
  QueuePrimaryTabKey,
  SkillGapJobItem,
  StorageOverviewData,
} from './types';

export const QUEUE_PRIMARY_TABS: {
  key: QueuePrimaryTabKey;
  label: string;
  badgeCount?: number;
}[] = [
  { key: 'skill-gap-jobs', label: 'Skill Gap Jobs', badgeCount: 14210 },
  { key: 'web-push', label: 'Web Push & Thiết bị', badgeCount: 8420 },
  { key: 'trash-profiles', label: 'Thùng rác hồ sơ', badgeCount: 48 },
  { key: 'storage', label: 'Tổng quan lưu trữ (Storage)' },
];

export const INITIAL_QUEUE_KPI_STATS: QueueKpiStats = {
  pendingCount: 18,
  pendingLatencyText: 'Ước tính trễ: 1.2s',
  runningCount: 6,
  runningCpuLoadText: 'Tải CPU worker: 38%',
  succeededCount: 13956,
  succeededRateText: '98.37% tỷ lệ hoàn tất',
  failedCount: 230,
  failedAlertText: 'Cần can thiệp lại',
};

export const INITIAL_SKILL_GAP_JOBS: SkillGapJobItem[] = [
  {
    id: '#JOB-GAP-9941',
    candidateName: 'Nguyễn Hoàng Nam',
    roleTitle: 'Senior Go Backend Lead',
    status: 'FAILED',
    statusDetail: 'Timeout SBERT 45s (Model node 4)',
    attemptsUsed: 3,
    maxAttempts: 3,
    availableAt: '14:20:10',
    leaseExpiresAt: 'Hết hạn',
    isLeaseExpired: true,
    createdAt: '14:15:00',
  },
  {
    id: '#JOB-GAP-9942',
    candidateName: 'Trần Thị Mai Anh',
    roleTitle: 'Frontend React / Next.js',
    status: 'RUNNING',
    statusDetail: 'Lease ID: lse_99a1_p02',
    attemptsUsed: 1,
    maxAttempts: 3,
    availableAt: '14:22:00',
    leaseExpiresAt: '14:27:00',
    leaseRemainingText: 'còn 4p 18s',
    createdAt: '14:21:40',
  },
  {
    id: '#JOB-GAP-9943',
    candidateName: 'Lê Quốc Bảo',
    roleTitle: 'DevOps SRE & Cloud Ops',
    status: 'SUCCEEDED',
    statusDetail: '4 gap entities mapped',
    attemptsUsed: 1,
    maxAttempts: 3,
    availableAt: '14:18:22',
    leaseExpiresAt: '-',
    createdAt: '14:18:00',
  },
  {
    id: '#JOB-GAP-9944',
    candidateName: 'Vũ Đình Trọng',
    roleTitle: 'Fullstack Node.js & Microservices',
    status: 'PENDING',
    statusDetail: 'Đợi GPU Slot khả dụng',
    attemptsUsed: 0,
    maxAttempts: 3,
    availableAt: '14:25:00',
    leaseExpiresAt: '-',
    createdAt: '14:24:50',
  },
];

export const INITIAL_STORAGE_OVERVIEW: StorageOverviewData = {
  bucketRegion: 'ap-southeast-1',
  totalUsedGb: 148.6,
  totalCapacityGb: 500,
  usedPercentage: 29.7,
  segments: [
    {
      id: 'cv-attachments',
      label: 'Tài liệu CV đính kèm',
      sizeGb: 62.4,
      subLabel: '(PDF/DOCX)',
      widthPct: 12.48,
      colorClass: 'bg-[#ad2c00]',
    },
    {
      id: 'jd-rubric',
      label: 'Job Descriptions & Rubric',
      sizeGb: 18.2,
      widthPct: 3.64,
      colorClass: 'bg-[#186392]',
    },
    {
      id: 'simli-voice',
      label: 'Simli Avatar & Voice Cache',
      sizeGb: 45.8,
      widthPct: 9.16,
      colorClass: 'bg-[#8ccafe]',
    },
    {
      id: 'bytea-cache',
      label: 'PostgreSQL BYTEA Cache',
      sizeGb: 22.2,
      widthPct: 4.44,
      colorClass: 'bg-[#006b2f]',
    },
  ],
  orphanedFilesCount: 34,
  orphanedFilesSizeMb: 186,
  lastSyncedText: '3 phút trước',
  retentionDays: 90,
};
