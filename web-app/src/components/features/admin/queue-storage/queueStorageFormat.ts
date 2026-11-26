const numbers = new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 1 });
const times = new Intl.DateTimeFormat('vi-VN', { dateStyle: 'short', timeStyle: 'medium' });
const units = ['B', 'KB', 'MB', 'GB', 'TB'];

const failures: Record<string, string> = {
  LEASE_EXPIRED: 'Lease đã hết hạn',
  INPUT_CHANGED: 'Hồ sơ hoặc dữ liệu đầu vào đã thay đổi',
  UPSTREAM: 'Dịch vụ AI trả lỗi',
  TIMEOUT: 'Dịch vụ AI phản hồi quá thời gian',
  PROCESSING_FAILED: 'Xử lý phân tích thất bại',
};

export function queueFailure(code: string | null) {
  return code ? failures[code] ?? 'Xử lý phân tích thất bại' : null;
}

export function queueTime(value: string | null) {
  return value ? times.format(new Date(value)) : '—';
}

export function storageBytes(bytes: number) {
  const exponent = bytes > 0 ? Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1) : 0;
  return numbers.format(bytes / 1024 ** exponent) + ' ' + units[exponent];
}
