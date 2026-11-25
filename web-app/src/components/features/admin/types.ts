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
}

export interface KpiMetricsData {
  users: number;
  usersGrowth: number | null;
  applicationProfiles: number;
  applicationProfilesGrowth: number | null;
  interviews: number;
  completedInterviews: number;
  interviewsGrowth: number | null;
  completionRate: number | null;
  completionRateChange: number | null;
  skillGapJobs: number;
  successfulSkillGapJobs: number;
  skillGapSuccessRate: number | null;
  textInterviews: number;
  voiceInterviews: number;
}

export interface TelemetryDataPoint {
  from: string;
  through: string;
  analyses: number;
  completedInterviews: number;
}

export interface DistributionItem {
  code: string;
  count: number;
  percentage: number;
}

export interface KnowledgeGapItem {
  title: string;
  candidates: number;
  percentage: number;
}

export interface PopularRoleItem {
  title: string;
  interviews: number;
  growth: number | null;
}

export interface AdminOverviewData {
  kpis: KpiMetricsData;
  telemetry: TelemetryDataPoint[];
  termination: DistributionItem[];
  assessments: DistributionItem[];
  knowledgeGaps: KnowledgeGapItem[];
  popularRoles: PopularRoleItem[];
}
