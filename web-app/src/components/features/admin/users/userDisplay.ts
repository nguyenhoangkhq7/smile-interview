const dates = new Intl.DateTimeFormat('vi-VN', { dateStyle: 'short' });

export function userInitials(name: string) {
  const words = name.trim().split(/\s+/);
  return words.slice(0, words.length > 1 ? 2 : 1).map(word => word.slice(0, words.length === 1 ? 2 : 1))
    .join('').toLocaleUpperCase('vi-VN');
}

export function userDate(value: string) {
  return dates.format(new Date(value));
}
