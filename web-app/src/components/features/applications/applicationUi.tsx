import { attemptLabels, InterviewAttempt } from '@/services/applicationProfiles';

export function formatProfileDate(value: string | null, includeTime = false) {
  if (!value) return 'Chưa có';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Chưa có';
  return new Intl.DateTimeFormat('vi-VN', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    ...(includeTime ? { hour: '2-digit', minute: '2-digit' } as const : {}),
  }).format(date);
}

export function activeAttempt(attempts: InterviewAttempt[]) {
  return attempts.find(attempt => ['Not started', 'In progress'].includes(attempt.status));
}

export function finishedAttempt(attempt: InterviewAttempt) {
  return !['Not started', 'In progress'].includes(attempt.status);
}

export function searchText(value: string) {
  return value.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/g, 'd');
}

export function skillLabel(value: string) {
  const labels: Record<string, string> = {
    html_css: 'HTML / CSS', html: 'HTML', css: 'CSS', javascript: 'JavaScript', typescript: 'TypeScript',
    sql: 'SQL', postgresql: 'PostgreSQL', mysql: 'MySQL', java: 'Java', python: 'Python',
    react: 'React', reactjs: 'React', nodejs: 'Node.js', git: 'Git', docker: 'Docker',
    spring_boot: 'Spring Boot', rest_api: 'REST API', mongodb: 'MongoDB', aws: 'AWS',
  };
  return labels[value.toLowerCase()] || value.replace(/_/g, ' ');
}

export function AttemptBadge({ attempt }: { attempt: InterviewAttempt }) {
  const color = attempt.status === 'In progress' ? 'bg-orange-50 text-orange-800 ring-orange-200/70'
    : attempt.status === 'Completed' ? 'bg-emerald-50 text-emerald-800 ring-emerald-200/70'
      : attempt.status === 'Stopped early' ? 'bg-amber-50 text-amber-800 ring-amber-200/70'
        : 'bg-muted/70 text-muted-foreground ring-border';
  return <span className={`inline-flex max-w-full items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset ${color}`}>
    <span className="size-1.5 shrink-0 rounded-full bg-current" aria-hidden="true" />{attemptLabels[attempt.status]}
  </span>;
}
