import type { Metadata } from 'next';
import ProtectedRoute from '@/components/auth/ProtectedRoute';
import { PracticeHeading } from '@/components/features/practice/PracticeOverview';
import { PracticeProfilesContent } from '@/components/features/practice/PracticeProfileContent';
import styles from '@/components/features/practice/practice.module.css';

export const metadata: Metadata = {
  title: 'Ôn tập | Smile Interview',
};

export default function PracticePage() {
  return (
    <ProtectedRoute>
      <div className={styles.surface}>
        <div className="mx-auto max-w-7xl space-y-6 px-4 py-7 sm:px-6 sm:py-9 lg:px-12">
          <PracticeHeading />
          <PracticeProfilesContent />
        </div>
      </div>
    </ProtectedRoute>
  );
}
