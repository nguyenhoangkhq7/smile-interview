import axiosClient from '@/lib/axiosClient';
import type { AuditDetail, AuditFilter, AuditPage } from '@/components/features/admin/audit-logs/types';

const path = '/api/admin/audit-logs';
const baseURL = '/';

export function getTodayAuditDate(): string {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Ho_Chi_Minh',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date());
  const year = parts.find((p) => p.type === 'year')?.value ?? '2026';
  const month = parts.find((p) => p.type === 'month')?.value ?? '01';
  const day = parts.find((p) => p.type === 'day')?.value ?? '01';
  return `${year}-${month}-${day}`;
}

function shiftAuditDate(baseIsoDate: string, daysDelta: number, monthsDelta = 0): string {
  const [y, m, d] = baseIsoDate.split('-').map(Number);
  const dt = new Date(Date.UTC(y, m - 1 + monthsDelta, d + daysDelta));
  const year = dt.getUTCFullYear();
  const month = String(dt.getUTCMonth() + 1).padStart(2, '0');
  const day = String(dt.getUTCDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export function resolveAuditDateRange(filter: AuditFilter): { from?: string; to?: string } {
  const today = getTodayAuditDate();
  switch (filter.datePreset) {
    case 'today':
      return { from: today, to: today };
    case '7d':
      return { from: shiftAuditDate(today, -6), to: today };
    case '1m':
      return { from: shiftAuditDate(today, 0, -1), to: today };
    case '2m':
      return { from: shiftAuditDate(today, 0, -2), to: today };
    case 'day':
      return filter.date ? { from: filter.date, to: filter.date } : {};
    case 'range':
      return {
        from: filter.fromDate || undefined,
        to: filter.toDate || undefined,
      };
    default:
      return {};
  }
}

function params(filter: AuditFilter) {
  const range = resolveAuditDateRange(filter);
  return {
    search: filter.search.trim() || undefined,
    actorId: filter.actorId || undefined,
    action: filter.action || undefined,
    from: range.from,
    to: range.to,
  };
}

export const adminAudit = {
  async list(filter: AuditFilter, page: number, signal: AbortSignal) {
    return (await axiosClient.get<AuditPage>(path, { baseURL, signal, params: { ...params(filter), page } })).data;
  },
  async detail(id: string, signal: AbortSignal) {
    return (await axiosClient.get<AuditDetail>(path + '/' + id, { baseURL, signal })).data;
  },
  async export(filter: AuditFilter) {
    return (await axiosClient.get<Blob>(path + '/export', { baseURL, params: params(filter), responseType: 'blob' })).data;
  },
};
