import type { Metadata } from 'next';
import ProtectedRoute from '@/components/auth/ProtectedRoute';
import { AdminDashboardView } from '@/components/features/admin';

export const metadata: Metadata = {
  title: 'Bảng Điều Phối Admin',
  description:
    'Theo dõi hoạt động, chất lượng AI và tình trạng vận hành Smile Interview.',
};

export default function AdminPage() {
  return (
    <ProtectedRoute requiredRole="ADMIN">
      <AdminDashboardView />
    </ProtectedRoute>
  );
}
