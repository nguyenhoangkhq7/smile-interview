'use client';

import React, { useMemo, useRef, useState } from 'react';
import { INITIAL_ADMIN_USERS, INITIAL_USERS_STATS } from './mockUsersData';
import { AdminUserRecord, AdminUserRole, AdminUserStatus } from './types';
import UserDetailDrawer from './UserDetailDrawer';
import { ActionToast, AddAdminModal, LockAccountModal } from './UserModals';
import UsersFilterBar from './UsersFilterBar';
import UsersHeader from './UsersHeader';
import UsersStatsBento from './UsersStatsBento';
import UsersTable from './UsersTable';

export default function UserManagementView() {
  const [users, setUsers] = useState<AdminUserRecord[]>(INITIAL_ADMIN_USERS);
  const [stats, setStats] = useState(INITIAL_USERS_STATS);

  const [localSearch, setLocalSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState<'' | AdminUserRole>('');
  const [statusFilter, setStatusFilter] = useState<'' | AdminUserStatus>('');

  const [selectedUserKey, setSelectedUserKey] = useState<string | null>(null);
  const [lockModalTarget, setLockModalTarget] = useState<AdminUserRecord | null>(null);
  const [addAdminOpen, setAddAdminOpen] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const triggerToast = (msg: string) => {
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    setToastMessage(msg);
    toastTimerRef.current = setTimeout(() => {
      setToastMessage(null);
    }, 3000);
  };

  const effectiveSearch = localSearch.trim().toLowerCase();

  const filteredUsers = useMemo(() => {
    return users.filter((u) => {
      if (roleFilter && u.role !== roleFilter) return false;
      if (statusFilter && u.status !== statusFilter) return false;
      if (effectiveSearch) {
        const matchName = u.fullName.toLowerCase().includes(effectiveSearch);
        const matchEmail = u.email.toLowerCase().includes(effectiveSearch);
        const matchPhone = u.phone.toLowerCase().includes(effectiveSearch);
        if (!matchName && !matchEmail && !matchPhone) return false;
      }
      return true;
    });
  }, [users, roleFilter, statusFilter, effectiveSearch]);

  const selectedUser = useMemo(
    () => users.find((u) => u.key === selectedUserKey) ?? null,
    [users, selectedUserKey]
  );

  const handleToggleRole = (target: AdminUserRecord) => {
    const nextRole: AdminUserRole = target.role === 'ADMIN' ? 'USER' : 'ADMIN';
    setUsers((prev) =>
      prev.map((u) => (u.key === target.key ? { ...u, role: nextRole } : u))
    );
    setStats((prev) => ({
      ...prev,
      adminUsers: nextRole === 'ADMIN' ? prev.adminUsers + 1 : Math.max(1, prev.adminUsers - 1),
    }));
    triggerToast(
      nextRole === 'ADMIN'
        ? `Đã cấp quyền quản trị viên cho ${target.fullName}!`
        : `Đã chuyển ${target.fullName} về vai trò USER.`
    );
  };

  const handleResetPassword = (target: AdminUserRecord) => {
    triggerToast(`Email đặt lại mật khẩu đã được gửi tới ${target.email}!`);
  };

  const handleConfirmToggleLock = (target: AdminUserRecord) => {
    const nextStatus: AdminUserStatus = target.status === 'LOCKED' ? 'ACTIVE' : 'LOCKED';
    setUsers((prev) =>
      prev.map((u) => (u.key === target.key ? { ...u, status: nextStatus } : u))
    );
    setStats((prev) => ({
      ...prev,
      activeUsers: nextStatus === 'ACTIVE' ? prev.activeUsers + 1 : prev.activeUsers - 1,
      lockedUsers: nextStatus === 'LOCKED' ? prev.lockedUsers + 1 : Math.max(0, prev.lockedUsers - 1),
    }));
    setLockModalTarget(null);
    triggerToast(
      nextStatus === 'LOCKED'
        ? `Đã khóa tài khoản ${target.fullName}`
        : `Đã mở khóa tài khoản ${target.fullName}`
    );
  };

  const handleAddAdmin = (payload: { fullName: string; email: string; level: string }) => {
    const parts = payload.fullName.trim().split(/\s+/);
    const initials =
      parts.length >= 2
        ? `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase()
        : payload.fullName.slice(0, 2).toUpperCase();

    const newRecord: AdminUserRecord = {
      ...INITIAL_ADMIN_USERS[3],
      key: `admin-${Date.now()}`,
      userIdCode: `USR-${Math.floor(100000 + Math.random() * 900000)}`,
      initials,
      fullName: payload.fullName,
      email: payload.email,
      role: 'ADMIN',
      status: 'ACTIVE',
      isSelfAccount: false,
      joinedDate: '25/11/2026',
    };

    setUsers((prev) => [newRecord, ...prev]);
    setStats((prev) => ({
      ...prev,
      totalUsers: prev.totalUsers + 1,
      activeUsers: prev.activeUsers + 1,
      adminUsers: prev.adminUsers + 1,
    }));
    triggerToast(`Đã cấp quyền ${payload.level.split(' ')[0]} cho ${payload.email}!`);
  };

  const handleRefresh = () => {
    setIsRefreshing(true);
    setTimeout(() => {
      setIsRefreshing(false);
      triggerToast('Đã làm mới danh sách người dùng');
    }, 450);
  };

  return (
    <div className="relative flex w-full flex-col gap-5 pb-8">
      <UsersHeader
        onExportCsv={() => triggerToast('Đang xuất danh sách người dùng ra CSV...')}
        onOpenAddAdmin={() => setAddAdminOpen(true)}
      />

      <UsersStatsBento stats={stats} />

      <UsersFilterBar
        searchTerm={localSearch}
        onSearchChange={setLocalSearch}
        roleFilter={roleFilter}
        onRoleFilterChange={setRoleFilter}
        statusFilter={statusFilter}
        onStatusFilterChange={setStatusFilter}
        onResetFilters={() => {
          setLocalSearch('');
          setRoleFilter('');
          setStatusFilter('');
        }}
      />

      <UsersTable
        users={filteredUsers}
        totalCatalogCount={stats.totalUsers}
        selectedUserKey={selectedUserKey}
        onSelectUser={(key) => setSelectedUserKey(key)}
        onRequestToggleLock={(user) => setLockModalTarget(user)}
        onRefresh={handleRefresh}
        isRefreshing={isRefreshing}
      />

      <UserDetailDrawer
        user={selectedUser}
        onClose={() => setSelectedUserKey(null)}
        onToggleRole={handleToggleRole}
        onResetPassword={handleResetPassword}
        onRequestLockAction={(user) => setLockModalTarget(user)}
      />

      <LockAccountModal
        targetUser={lockModalTarget}
        onClose={() => setLockModalTarget(null)}
        onConfirm={handleConfirmToggleLock}
      />

      <AddAdminModal
        open={addAdminOpen}
        onClose={() => setAddAdminOpen(false)}
        onAddAdmin={handleAddAdmin}
      />

      <ActionToast message={toastMessage} />
    </div>
  );
}
