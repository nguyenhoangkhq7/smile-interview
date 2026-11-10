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
          <Link href="/practice" className="inline-flex items-center gap-2 text-sm font-medium text-(--practice-primary) hover:underline">
            <ArrowLeft size={16} aria-hidden="true" /> Quay lại danh sách ôn tập
          </Link>
          <PracticePlanDetail key={profileId} profileId={profileId} />
        </div>
      </div>
    </ProtectedRoute>
  );
}
