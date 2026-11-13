import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';
import ProtectedRoute from '@/components/auth/ProtectedRoute';
import { PracticePlanDetail } from '@/components/features/practice/PracticeProfileContent';
import styles from '@/components/features/practice/practice.module.css';

export default async function PracticePlanPage({ params }: { params: Promise<{ planId: string }> }) {
  const { planId: profileId } = await params;

  return (
    <ProtectedRoute>
      <div className={styles.surface}>
        <div className="mx-auto max-w-[90rem] space-y-5 px-4 py-8 sm:px-6 lg:px-12">
          <Link
            href="/practice"
            className="group inline-flex items-center gap-2 text-xs font-semibold text-slate-500 hover:text-(--practice-primary) transition-colors"
          >
            <span className="grid size-6 place-items-center rounded-full bg-card border border-slate-200/80 shadow-xs transition-transform group-hover:-translate-x-0.5">
              <ArrowLeft size={13} aria-hidden="true" />
            </span>
            <span>Quay lại danh sách ôn tập</span>
          </Link>
          <PracticePlanDetail key={profileId} profileId={profileId} />
        </div>
      </div>
    </ProtectedRoute>
  );
}
