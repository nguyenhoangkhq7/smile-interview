'use client';

import { useEffect, useState } from 'react';
import { adminAudit } from '@/services/adminAudit';
import type { AuditDetail, AuditFilter, AuditPage } from '@/components/features/admin/audit-logs/types';

type Result<T> = { key: string; data?: T; failed?: boolean };

export function useAdminAudit(filter: AuditFilter, page: number, selected: string | null) {
  const { search, actorId, action, datePreset, date, fromDate, toDate } = filter;
  const [refresh, setRefresh] = useState(0);
  const listKey = JSON.stringify([search, actorId, action, datePreset, date, fromDate, toDate, page, refresh]);
  const detailKey = JSON.stringify([selected, refresh]);
  const [list, setList] = useState<Result<AuditPage>>();
  const [detail, setDetail] = useState<Result<AuditDetail>>();

  useEffect(() => {
    const request = new AbortController();
    const timer = setTimeout(() => {
      void adminAudit.list({ search, actorId, action, datePreset, date, fromDate, toDate }, page, request.signal).then((data) => {
        if (!request.signal.aborted) setList({ key: listKey, data });
      }).catch(() => {
        if (!request.signal.aborted) setList({ key: listKey, failed: true });
      });
    }, search ? 200 : 0);
    return () => {
      clearTimeout(timer);
      request.abort();
    };
  }, [search, actorId, action, datePreset, date, fromDate, toDate, page, listKey]);

  useEffect(() => {
    if (!selected) return;
    const request = new AbortController();
    void adminAudit.detail(selected, request.signal).then((data) => {
      if (!request.signal.aborted) setDetail({ key: detailKey, data });
    }).catch(() => {
      if (!request.signal.aborted) setDetail({ key: detailKey, failed: true });
    });
    return () => request.abort();
  }, [selected, detailKey]);

  return {
    list: list?.key === listKey ? list : undefined,
    detail: detail?.key === detailKey ? detail : undefined,
    actors: list?.data?.actors ?? [],
    reload: () => setRefresh((value) => value + 1),
  };
}
