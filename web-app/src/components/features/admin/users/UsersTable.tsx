'use client';

import React from 'react';
import {
  BadgeCheck,
  ChevronLeft,
  ChevronRight,
  Eye,
  FileText,
  Lock,
  LockOpen,
  RefreshCw,
  Video,
} from 'lucide-react';
import { AdminUserRecord } from './types';

interface UsersTableProps {
  users: AdminUserRecord[];
  totalCatalogCount: number;
  selectedUserKey: string | null;
  onSelectUser: (userKey: string) => void;
  onRequestToggleLock: (user: AdminUserRecord) => void;
  onRefresh: () => void;
  isRefreshing: boolean;
}

export default function UsersTable({
  users,
  totalCatalogCount,
  selectedUserKey,
  onSelectUser,
  onRequestToggleLock,
  onRefresh,
  isRefreshing,
}: UsersTableProps) {
  return (
    <div className="flex flex-col overflow-hidden rounded-xl bg-white shadow-xs">
      {/* Table Header Info Bar */}
      <div className="flex items-center justify-between bg-[#f1f3ff] px-6 py-3">
        <div className="flex items-center gap-2">
          <span className="text-base font-semibold text-[#141b2c]">Danh sách tài khoản</span>
          <span className="rounded-full bg-[#dbe2f9] px-2.5 py-0.5 font-mono text-xs font-medium text-[#5c4039]">
            {totalCatalogCount.toLocaleString('en-US')}
          </span>
        </div>

        <button
          type="button"
          onClick={onRefresh}
          title="Làm mới"
          className="rounded p-1.5 text-[#5c4039] transition-colors hover:bg-[#e9edff] hover:text-[#141b2c] cursor-pointer"
        >
          <RefreshCw className={`size-4 ${isRefreshing ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Data Grid Responsive Container */}
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left">
          <thead>
            <tr className="select-none bg-[#f1f3ff] text-[11px] font-semibold uppercase tracking-wider text-[#5c4039]">
              <th className="px-6 py-3">Người dùng</th>
              <th className="px-4 py-3">Số hồ sơ</th>
              <th className="px-4 py-3">Phiên phỏng vấn</th>
              <th className="px-4 py-3">Vai trò</th>
              <th className="px-4 py-3">Trạng thái</th>
              <th className="px-4 py-3">Ngày tham gia</th>
              <th className="px-6 py-3 text-right">Thao tác</th>
            </tr>
          </thead>

          <tbody className="divide-y divide-[#f1f3ff] text-sm text-[#141b2c]">
            {users.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-6 py-10 text-center text-xs text-[#5c4039]">
                  Không tìm thấy tài khoản người dùng nào khớp với bộ lọc hiện tại.
                </td>
              </tr>
            ) : (
              users.map((user) => {
                const isSelected = selectedUserKey === user.key;
                const isLocked = user.status === 'LOCKED';

                return (
                  <tr
                    key={user.key}
                    onClick={() => onSelectUser(user.key)}
                    className={`cursor-pointer transition-colors ${
                      isSelected
                        ? 'bg-[#cce5ff]/25 hover:bg-[#cce5ff]/35'
                        : isLocked
                          ? 'bg-[#ffdad6]/15 hover:bg-[#f1f3ff]/80'
                          : 'hover:bg-[#f1f3ff]/70'
                    }`}
                  >
                    <td className="px-6 py-3.5">
                      <div className="flex items-center gap-3">
                        <div
                          className={`flex size-9 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${user.avatarBgClass} ${user.avatarTextClass}`}
                        >
                          {user.initials}
                        </div>
                        <div className="min-w-0">
                          <div className="flex items-center gap-1.5 truncate text-sm font-semibold text-[#141b2c]">
                            <span className="truncate">{user.fullName}</span>
                            {user.isVerified && (
                              <BadgeCheck
                                className="size-4 shrink-0 text-[#186392]"
                                aria-label="Được xác minh"
                              />
                            )}
                          </div>
                          <div className="truncate text-xs text-[#5c4039]">{user.email}</div>
                        </div>
                      </div>
                    </td>

                    <td className="px-4 py-3.5">
                      <span className="inline-flex items-center gap-1.5 rounded-md bg-[#e9edff] px-2.5 py-1 text-xs font-medium text-[#141b2c]">
                        <FileText className="size-3.5 text-[#186392]" />
                        {user.resumesCount} hồ sơ
                      </span>
                    </td>

                    <td className="px-4 py-3.5">
                      <span className="inline-flex items-center gap-1.5 rounded-md bg-[#e9edff] px-2.5 py-1 text-xs font-medium text-[#141b2c]">
                        <Video className="size-3.5 text-[#ad2c00]" />
                        {user.sessionsCount} phiên
                      </span>
                    </td>

                    <td className="px-4 py-3.5">
                      <span
                        className={`inline-block rounded px-2 py-0.5 text-[11px] tracking-wide ${
                          user.role === 'ADMIN'
                            ? 'bg-[#cce5ff] font-bold text-[#001e31]'
                            : 'bg-[#dbe2f9] font-semibold text-[#5c4039]'
                        }`}
                      >
                        {user.role}
                      </span>
                    </td>

                    <td className="px-4 py-3.5">
                      {isLocked ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-[#ffdad6] px-2.5 py-1 text-[11px] font-semibold text-[#93000a]">
                          <Lock className="size-3" />
                          LOCKED
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 rounded-full bg-[#95f8a7] px-2.5 py-1 text-[11px] font-semibold text-[#00210a]">
                          <span className="size-1.5 rounded-full bg-[#006b2f]" />
                          ACTIVE
                        </span>
                      )}
                    </td>

                    <td className="px-4 py-3.5 font-mono text-xs text-[#5c4039]">
                      {user.joinedDate}
                    </td>

                    <td className="px-6 py-3.5 text-right">
                      <div
                        className="inline-flex items-center gap-1"
                        onClick={(e) => e.stopPropagation()}
                      >
                        {user.isSelfAccount ? (
                          <span className="rounded bg-[#e9edff] px-2 py-1 font-mono text-xs text-[#5c4039]">
                            Tài khoản hiện tại
                          </span>
                        ) : (
                          <>
                            <button
                              type="button"
                              onClick={() => onSelectUser(user.key)}
                              title="Xem chi tiết"
                              className="rounded-lg p-1.5 text-[#186392] transition-colors hover:bg-[#e9edff] cursor-pointer"
                            >
                              <Eye className="size-4.5" />
                            </button>

                            {isLocked && (
                              <button
                                type="button"
                                onClick={() => onRequestToggleLock(user)}
                                title="Mở khóa tài khoản"
                                className="rounded-lg p-1.5 text-[#ba1a1a] transition-colors hover:bg-[#e9edff] cursor-pointer"
                              >
                                <LockOpen className="size-4.5" />
                              </button>
                            )}
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination Footer */}
      <div className="flex flex-col items-center justify-between gap-4 border-t border-[#e9edff] bg-white px-6 py-3.5 sm:flex-row">
        <div className="text-xs text-[#5c4039]">
          Hiển thị <span className="font-semibold text-[#141b2c]">1 - {users.length}</span> /{' '}
          <span className="font-semibold text-[#141b2c]">
            {totalCatalogCount.toLocaleString('en-US')}
          </span>{' '}
          người dùng
        </div>

        <div className="flex items-center gap-1.5">
          <button
            type="button"
            disabled
            aria-label="Trang trước"
            className="flex size-7 cursor-not-allowed items-center justify-center rounded-lg bg-[#f1f3ff] text-[#5c4039] opacity-50"
          >
            <ChevronLeft className="size-4" />
          </button>
          <button
            type="button"
            className="flex size-7 items-center justify-center rounded-lg bg-[#d83900] text-xs font-semibold text-[#fffbff]"
          >
            1
          </button>
          <button
            type="button"
            className="flex size-7 items-center justify-center rounded-lg bg-[#f1f3ff] text-xs font-semibold text-[#141b2c] hover:bg-[#e9edff] cursor-pointer"
          >
            2
          </button>
          <button
            type="button"
            className="flex size-7 items-center justify-center rounded-lg bg-[#f1f3ff] text-xs font-semibold text-[#141b2c] hover:bg-[#e9edff] cursor-pointer"
          >
            3
          </button>
          <span className="px-1 text-xs text-[#5c4039]">...</span>
          <button
            type="button"
            className="flex h-7 items-center justify-center rounded-lg bg-[#f1f3ff] px-2 text-xs font-semibold text-[#141b2c] hover:bg-[#e9edff] cursor-pointer"
          >
            2080
          </button>
          <button
            type="button"
            aria-label="Trang tiếp"
            className="flex size-7 items-center justify-center rounded-lg bg-[#f1f3ff] text-[#141b2c] hover:bg-[#e9edff] cursor-pointer"
          >
            <ChevronRight className="size-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
