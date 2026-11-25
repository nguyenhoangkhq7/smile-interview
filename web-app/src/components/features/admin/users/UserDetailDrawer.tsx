'use client';

import React, { useState } from 'react';
import {
  CheckCircle2,
  Circle,
  ClipboardCheck,
  Eye,
  FileText,
  KeyRound,
  Lock,
  LockOpen,
  UserCog,
  Video,
  X,
} from 'lucide-react';
import { AdminUserRecord, UserDrawerTabKey } from './types';

interface UserDetailDrawerProps {
  user: AdminUserRecord | null;
  onClose: () => void;
  onToggleRole: (user: AdminUserRecord) => void;
  onResetPassword: (user: AdminUserRecord) => void;
  onRequestLockAction: (user: AdminUserRecord) => void;
}

export default function UserDetailDrawer({
  user,
  onClose,
  onToggleRole,
  onResetPassword,
  onRequestLockAction,
}: UserDetailDrawerProps) {
  const [activeTab, setActiveTab] = useState<UserDrawerTabKey>('sessions');

  const isOpen = user !== null;
  const isLocked = user?.status === 'LOCKED';

  return (
    <>
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-[#141b2c]/25 backdrop-blur-[1px] transition-opacity duration-300"
          onClick={onClose}
        />
      )}

      <aside
        aria-label="Chi tiết người dùng"
        className={`fixed inset-y-0 right-0 z-50 flex w-full max-w-lg flex-col bg-white shadow-2xl transition-transform duration-300 ease-in-out ${
          isOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        {user && (
          <>
            {/* Drawer Header */}
            <div className="flex items-start justify-between bg-[#f1f3ff] p-5">
              <div className="flex items-center gap-3.5">
                <div
                  className={`flex size-12 shrink-0 items-center justify-center rounded-full text-lg font-bold shadow-xs ${user.avatarBgClass} ${user.avatarTextClass}`}
                >
                  {user.initials}
                </div>

                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="text-lg font-bold leading-tight text-[#141b2c]">
                      {user.fullName}
                    </h2>
                    {isLocked ? (
                      <span className="rounded-full bg-[#ffdad6] px-2 py-0.5 text-[11px] font-semibold text-[#93000a]">
                        LOCKED
                      </span>
                    ) : (
                      <span className="rounded-full bg-[#95f8a7] px-2 py-0.5 text-[11px] font-semibold text-[#00210a]">
                        ACTIVE
                      </span>
                    )}
                  </div>
                  <p className="mt-0.5 text-xs text-[#5c4039]">
                    {user.email} • {user.phone}
                  </p>
                </div>
              </div>

              <button
                type="button"
                onClick={onClose}
                aria-label="Đóng"
                className="rounded-lg p-1.5 text-[#5c4039] transition-colors hover:bg-[#e9edff] hover:text-[#141b2c] cursor-pointer"
              >
                <X className="size-5" />
              </button>
            </div>

            {/* Stats Tri-card Overview */}
            <div className="grid grid-cols-3 gap-2 bg-white p-4">
              <div className="rounded-lg bg-[#f1f3ff] p-2.5 text-center">
                <span className="block text-xl font-bold text-[#141b2c] tabular-nums">
                  {user.resumesCount}
                </span>
                <span className="text-[11px] font-semibold uppercase text-[#5c4039]">
                  Hồ sơ
                </span>
              </div>

              <div className="rounded-lg bg-[#f1f3ff] p-2.5 text-center">
                <span className="block text-xl font-bold text-[#ad2c00] tabular-nums">
                  {user.sessionsCount}
                </span>
                <span className="text-[11px] font-semibold uppercase text-[#5c4039]">
                  Phiên ({user.avgScoreLabel})
                </span>
              </div>

              <div className="rounded-lg bg-[#f1f3ff] p-2.5 text-center">
                <span className="block text-xl font-bold text-[#186392] tabular-nums">
                  {user.completedTasksRatio}
                </span>
                <span className="text-[11px] font-semibold uppercase text-[#5c4039]">
                  Ôn tập
                </span>
              </div>
            </div>

            {/* Tabs Header */}
            <div className="flex border-b border-[#e9edff] bg-white px-5">
              <button
                type="button"
                onClick={() => setActiveTab('sessions')}
                className={`flex items-center gap-1.5 border-b-2 px-3 py-2.5 text-xs font-semibold transition-all cursor-pointer ${
                  activeTab === 'sessions'
                    ? 'border-[#ad2c00] text-[#ad2c00]'
                    : 'border-transparent text-[#5c4039] hover:text-[#141b2c]'
                }`}
              >
                <Video className="size-3.5" />
                <span>Phiên phỏng vấn ({user.sessionsCount})</span>
              </button>

              <button
                type="button"
                onClick={() => setActiveTab('resumes')}
                className={`flex items-center gap-1.5 border-b-2 px-3 py-2.5 text-xs font-semibold transition-all cursor-pointer ${
                  activeTab === 'resumes'
                    ? 'border-[#ad2c00] text-[#ad2c00]'
                    : 'border-transparent text-[#5c4039] hover:text-[#141b2c]'
                }`}
              >
                <FileText className="size-3.5" />
                <span>Hồ sơ ({user.resumesCount})</span>
              </button>

              <button
                type="button"
                onClick={() => setActiveTab('plans')}
                className={`flex items-center gap-1.5 border-b-2 px-3 py-2.5 text-xs font-semibold transition-all cursor-pointer ${
                  activeTab === 'plans'
                    ? 'border-[#ad2c00] text-[#ad2c00]'
                    : 'border-transparent text-[#5c4039] hover:text-[#141b2c]'
                }`}
              >
                <ClipboardCheck className="size-3.5" />
                <span>Kế hoạch ôn tập</span>
              </button>
            </div>

            {/* Drawer Body */}
            <div className="flex-1 space-y-3 overflow-y-auto bg-white p-5">
              {activeTab === 'sessions' && (
                <div className="animate-fade-up space-y-2.5">
                  {user.recentSessions.map((session) => {
                    const badgeClasses =
                      session.scoreVariant === 'emerald'
                        ? 'bg-[#95f8a7] text-[#00210a]'
                        : session.scoreVariant === 'blue'
                          ? 'bg-[#cce5ff] text-[#001e31]'
                          : 'bg-[#e9edff] text-[#141b2c]';

                    return (
                      <div
                        key={session.id}
                        className="rounded-xl bg-[#f1f3ff] p-3.5 transition-all hover:bg-[#e9edff]"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="text-sm font-semibold text-[#141b2c]">
                                {session.roleTitle}
                              </span>
                              <span
                                className={`rounded-full px-2 py-0.5 font-mono text-xs font-bold ${badgeClasses}`}
                              >
                                {session.scoreLabel}
                              </span>
                            </div>
                            <p className="mt-1 text-xs text-[#5c4039]">
                              {session.dateTimeLabel} • {session.durationLabel}
                            </p>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              {activeTab === 'resumes' && (
                <div className="animate-fade-up space-y-2.5">
                  {user.resumes.map((res) => (
                    <div
                      key={res.id}
                      className="flex items-center justify-between rounded-xl bg-[#f1f3ff] p-3.5"
                    >
                      <div className="flex min-w-0 items-center gap-3">
                        <FileText className={`size-6 shrink-0 ${res.iconColorClass}`} />
                        <div className="min-w-0">
                          <div className="truncate text-sm font-semibold text-[#141b2c]">
                            {res.fileName}
                          </div>
                          <div className="text-xs text-[#5c4039]">
                            {res.updatedAt} • {res.fileSize}
                          </div>
                        </div>
                      </div>
                      <button
                        type="button"
                        aria-label="Xem hồ sơ"
                        className="rounded-lg p-1.5 text-[#186392] transition-colors hover:bg-[#e9edff] cursor-pointer"
                      >
                        <Eye className="size-4" />
                      </button>
                    </div>
                  ))}
                </div>
              )}

              {activeTab === 'plans' && (
                <div className="animate-fade-up rounded-xl bg-[#f1f3ff] p-4">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-sm font-semibold text-[#141b2c]">
                      {user.studyPlan.title}
                    </span>
                    <span className="font-mono text-xs font-bold text-[#006b2f]">
                      {user.studyPlan.completionPct}%
                    </span>
                  </div>

                  <div className="mb-3 h-1.5 w-full overflow-hidden rounded-full bg-[#dbe2f9]">
                    <div
                      className="h-full rounded-full bg-[#006b2f] transition-all duration-500"
                      style={{ width: `${user.studyPlan.completionPct}%` }}
                    />
                  </div>

                  <ul className="space-y-2 text-xs text-[#5c4039]">
                    {user.studyPlan.tasks.map((task) => (
                      <li
                        key={task.id}
                        className={`flex items-center gap-2 ${
                          task.completed ? 'font-medium text-[#141b2c]' : 'text-[#5c4039]'
                        }`}
                      >
                        {task.completed ? (
                          <CheckCircle2 className="size-4 shrink-0 text-[#006b2f]" />
                        ) : (
                          <Circle className="size-4 shrink-0 text-[#907067]" />
                        )}
                        <span>{task.label}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            {/* Administrative Actions Footer */}
            <div className="flex flex-col gap-2 border-t border-[#e9edff] bg-[#f1f3ff] p-4">
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => onToggleRole(user)}
                  className="flex items-center justify-center gap-1.5 rounded-lg bg-white px-3 py-2 text-xs font-medium text-[#141b2c] shadow-2xs transition-all hover:bg-[#e9edff] cursor-pointer"
                >
                  <UserCog className="size-4 text-[#186392]" />
                  <span>{user.role === 'ADMIN' ? 'Hạ về quyền User' : 'Nâng quyền Admin'}</span>
                </button>

                <button
                  type="button"
                  onClick={() => onResetPassword(user)}
                  className="flex items-center justify-center gap-1.5 rounded-lg bg-white px-3 py-2 text-xs font-medium text-[#141b2c] shadow-2xs transition-all hover:bg-[#e9edff] cursor-pointer"
                >
                  <KeyRound className="size-4 text-[#ad2c00]" />
                  <span>Đặt lại mật khẩu</span>
                </button>
              </div>

              <button
                type="button"
                onClick={() => onRequestLockAction(user)}
                className={`flex w-full items-center justify-center gap-1.5 rounded-lg px-4 py-2 text-xs font-semibold transition-all cursor-pointer ${
                  isLocked
                    ? 'bg-[#95f8a7] text-[#00210a] hover:bg-[#006b2f] hover:text-white'
                    : 'bg-[#ffdad6] text-[#93000a] hover:bg-[#ba1a1a] hover:text-white'
                }`}
              >
                {isLocked ? (
                  <>
                    <LockOpen className="size-4" />
                    <span>Mở khóa tài khoản</span>
                  </>
                ) : (
                  <>
                    <Lock className="size-4" />
                    <span>Khóa tài khoản</span>
                  </>
                )}
              </button>
            </div>
          </>
        )}
      </aside>
    </>
  );
}
