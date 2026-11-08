import React from 'react';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { HrSessionDetailClient } from '@/components/features/hr';
import { Button } from '@/components/ui/button';
import { ArrowLeft, FileCheck } from 'lucide-react';

export const revalidate = 0;

export default async function HrSessionDetailPage({
  params,
}: {
  params: Promise<{ sessionId: string }>;
}) {
  const { sessionId } = await params;

  if (!sessionId) {
    notFound();
  }

  return (
    <div className="container mx-auto max-w-5xl px-4 space-y-6">
      {/* Header Navigation */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 pb-4">
        <div className="flex items-center space-x-3">
          <Link href="/hr-dashboard">
            <Button variant="outline" size="sm" className="gap-1 text-slate-700 inline-flex items-center gap-1">
              <ArrowLeft className="size-4" /> Quay lại danh sách
            </Button>
          </Link>
          <div>
            <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
              <FileCheck className="size-5 text-brand-orange" />
              Chi Tiết Phỏng Vấn
            </h1>
            <p className="text-[11px] text-slate-400 font-mono mt-0.5">Session ID: {sessionId}</p>
          </div>
        </div>
      </div>

      {/* Client wrapper handles fetching authenticated session data, tabs + form */}
      <HrSessionDetailClient
        sessionId={sessionId}
        sessionData={null}
      />
    </div>
  );
}
