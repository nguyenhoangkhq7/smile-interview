import { IconClock } from '@/components/ui/icons';

export function EmptyHistory() {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-center text-muted-foreground">
      <IconClock size={48} className="opacity-30" />
      <p className="text-sm">Không có phiên phỏng vấn nào để hiển thị.</p>
      <p className="text-xs opacity-70">Hãy tạo một phiên phỏng vấn mới để bắt đầu!</p>
    </div>
  );
}
