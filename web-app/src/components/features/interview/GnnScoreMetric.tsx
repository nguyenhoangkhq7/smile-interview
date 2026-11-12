const percentage = new Intl.NumberFormat('vi-VN', {
  style: 'percent',
  maximumFractionDigits: 0,
});

export function GnnScoreMetric({ score }: { score?: number | null }) {
  const hasScore = typeof score === 'number' && Number.isFinite(score) && score >= 0 && score <= 1;

  return (
    <div className="rounded-xl border border-brand-green/20 bg-brand-green/5 p-4 text-center">
      {hasScore ? (
        <div className="text-2xl font-bold tabular-nums text-brand-green">{percentage.format(score)}</div>
      ) : (
        <div className="text-sm font-medium text-muted-foreground">Chưa có điểm</div>
      )}
      <div className="mt-1 text-[11px] font-medium text-muted-foreground">
        Mức phù hợp của CV với công việc
      </div>
      <p className="mt-2 text-xs leading-5 text-muted-foreground">Ước tính từ nội dung tài liệu, chưa phải kết quả đánh giá qua phỏng vấn.</p>
    </div>
  );
}
