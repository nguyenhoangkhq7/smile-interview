import type { Metadata } from 'next';
import { AdminDashboardView } from '@/components/features/admin';

export const metadata: Metadata = {
  title: 'Bảng Điều Phối Admin',
  description:
    'Theo dõi hoạt động, chất lượng AI và tình trạng vận hành Smile Interview trong thời gian thực.',
};

export default function AdminPage() {
  return <AdminDashboardView />;
}
