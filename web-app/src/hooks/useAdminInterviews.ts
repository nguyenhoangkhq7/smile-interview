'use client';

import { useEffect, useState } from 'react';
import type { InterviewDetail, InterviewFilter, InterviewPage } from '@/components/features/admin/sessions/types';
import { adminInterviews } from '@/services/adminInterviews';

type Result<T> = { key: string; data?: T; failed?: boolean };

const CATALOG_POLL_MS = 5000;
const LIVE_DETAIL_POLL_MS = 2500;

export function useAdminInterviews(search: string, status: InterviewFilter, page: number, selected: string | null) {
  const [revision, setRevision] = useState(0);
  const [catalog, setCatalog] = useState<Result<InterviewPage>>();
  const [detail, setDetail] = useState<Result<InterviewDetail>>();
  const catalogKey = JSON.stringify([search, status, page, revision]);
  const detailKey = JSON.stringify([selected, revision]);

  useEffect(() => {
    const request = new AbortController();
    let pollTimer: ReturnType<typeof setTimeout> | undefined;

    const loadCatalog = () => {
      void adminInterviews.list(search, status, page, request.signal)
        .then((data) => {
          if (!request.signal.aborted) {
            setCatalog({ key: catalogKey, data });
            pollTimer = setTimeout(loadCatalog, CATALOG_POLL_MS);
          }
        })
        .catch(() => {
          if (!request.signal.aborted) setCatalog({ key: catalogKey, failed: true });
        });
    };

    const debounceTimer = setTimeout(loadCatalog, search ? 200 : 0);
    return () => {
      clearTimeout(debounceTimer);
      clearTimeout(pollTimer);
      request.abort();
    };
  }, [catalogKey, page, search, status]);

  useEffect(() => {
    if (!selected) return;
    const request = new AbortController();
    let pollTimer: ReturnType<typeof setTimeout> | undefined;

    const loadDetail = () => {
      void adminInterviews.detail(selected, request.signal)
        .then((data) => {
          if (!request.signal.aborted) {
            setDetail({ key: detailKey, data });
            if (!data.finalized) {
              pollTimer = setTimeout(loadDetail, LIVE_DETAIL_POLL_MS);
            }
          }
        })
        .catch(() => {
          if (!request.signal.aborted) setDetail({ key: detailKey, failed: true });
        });
    };

    loadDetail();
    return () => {
      clearTimeout(pollTimer);
      request.abort();
    };
  }, [detailKey, selected]);

  return {
    catalog: catalog?.key === catalogKey ? catalog : undefined,
    detail: detail?.key === detailKey ? detail : undefined,
    reload: () => setRevision((value) => value + 1),
  };
}
