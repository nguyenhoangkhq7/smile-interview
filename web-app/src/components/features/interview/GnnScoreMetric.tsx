const percentage = new Intl.NumberFormat('vi-VN', {
  style: 'percent',
  maximumFractionDigits: 2,
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
        Độ phù hợp CV–JD (GNN)
      </div>
    </div>
  );
}
