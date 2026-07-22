import Link from 'next/link';
import { Badge } from '@/components/ui/badge';
import { buttonVariants } from '@/components/ui/button';
import { IconClock } from '@/components/ui/icons';
import type { SessionHistoryItem } from '@/services/historyService';
import { cn } from '@/lib/utils';

interface HistoryItemCardProps {
  item: SessionHistoryItem;
}

function formatDate(dateStr: string): string {
  try {
    return new Date(dateStr).toLocaleDateString('vi-VN', {
      year: 'numeric', month: 'numeric', day: 'numeric',
    });
  } catch {
    return dateStr;
  }
}

function formatScore(item: SessionHistoryItem): string {
  if (item.status === 'Completed' && item.overallScore != null) {
    return item.overallScore <= 10
      ? `${item.overallScore}/10`
      : `${item.overallScore}`;
  }
  if (item.competencyFitScore != null) return `${item.competencyFitScore}% (CV Match)`;
  return 'N/A';
}

export function HistoryItemCard({ item }: HistoryItemCardProps) {
  const isCompleted = item.status === 'Completed';
  const actionLink  = isCompleted
    ? `/interview/session/${item.id}/result`
    : `/interview/session/${item.id}`;

  return (
    <div className="flex flex-col gap-4 rounded-xl border border-border bg-card p-5 shadow-sm transition-all hover:border-brand-orange/30 hover:shadow-md sm:flex-row sm:items-center sm:justify-between">
      {/* Content */}
      <div className="flex-1 space-y-2.5">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-semibold text-foreground">
            {item.roleTitle || item.cvFilename || 'Không rõ vị trí'}
          </span>
          <Badge variant={isCompleted ? 'default' : 'secondary'} className={isCompleted
            ? 'bg-brand-green/15 text-brand-green hover:bg-brand-green/25'
            : 'bg-brand-orange/10 text-brand-orange hover:bg-brand-orange/20'
          }>
            {isCompleted ? 'Đã hoàn thành' : 'Đang phỏng vấn'}
          </Badge>
        </div>

        <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-muted-foreground">
          <span><span className="font-medium text-foreground">Điểm:</span> {formatScore(item)}</span>
          <span><span className="font-medium text-foreground">Cấp độ:</span> {item.candidateLevel || 'N/A'}</span>
          <span><span className="font-medium text-foreground">Ngành:</span> {item.roleTypeDetected || 'N/A'}</span>
          <span><span className="font-medium text-foreground">Ngày:</span> {formatDate(item.date)}</span>
        </div>
      </div>

      {/* Actions */}
      <div className="flex shrink-0 flex-wrap gap-2">
        {!isCompleted && item.competencyFitScore !== undefined && (
          <Link
            href={`/interview/new?sessionId=${item.id}`}
            className={cn(
              buttonVariants({ variant: 'outline', size: 'sm' }),
              "border-brand-green/30 text-brand-green hover:bg-brand-green/5"
            )}
          >
            Xem kết quả CV
          </Link>
        )}
        <Link
          href={actionLink}
          className={cn(
            buttonVariants({ size: 'sm' }),
            "bg-brand-orange text-white hover:bg-brand-orange-hover flex items-center gap-1.5"
          )}
        >
          <IconClock size={13} />
          {isCompleted ? 'Xem báo cáo' : 'Tiếp tục'}
        </Link>
      </div>
    </div>
  );
}
