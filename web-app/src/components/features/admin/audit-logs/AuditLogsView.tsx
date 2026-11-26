'use client';

import { useEffect, useRef, useState } from 'react';
import { useAdminAudit } from '@/hooks/useAdminAudit';
import { adminAudit } from '@/services/adminAudit';
import { ActionToast } from '../users/UserModals';
import AuditLogDetailDrawer from './AuditLogDetailDrawer';
import AuditLogsFilterBar from './AuditLogsFilterBar';
import AuditLogsHeader from './AuditLogsHeader';
import AuditLogsTable from './AuditLogsTable';
import type { AuditFilter } from './types';

const empty: AuditFilter = {
  search: '',
  actorId: '',
  action: '',
  datePreset: 'all',
  date: '',
  fromDate: '',
  toDate: '',
};

export default function AuditLogsView() {
  const [filter, setFilter] = useState(empty);
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [notice, setNotice] = useState('');
  const [toast, setToast] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const { list, detail, actors, reload } = useAdminAudit(filter, page, selected);
  const data = list?.data;
  useEffect(() => () => clearTimeout(timer.current), []);

  function change(next: AuditFilter) {
    setFilter(next);
    setPage(1);
    setNotice('');
  }

  async function copy(value: string, message: string) {
    try {
      await navigator.clipboard.writeText(value);
      setNotice('');
      clearTimeout(timer.current);
      setToast(message);
      timer.current = setTimeout(() => setToast(null), 2500);
      return true;
    } catch {
      setNotice('Không thể sao chép vào clipboard.');
      return false;
    }
  }

  async function exportCsv() {
    setExporting(true);
    setNotice('');
    try {
      const blob = await adminAudit.export(filter);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'admin-audit-logs.csv';
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch {
      setNotice('Không thể xuất nhật ký. Vui lòng thử lại.');
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="flex w-full flex-col gap-5 pb-8">
      <AuditLogsHeader stats={data?.stats} exporting={exporting}
        canExport={Boolean(data?.total)} onExportCsv={() => void exportCsv()} />
      <AuditLogsFilterBar filter={filter} actors={actors}
        onChange={change} onResetFilters={() => change(empty)} />
      {notice && <p className="text-sm text-red-700" role="alert">{notice}</p>}
      {list?.failed ? (
        <p className="rounded-xl bg-white dark:bg-card p-5 text-sm text-red-700" role="alert">
          Không thể tải nhật ký quản trị.
          <button type="button" className="ml-3 underline" onClick={reload}>Thử lại</button>
        </p>
      ) : data ? <AuditLogsTable logs={data.rows} totalCount={data.total} page={data.page} size={data.size}
        onPage={setPage} selectedLogId={selected} onSelectLog={setSelected}
        onCopyCode={(code) => void copy(code, 'Đã sao chép mã đối tượng.')} />
        : <p className="rounded-xl bg-white dark:bg-card p-5 text-sm" role="status">Đang tải nhật ký…</p>}
      <AuditLogDetailDrawer key={selected} open={selected !== null} detail={detail?.data} failed={detail?.failed}
        onRetry={reload} onClose={() => setSelected(null)}
        onCopyJson={(json) => copy(json, 'Đã sao chép JSON nhật ký.')} />
      <ActionToast message={toast} />
    </div>
  );
}
