import type { Metadata } from 'next';
import HrRoute from '@/components/auth/HrRoute';
import { HrNavbar } from '@/components/features/hr';

export const metadata: Metadata = {
  title: 'HR Workspace — Smile Interview',
  description: 'Cổng thông tin làm việc và đánh giá chuyên môn dành cho chuyên viên HR.',
  robots: { index: false, follow: false },
};

/**
 * Dedicated Corporate Layout for HR Workspace (/hr-dashboard/**).
 * Completely isolated from candidate (main) layout.
 * Includes HrRoute role guard & HrNavbar.
 */
export default function HrLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <HrRoute>
      <div className="flex min-h-screen flex-col bg-slate-50 font-sans text-slate-900">
        <HrNavbar />
        <main className="flex-1 bg-slate-50 p-6 min-h-[calc(100vh-64px)]">
          {children}
        </main>
      </div>
    </HrRoute>
  );
}
