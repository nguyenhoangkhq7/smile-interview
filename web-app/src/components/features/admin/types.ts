export type TimeRangeKey = '7d' | '30d' | '90d' | 'all';

export type AdminSectionKey =
  | 'tong-quan'
  | 'nguoi-dung'
  | 'phien-phong-van'
  | 'hang-doi-va-luu-tru'
  | 'ai-va-chinh-sach'
  | 'nhat-ky-quan-tri';

export interface AdminNavItem {
  key: AdminSectionKey;
  label: string;
  href: string;
  badge?: string;
}

export interface KpiMetricsData {
  totalUsers: number;
  usersGrowth: string;
  usersThisWeek: number;
  usersOnline: number;
  resumesTracked: number;
  resumesGrowth: string;
  interviewsCount: number;
  interviewsGrowth: string;
  interviewsCompleted: number;
  completionRate: number;
  completionRateGrowth: string;
  skillGapJobs: number;
  skillGapSuccessRate: string;
  skillGapSuccessCount: number;
  skillGapFailedCount: number;
  textModePct: number;
  voiceModePct: number;
  textModeCount: number;
  voiceModeCount: number;
}

export interface TelemetryDataPoint {
  label: string;
  x: number;
  cvJdY: number;
  completedY: number;
  cvJdValue: number;
  completedValue: number;
}

export interface TelemetryQuickMetrics {
  peakCvPerDay: number;
  avgProcessingTimeSec: number;
  vectorBandwidthLivePct: number;
}

export interface TerminationSegment {
  id: string;
  label: string;
  percentage: number;
  color: string;
  dotColorClass: string;
}

export interface AiEvalLevelItem {
  code:
    | 'ABOVE_TARGET'
    | 'AT_TARGET'
    | 'BELOW_TARGET'
    | 'NOT_DEMONSTRATED'
    | 'INSUFFICIENT'
    | 'NOT_ASSESSED';
  title: string;
  percentage: number;
  evaluationsCount: number;
  badgeBgClass: string;
  badgeTextClass: string;
  percentTextClass: string;
  barColorClass: string;
  ribbonColorClass: string;
}

export interface EndingReasonItem {
  label: string;
  percentage: number;
  dotColorClass: string;
}

export interface KnowledgeGapItem {
  rank: number;
  title: string;
  percentage: number;
  candidatesCount: number;
  rankTextClass: string;
  barColorClass: string;
}

export interface PopularRoleItem {
  code: string;
  title: string;
  techStack: string;
  count: number;
  growth: string;
  badgeBgClass: string;
  badgeTextClass: string;
  growthTextClass: string;
}

export interface DashboardDataset {
  rangeLabel: string;
  kpi: KpiMetricsData;
  telemetryPoints: TelemetryDataPoint[];
  quickMetrics: TelemetryQuickMetrics;
  terminationSegments: TerminationSegment[];
  aiEvalConfidencePct: number;
  aiEvalF1Score: number;
  aiEvalLevels: AiEvalLevelItem[];
  endingReasons: EndingReasonItem[];
  totalSampleSessions: number;
  knowledgeGaps: KnowledgeGapItem[];
  studyPlanCompletionPct: number;
  avgStudyTasksCompleted: number;
  popularRoles: PopularRoleItem[];
  totalMajorCategoriesCount: number;
}
