'use client';

import { useRef, useState } from 'react';
import { toast } from 'sonner';
import { adminUsersError, useAdminUserDetail, useAdminUsers } from '@/hooks/useAdminUsers';
import { adminUsers } from '@/services/adminUsers';
import type { AdminUserRecord, PasswordSetupLink } from './types';
import UserDetailDrawer from './UserDetailDrawer';
import { AddAdminModal, LockAccountModal } from './UserModals';
import PasswordSetupLinkDialog from './PasswordSetupLinkDialog';
import UsersFilterBar from './UsersFilterBar';
import UsersHeader from './UsersHeader';
import UsersStatsBento from './UsersStatsBento';
import UsersTable from './UsersTable';

export default function UserManagementView() {
  const catalog = useAdminUsers();
  const [selected, setSelected] = useState<string | null>(null);
  const [lockTarget, setLockTarget] = useState<AdminUserRecord | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [link, setLink] = useState<PasswordSetupLink>();
  const [busy, setBusy] = useState(false);
  const inFlight = useRef(false);
  const detail = useAdminUserDetail(selected, catalog.revision);
  const page = catalog.result?.data;

  async function perform(action: () => Promise<void>) {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    try {
      await action();
    } catch (error) {
      toast.error(adminUsersError(error, 'Không thực hiện được thao tác.'));
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }

  function exportCsv() {
    void perform(async () => {
      const file = await adminUsers.export(catalog.filter);
      const url = URL.createObjectURL(file);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = 'users.csv';
      anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    });
  }

  return (
    <div className="relative flex w-full flex-col gap-5 pb-8">
      <UsersHeader onExportCsv={exportCsv} onOpenAddAdmin={() => setAddOpen(true)} />
      {page && <UsersStatsBento stats={page.stats} />}
      <UsersFilterBar
        searchTerm={catalog.filter.search}
        onSearchChange={(search) => catalog.changeFilter({ ...catalog.filter, search })}
        roleFilter={catalog.filter.role}
        onRoleFilterChange={(role) => catalog.changeFilter({ ...catalog.filter, role })}
        statusFilter={catalog.filter.status}
        onStatusFilterChange={(status) => catalog.changeFilter({ ...catalog.filter, status })}
        onResetFilters={catalog.reset}
      />

      {page ? (
        <UsersTable users={page.users} totalCatalogCount={page.total} page={page.page} pageSize={page.size}
          selectedUserKey={selected} onSelectUser={setSelected} onRequestToggleLock={setLockTarget}
          onRefresh={catalog.refresh} onPageChange={catalog.setPage} />
      ) : (
        <div className="rounded-xl bg-white dark:bg-card p-6 text-sm text-[#5c4039] dark:text-muted-foreground" role={catalog.result?.error ? 'alert' : 'status'}>
          {catalog.result?.error ?? 'Đang tải danh sách người dùng…'}
          {catalog.result?.error && (
            <button type="button" onClick={catalog.refresh} className="ml-3 font-semibold underline">Thử lại</button>
          )}
        </div>
      )}

      {selected && (
        <UserDetailDrawer
          key={selected} detail={detail?.data} error={detail?.error} busy={busy} onClose={() => setSelected(null)}
          onResetPassword={(user) => void perform(async () => setLink(await adminUsers.resetPassword(user.id)))}
          onRequestLockAction={setLockTarget}
        />
      )}

      {lockTarget && (
        <LockAccountModal key={lockTarget.id} targetUser={lockTarget} busy={busy}
          onClose={() => setLockTarget(null)}
          onConfirm={(user, reason) => void perform(async () => {
            const status = user.status === 'LOCKED' ? 'ACTIVE' : 'LOCKED';
            await adminUsers.changeStatus(user.id, status, reason);
            setLockTarget(null);
            catalog.refresh();
            toast.success(status === 'LOCKED' ? 'Đã khóa tài khoản.' : 'Đã mở khóa tài khoản.');
          })}
        />
      )}

      {addOpen && (
        <AddAdminModal busy={busy} onClose={() => setAddOpen(false)}
          onAddAdmin={(input) => void perform(async () => {
            const setup = await adminUsers.create(input);
            setAddOpen(false);
            setLink(setup);
            catalog.setPage(1);
            catalog.refresh();
          })}
        />
      )}
      {link && <PasswordSetupLinkDialog link={link} onClose={() => setLink(undefined)} />}
    </div>
  );
}
