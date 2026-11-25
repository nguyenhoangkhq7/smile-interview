'use client';

import { ChevronLeft, ChevronRight, Eye, FileText, Lock, LockOpen, RefreshCw, Video } from 'lucide-react';
import type { AdminUserRecord } from './types';
import { userDate, userInitials } from './userDisplay';

interface UsersTableProps {
  users: AdminUserRecord[];
  totalCatalogCount: number;
  page: number;
  pageSize: number;
  selectedUserKey: string | null;
  onSelectUser: (userKey: string) => void;
  onRequestToggleLock: (user: AdminUserRecord) => void;
  onRefresh: () => void;
  onPageChange: (page: number) => void;
}

const columns = ['Người dùng', 'Số hồ sơ', 'Phiên phỏng vấn', 'Vai trò', 'Trạng thái', 'Ngày tham gia', 'Thao tác'];
const numbers = new Intl.NumberFormat('vi-VN');
const action = 'rounded-lg p-1.5 text-[#186392] dark:text-sky-300 hover:bg-[#e9edff] dark:hover:bg-secondary';
const pagination = 'flex size-8 items-center justify-center rounded-lg bg-[#f1f3ff] dark:bg-muted disabled:opacity-40';

export default function UsersTable({
  users, totalCatalogCount, page, pageSize, selectedUserKey, onSelectUser, onRequestToggleLock, onRefresh, onPageChange,
}: UsersTableProps) {
  const pageCount = Math.max(1, Math.ceil(totalCatalogCount / pageSize));
  const offset = (page - 1) * pageSize;
  const start = users.length ? offset + 1 : 0;
  const end = users.length ? offset + users.length : 0;

  return (
    <div className="overflow-hidden rounded-xl bg-white dark:bg-card shadow-xs">
      <div className="flex items-center justify-between bg-[#f1f3ff] dark:bg-muted px-6 py-3">
        <div className="flex items-center gap-2">
          <h2 className="font-semibold text-[#141b2c] dark:text-foreground">Danh sách tài khoản</h2>
          <span className="rounded-full bg-[#dbe2f9] dark:bg-muted px-2.5 py-0.5 text-xs">{numbers.format(totalCatalogCount)}</span>
        </div>
        <button type="button" onClick={onRefresh} aria-label="Làm mới danh sách" className={action}><RefreshCw className="size-4" /></button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-205 text-left text-sm">
          <thead className="bg-[#f1f3ff] dark:bg-muted text-xs uppercase tracking-wide text-[#5c4039] dark:text-muted-foreground">
            <tr>{columns.map((column, index) => <th key={column} scope="col"
              className={index === columns.length - 1 ? 'px-5 py-3 text-right' : 'px-5 py-3'}>{column}</th>)}</tr>
          </thead>
          <tbody className="divide-y divide-[#e9edff]">
            {!users.length && <tr><td colSpan={7} className="px-6 py-8 text-center text-sm text-[#5c4039] dark:text-muted-foreground">Không tìm thấy tài khoản phù hợp.</td></tr>}
            {users.map((user) => {
              const locked = user.status === 'LOCKED';
              const LockIcon = locked ? LockOpen : Lock;
              return (
                <tr key={user.id} className={selectedUserKey === user.id ? 'bg-[#e9edff] dark:bg-secondary' : locked ? 'bg-[#fff6f5] dark:bg-red-950/40' : 'hover:bg-[#f8f9ff] dark:hover:bg-background'}>
                  <td className="px-5 py-3.5">
                    <button type="button" onClick={() => onSelectUser(user.id)} className="flex items-center gap-3 text-left">
                      <span className="grid size-9 shrink-0 place-items-center rounded-full bg-[#e0e8ff] dark:bg-secondary text-xs font-semibold text-[#186392] dark:text-sky-300">
                        {userInitials(user.fullName)}
                      </span>
                      <span><strong className="block text-[#141b2c] dark:text-foreground">{user.fullName}</strong><span className="text-xs text-[#5c4039] dark:text-muted-foreground">{user.email}</span></span>
                    </button>
                  </td>
                  <td className="px-5 py-3.5"><span className="inline-flex items-center gap-1.5 rounded-lg bg-[#e9edff] dark:bg-secondary px-2 py-1 text-xs">
                    <FileText className="size-3.5 text-[#186392] dark:text-sky-300" /> {numbers.format(user.profilesCount)} hồ sơ
                  </span></td>
                  <td className="px-5 py-3.5"><span className="inline-flex items-center gap-1.5 rounded-lg bg-[#e9edff] dark:bg-secondary px-2 py-1 text-xs">
                    <Video className="size-3.5 text-[#ad2c00] dark:text-orange-300" /> {numbers.format(user.sessionsCount)} phiên
                  </span></td>
                  <td className="px-5 py-3.5"><span className={'rounded px-2 py-1 text-xs font-semibold ' + (user.role === 'ADMIN' ? 'bg-[#cce5ff] dark:bg-sky-950' : 'bg-[#e9edff] dark:bg-secondary')}>{user.role}</span></td>
                  <td className="px-5 py-3.5"><span className={'rounded-full px-2.5 py-1 text-xs font-semibold ' + (locked ? 'bg-[#ffdad6] dark:bg-red-950 text-[#93000a] dark:text-red-200' : 'bg-[#95f8a7] dark:bg-emerald-950 text-[#006b2f] dark:text-emerald-300')}>{user.status}</span></td>
                  <td className="whitespace-nowrap px-5 py-3.5 text-xs text-[#5c4039] dark:text-muted-foreground">{userDate(user.joinedAt)}</td>
                  <td className="px-5 py-3.5 text-right">
                    {user.self ? <span className="text-xs text-[#5c4039] dark:text-muted-foreground">Tài khoản hiện tại</span> : (
                      <div className="flex justify-end gap-1">
                        <button type="button" onClick={() => onSelectUser(user.id)} className={action} aria-label={'Xem ' + user.fullName}><Eye className="size-4" /></button>
                        <button type="button" onClick={() => onRequestToggleLock(user)} className={action}
                          aria-label={(locked ? 'Mở khóa ' : 'Khóa ') + user.fullName}><LockIcon className="size-4" /></button>
                      </div>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-4 border-t border-[#e9edff] dark:border-border px-6 py-3 text-xs">
        <span>Hiển thị {numbers.format(start)}–{numbers.format(end)} / {numbers.format(totalCatalogCount)} người dùng</span>
        <nav aria-label="Trang danh sách người dùng" className="flex items-center gap-2">
          <button type="button" className={pagination} disabled={page <= 1} onClick={() => onPageChange(page - 1)} aria-label="Trang trước"><ChevronLeft className="size-4" /></button>
          <span className="tabular-nums" aria-live="polite">{page} / {pageCount}</span>
          <button type="button" className={pagination} disabled={page >= pageCount} onClick={() => onPageChange(page + 1)} aria-label="Trang tiếp"><ChevronRight className="size-4" /></button>
        </nav>
      </div>
    </div>
  );
}
