'use client';

import { useState } from 'react';
import type { InterviewDocumentKind } from '@/components/features/admin/sessions/types';
import { adminInterviews } from '@/services/adminInterviews';

export function useAdminDocumentDownload(id: string, kind: InterviewDocumentKind) {
  const [pending, setPending] = useState(false);
  const [failed, setFailed] = useState(false);

  async function download() {
    setPending(true);
    setFailed(false);
    try {
      const { blob, name } = await adminInterviews.original(id, kind);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = name;
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch {
      setFailed(true);
    } finally {
      setPending(false);
    }
  }

  return { pending, failed, download };
}
