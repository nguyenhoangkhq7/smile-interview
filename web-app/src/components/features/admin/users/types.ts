export type AdminUserRole = 'USER' | 'ADMIN';
export type AdminUserStatus = 'ACTIVE' | 'LOCKED';
export type UserDrawerTabKey = 'sessions' | 'resumes' | 'plans';

export interface UserSessionSummaryItem {
  id: string;
  roleTitle: string;
  scoreLabel: string;
  scoreVariant: 'emerald' | 'blue' | 'neutral';
  competencyText: string;
  durationLabel: string;
  confidencePct: number;
  dateTimeLabel: string;
}

export interface UserResumeSummaryItem {
  id: string;
  fileName: string;
  updatedAt: string;
  fileSize: string;
  matchPct: number;
  iconColorClass: string;
}

export interface UserStudyPlanTask {
  id: string;
  label: string;
  completed: boolean;
}

export interface UserStudyPlanSummary {
  title: string;
  completionPct: number;
  tasks: UserStudyPlanTask[];
}

export interface AdminUserRecord {
  key: string;
  userIdCode: string;
  initials: string;
  fullName: string;
  email: string;
  phone: string;
  resumesCount: number;
  sessionsCount: number;
  avgScoreLabel: string;
  completedTasksRatio: string;
  role: AdminUserRole;
  status: AdminUserStatus;
  joinedDate: string;
  isVerified?: boolean;
  isSelfAccount?: boolean;
  lockReason?: string;
  avatarBgClass: string;
  avatarTextClass: string;
  recentSessions: UserSessionSummaryItem[];
  resumes: UserResumeSummaryItem[];
  studyPlan: UserStudyPlanSummary;
  frequencyDeltaLabel: string;
  frequencyBars: { heightClass: string; colorClass: string; label?: string }[];
}

export interface UsersOverviewStats {
  totalUsers: number;
  totalGrowth: string;
  activeUsers: number;
  activeRatePct: string;
  lockedUsers: number;
  lockedTag: string;
  adminUsers: number;
  adminTag: string;
}
