export type AdminUserRole = 'USER' | 'ADMIN' | 'CANDIDATE';
export type AdminUserStatus = 'ACTIVE' | 'LOCKED';

export interface UserCatalogFilter {
  search: string;
  role: Exclude<AdminUserRole, 'ADMIN'> | '';
  status: AdminUserStatus | '';
}

export interface AdminUserRecord {
  id: string;
  fullName: string;
  email: string;
  phone: string | null;
  role: AdminUserRole;
  status: AdminUserStatus;
  joinedAt: string;
  profilesCount: number;
  sessionsCount: number;
  self: boolean;
  lockReason: string | null;
}

export interface UsersOverviewStats {
  totalUsers: number;
  activeUsers: number;
  lockedUsers: number;
  registeredLast30Days: number;
}

export interface AdminUserPage {
  users: AdminUserRecord[];
  total: number;
  page: number;
  size: number;
  stats: UsersOverviewStats;
}

export interface AdminUserDetail {
  user: AdminUserRecord;
  interviews: { id: string; roleTitle: string | null; status: string | null; score: number | null;
    startedAt: string; endedAt: string | null }[];
  profiles: { id: string; title: string; roleTitle: string; createdAt: string }[];
  plans: { id: number; title: string; totalTasks: number; completedTasks: number }[];
}

export interface PasswordSetupLink {
  token: string;
  expiresAt: string;
}
