import type { AdminNavItem, TimeRangeKey } from '../types';

export const ADMIN_NAV_ITEMS: AdminNavItem[] = [
  { key: 'tong-quan', label: 'Tổng quan' },
  { key: 'nguoi-dung', label: 'Người dùng' },
  { key: 'phien-phong-van', label: 'Phiên phỏng vấn' },
  { key: 'hang-doi-va-luu-tru', label: 'Hàng đợi & Lưu trữ' },
  { key: 'ai-va-chinh-sach', label: 'AI & Chính sách' },
  { key: 'nhat-ky-quan-tri', label: 'Nhật ký quản trị' },
];

export const TIME_RANGE_OPTIONS: { key: TimeRangeKey; label: string }[] = [
  { key: '7d', label: '7 ngày' },
  { key: '30d', label: '30 ngày' },
  { key: '90d', label: '90 ngày' },
  { key: 'all', label: 'Toàn thời gian' },
];
