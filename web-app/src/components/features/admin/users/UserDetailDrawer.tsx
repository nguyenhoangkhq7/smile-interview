'use client';

import { useState } from 'react';
import { Calendar, FileText, KeyRound, Lock, Unlock, Video, X } from 'lucide-react';
import type { AdminUserDetail, AdminUserRecord } from './types';
import { userDate, userInitials } from './userDisplay';

const tabs = [
  { key: 'interviews', label: 'Phiên phỏng vấn' },
  { key: 'profiles', label: 'Hồ sơ' },
  { key: 'plans', label: 'Kế hoạch học tập' },
] as const;

interface UserDetailDrawerProps {
  detail?: AdminUserDetail;
  error?: string;
  busy: boolean;
  onClose: () => void;
  onResetPassword: (user: AdminUserRecord) => void;
  onRequestLockAction: (user: AdminUserRecord) => void;
}

const entry =
  'flex items-center justify-between gap-3 rounded-xl border border-[#e0e8ff] dark:border-border bg-[#f9f9ff] dark:bg-background px-3.5 py-2.5 transition-colors hover:bg-[#f1f3ff] dark:hover:bg-muted';
const action =
  'inline-flex items-center gap-1.5 rounded-lg border border-[#e0e8ff] dark:border-border bg-white dark:bg-card px-3 py-2 text-xs font-semibold text-[#141b2c] dark:text-foreground transition-colors hover:bg-[#f1f3ff] dark:hover:bg-muted disabled:opacity-50';

export default function UserDetailDrawer({
  detail,
  error,
  busy,
  onClose,
  onResetPassword,
  onRequestLockAction,
}: UserDetailDrawerProps) {
  const [tab, setTab] = useState<(typeof tabs)[number]['key']>('interviews');
  const user = detail?.user;

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-[#141b2c]/45 p-4 backdrop-blur-[2px]"
      role="dialog"
      aria-modal="true"
      aria-labelledby="admin-user-detail-title"
    >
      <button
        type="button"
        tabIndex={-1}
        className="absolute inset-0 cursor-default"
        aria-label="Đóng chi tiết"
        onClick={onClose}
      />

      <div className="relative z-10 flex max-h-[85vh] w-full max-w-xl flex-col overflow-hidden rounded-2xl border border-[#e0e8ff] dark:border-border bg-white dark:bg-card shadow-2xl">
        {/* Modal Header */}
        <header className="flex items-start justify-between gap-4 border-b border-[#e0e8ff] dark:border-border bg-[#f9f9ff] dark:bg-background px-6 py-4">
          <div className="flex min-w-0 items-center gap-3.5">
            {user && (
              <span className="grid size-11 shrink-0 place-items-center rounded-full bg-[#e9edff] dark:bg-secondary text-sm font-bold text-[#186392] dark:text-sky-300">
                {userInitials(user.fullName)}
              </span>
            )}
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h2
                  id="admin-user-detail-title"
                  className="truncate text-base font-bold text-[#141b2c] dark:text-foreground"
                >
                  {user?.fullName ?? 'Chi tiết tài khoản'}
                </h2>
                {user && (
                  <>
                    <span
                      className={`inline-flex items-center rounded-md px-2 py-0.5 text-[11px] font-bold ${
                        user.role === 'ADMIN'
                          ? 'bg-[#e0e8ff] dark:bg-secondary text-[#186392] dark:text-sky-300'
                          : 'bg-[#f1f3ff] dark:bg-muted text-[#5c4039] dark:text-muted-foreground'
                      }`}
                    >
                      {user.role}
                    </span>
                    <span
                      className={`inline-flex items-center rounded-md px-2 py-0.5 text-[11px] font-bold ${
                        user.status === 'ACTIVE'
                          ? 'bg-[#95f8a7]/45 dark:bg-emerald-950/45 text-[#005323] dark:text-emerald-200'
                          : 'bg-[#ffdad6] dark:bg-red-950 text-[#93000a] dark:text-red-200'
                      }`}
                    >
                      {user.status === 'ACTIVE' ? 'Đang hoạt động' : 'Đã khóa'}
                    </span>
                  </>
                )}
              </div>
              {user && (
                <p className="mt-0.5 break-all text-xs text-[#5c4039] dark:text-muted-foreground">
                  {user.email}
                  {user.phone && ' · ' + user.phone}
                </p>
              )}
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            aria-label="Đóng"
            className="shrink-0 rounded-lg p-1.5 text-[#5c4039] dark:text-muted-foreground transition-colors hover:bg-[#e9edff] dark:hover:bg-secondary hover:text-[#141b2c] dark:hover:text-foreground"
          >
            <X className="size-5" />
          </button>
        </header>

        {/* Modal Body */}
        <div className="flex min-h-0 flex-1 flex-col px-6 py-4">
          {!detail && (
            <p
              role={error ? 'alert' : 'status'}
              className="py-8 text-center text-sm text-[#5c4039] dark:text-muted-foreground"
            >
              {error ?? 'Đang tải chi tiết…'}
            </p>
          )}

          {detail && user && (
            <>
              {/* Quick Stats Strip */}
              <div className="grid grid-cols-3 gap-2.5 rounded-xl bg-[#f1f3ff] dark:bg-muted p-3 text-xs">
                <div className="flex items-center gap-2">
                  <Calendar className="size-4 shrink-0 text-[#186392] dark:text-sky-300" />
                  <div>
                    <p className="text-[11px] text-[#5c4039] dark:text-muted-foreground">Ngày tham gia</p>
                    <p className="font-semibold text-[#141b2c] dark:text-foreground">{userDate(user.joinedAt)}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <FileText className="size-4 shrink-0 text-[#186392] dark:text-sky-300" />
                  <div>
                    <p className="text-[11px] text-[#5c4039] dark:text-muted-foreground">Hồ sơ ứng tuyển</p>
                    <p className="font-semibold text-[#141b2c] dark:text-foreground">{user.profilesCount} hồ sơ</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Video className="size-4 shrink-0 text-[#ad2c00] dark:text-orange-300" />
                  <div>
                    <p className="text-[11px] text-[#5c4039] dark:text-muted-foreground">Phiên phỏng vấn</p>
                    <p className="font-semibold text-[#141b2c] dark:text-foreground">{user.sessionsCount} phiên</p>
                  </div>
                </div>
                {user.lockReason && (
                  <p className="col-span-3 mt-1 border-t border-[#e0e8ff] dark:border-border pt-2 text-xs font-medium text-[#93000a] dark:text-red-200">
                    Lý do khóa: {user.lockReason}
                  </p>
                )}
              </div>

              {/* Tabs */}
              <div
                className="mt-4 flex flex-wrap gap-1.5 border-b border-[#e0e8ff] dark:border-border pb-3"
                aria-label="Thông tin người dùng"
              >
                {tabs.map((item) => (
                  <button
                    key={item.key}
                    type="button"
                    aria-pressed={tab === item.key}
                    onClick={() => setTab(item.key)}
                    className={
                      'inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs transition-colors ' +
                      (tab === item.key
                        ? 'bg-[#141b2c] font-semibold text-white'
                        : 'bg-[#f1f3ff] dark:bg-muted font-medium text-[#5c4039] dark:text-muted-foreground hover:bg-[#e0e8ff] dark:hover:bg-secondary hover:text-[#141b2c] dark:hover:text-foreground')
                    }
                  >
                    <span>{item.label}</span>
                    <span
                      className={`rounded-full px-1.5 py-0.2 text-[10px] ${
                        tab === item.key
                          ? 'bg-white/20 text-white'
                          : 'bg-white dark:bg-card text-[#141b2c] dark:text-foreground'
                      }`}
                    >
                      {detail[item.key].length}
                    </span>
                  </button>
                ))}
              </div>

              {/* Scrollable Tab Content */}
              <div className="mt-3 max-h-[38vh] min-h-[140px] space-y-2 overflow-y-auto pr-1 text-sm">
                {!detail[tab].length && (
                  <p className="py-8 text-center text-xs text-[#5c4039] dark:text-muted-foreground">
                    Chưa có dữ liệu trong mục này.
                  </p>
                )}

                {tab === 'interviews' &&
                  detail.interviews.map((interview) => (
                    <div className={entry} key={interview.id}>
                      <div className="min-w-0">
                        <p className="truncate text-xs font-semibold text-[#141b2c] dark:text-foreground">
                          {interview.roleTitle || 'Phiên phỏng vấn'}
                        </p>
                        <p className="mt-0.5 text-[11px] text-[#5c4039] dark:text-muted-foreground">
                          {userDate(interview.startedAt)}
                        </p>
                      </div>
                      <div className="flex shrink-0 items-center gap-2 text-xs">
                        {interview.score !== null && (
                          <span className="rounded-md bg-[#e9edff] dark:bg-secondary px-2 py-0.5 text-[11px] font-bold text-[#186392] dark:text-sky-300">
                            Điểm {interview.score}
                          </span>
                        )}
                        <span className="rounded-md bg-white dark:bg-card px-2 py-0.5 text-[11px] font-medium text-[#5c4039] dark:text-muted-foreground shadow-2xs">
                          {interview.status ?? 'Chưa rõ'}
                        </span>
                      </div>
                    </div>
                  ))}

                {tab === 'profiles' &&
                  detail.profiles.map((profile) => (
                    <div className={entry} key={profile.id}>
                      <div className="min-w-0">
                        <p className="truncate text-xs font-semibold text-[#141b2c] dark:text-foreground">
                          {profile.title}
                        </p>
                        <p className="mt-0.5 truncate text-[11px] text-[#5c4039] dark:text-muted-foreground">
                          {profile.roleTitle}
                        </p>
                      </div>
                      <span className="shrink-0 text-[11px] text-[#5c4039] dark:text-muted-foreground">
                        {userDate(profile.createdAt)}
                      </span>
                    </div>
                  ))}

                {tab === 'plans' &&
                  detail.plans.map((plan) => (
                    <div className={entry} key={plan.id}>
                      <p className="truncate text-xs font-semibold text-[#141b2c] dark:text-foreground">
                        {plan.title}
                      </p>
                      <span className="shrink-0 rounded-md bg-[#e9edff] dark:bg-secondary px-2 py-0.5 text-[11px] font-semibold text-[#186392] dark:text-sky-300">
                        {plan.completedTasks}/{plan.totalTasks} nhiệm vụ
                      </span>
                    </div>
                  ))}
              </div>
            </>
          )}
        </div>

        {/* Modal Footer */}
        {detail && user && (
          <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-[#e0e8ff] dark:border-border bg-[#f9f9ff] dark:bg-background px-6 py-3.5">
            {!user.self ? (
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  disabled={busy}
                  className={action}
                  onClick={() => onResetPassword(user)}
                >
                  <KeyRound className="size-3.5 text-[#5c4039] dark:text-muted-foreground" />
                  Đặt lại mật khẩu
                </button>
                <button
                  type="button"
                  disabled={busy}
                  className={
                    action +
                    (user.status === 'LOCKED'
                      ? ' border-[#006b2f]/30 text-[#006b2f] dark:text-emerald-300'
                      : ' border-[#ad2c00]/30 text-[#ad2c00] dark:text-orange-300')
                  }
                  onClick={() => onRequestLockAction(user)}
                >
                  {user.status === 'LOCKED' ? (
                    <>
                      <Unlock className="size-3.5" />
                      Mở khóa tài khoản
                    </>
                  ) : (
                    <>
                      <Lock className="size-3.5" />
                      Khóa tài khoản
                    </>
                  )}
                </button>
              </div>
            ) : (
              <span className="text-xs text-[#5c4039] dark:text-muted-foreground">Tài khoản quản trị đang đăng nhập</span>
            )}

            <button
              type="button"
              onClick={onClose}
              className="ml-auto rounded-lg bg-[#141b2c] px-4 py-2 text-xs font-semibold text-white transition-colors hover:bg-[#293041]"
            >
              Đóng
            </button>
          </footer>
        )}
      </div>
    </div>
  );
}
