'use client';

import ProtectedRoute from '@/components/auth/ProtectedRoute';
import { Skeleton } from '@/components/ui/skeleton';
import { useHistoryFilter } from '@/hooks/useHistoryFilter';
import { HistoryFilters } from '@/components/features/history/HistoryFilters';
import { HistoryItemCard } from '@/components/features/history/HistoryItemCard';
import { EmptyHistory } from '@/components/features/history/EmptyHistory';
import { IconClock } from '@/components/ui/icons';

export default function HistoryPage() {
  const {
    filtered, loading,
    searchTerm, setSearchTerm,
    timeFilter, setTimeFilter,
    scoreFilter, setScoreFilter,
  } = useHistoryFilter();

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-background">
        <div className="mx-auto max-w-4xl space-y-6 px-4 py-10 sm:px-6">

          {/* Header */}
          <div className="flex items-center gap-3">
            <span className="flex size-10 items-center justify-center rounded-xl bg-brand-orange/10 text-brand-orange">
              <IconClock size={20} />
            </span>
            <div>
              <h1 className="text-xl font-bold text-foreground">Lịch sử phân tích</h1>
              <p className="text-sm text-muted-foreground">Xem lại tất cả CV đã phân tích và kết quả đánh giá</p>
            </div>
          </div>

          {/* Filters */}
          <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
            <HistoryFilters
              searchTerm={searchTerm}   onSearch={setSearchTerm}
              timeFilter={timeFilter}   onTimeFilter={setTimeFilter}
              scoreFilter={scoreFilter} onScoreFilter={setScoreFilter}
            />
          </div>

          {/* List */}
          <div className="space-y-1">
            <div className="flex items-center justify-between px-1 pb-2">
              <h2 className="text-sm font-semibold text-foreground">Lịch sử phân tích CV</h2>
              <span className="text-xs text-muted-foreground">Tổng cộng: {filtered.length}</span>
            </div>

            {loading ? (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => <Skeleton key={i} className="h-24 rounded-xl" />)}
              </div>
            ) : filtered.length === 0 ? (
              <EmptyHistory />
            ) : (
              <div className="space-y-3">
                {filtered.map((item) => (
                  <HistoryItemCard key={item.id} item={item} />
                ))}
              </div>
            )}
          </div>

        </div>
      </div>
    </ProtectedRoute>
  );
}
