'use client';

import React, { useMemo, useRef, useState } from 'react';
import { ActionToast } from '../users/UserModals';
import AuditLogDetailDrawer from './AuditLogDetailDrawer';
import AuditLogsFilterBar from './AuditLogsFilterBar';
import AuditLogsHeader from './AuditLogsHeader';
import AuditLogsTable from './AuditLogsTable';
import { INITIAL_AUDIT_LOGS } from './mockAuditLogsData';
import { AuditActionType, AuditLogRecord } from './types';

export default function AuditLogsView() {
  const [searchTerm, setSearchTerm] = useState('');
  const [adminFilter, setAdminFilter] = useState('ALL');
  const [actionFilter, setActionFilter] = useState<'ALL' | AuditActionType>('ALL');
  const [selectedRecord, setSelectedRecord] = useState<AuditLogRecord | null>(null);

  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const triggerToast = (msg: string) => {
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    setToastMessage(msg);
    toastTimerRef.current = setTimeout(() => {
      setToastMessage(null);
    }, 2800);
  };

  const effectiveSearch = searchTerm.trim().toLowerCase();

  const filteredLogs = useMemo(() => {
    return INITIAL_AUDIT_LOGS.filter((log) => {
      if (adminFilter !== 'ALL' && log.adminName !== adminFilter) return false;
      if (actionFilter !== 'ALL' && log.action !== actionFilter) return false;
      if (effectiveSearch) {
        const matchCode = log.targetCode.toLowerCase().includes(effectiveSearch);
        const matchSummary = log.summaryText.toLowerCase().includes(effectiveSearch);
        const matchAdmin = log.adminName.toLowerCase().includes(effectiveSearch);
        const matchAction = log.action.toLowerCase().includes(effectiveSearch);
        if (!matchCode && !matchSummary && !matchAdmin && !matchAction) return false;
      }
      return true;
    });
  }, [adminFilter, actionFilter, effectiveSearch]);

  const handleCopyCode = (code: string) => {
    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      void navigator.clipboard.writeText(code);
    }
    triggerToast(`Đã sao chép mã ${code}!`);
  };

  const handleCopyJson = (jsonText: string) => {
    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      void navigator.clipboard.writeText(jsonText);
    }
    triggerToast('Đã sao chép JSON Payload!');
  };

  return (
    <div className="flex w-full flex-col gap-5 pb-8">
      <AuditLogsHeader
        totalLogsCount={1428}
        todayActionsCount={24}
        activeAdminsCount={3}
        onExportCsv={() =>
          triggerToast('Đang xuất dữ liệu nhật ký ra tệp CSV (1,428 bản ghi)...')
        }
      />

      <AuditLogsFilterBar
        searchTerm={searchTerm}
        onSearchChange={setSearchTerm}
        adminFilter={adminFilter}
        onAdminFilterChange={setAdminFilter}
        actionFilter={actionFilter}
        onActionFilterChange={setActionFilter}
        onResetFilters={() => {
          setSearchTerm('');
          setAdminFilter('ALL');
          setActionFilter('ALL');
        }}
      />

      <AuditLogsTable
        logs={filteredLogs}
        totalCount={1428}
        selectedLogId={selectedRecord?.id ?? null}
        onSelectLog={(record) => setSelectedRecord(record)}
        onCopyCode={handleCopyCode}
      />

      <AuditLogDetailDrawer
        record={selectedRecord}
        onClose={() => setSelectedRecord(null)}
        onCopyJson={handleCopyJson}
      />

      <ActionToast message={toastMessage} />
    </div>
  );
}
