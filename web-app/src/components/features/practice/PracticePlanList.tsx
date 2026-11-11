'use client';

import { Search, SearchX } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { usePracticePlanFilters } from '@/hooks/usePracticePlanFilters';
import { PracticePlanCard } from './PracticePlanCard';
import { practiceStatuses, type PracticePlan } from './practicePlans';

const filters = [{ value: 'all', label: 'Tất cả' }, ...practiceStatuses] as const;

interface PracticePlanEmptyStateProps {
  onReset: () => void;
}

function PracticePlanEmptyState({ onReset }: PracticePlanEmptyStateProps) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-2xl border border-slate-100 bg-card px-5 py-10 text-center shadow-xs">
      <span className="grid size-12 place-items-center rounded-full bg-(--practice-blue) text-(--practice-muted)">
        <SearchX size={22} aria-hidden="true" />
      </span>
      <p role="status" className="font-semibold">Không tìm thấy kế hoạch ôn tập phù hợp</p>
      <p className="text-sm text-(--practice-muted)">Hãy thử từ khóa hoặc bộ lọc trạng thái khác.</p>
      <Button
        type="button"
        onClick={onReset}
        className="h-9 rounded-full bg-(--practice-primary) px-4 hover:bg-(--practice-primary-hover)"
      >
        Đặt lại bộ lọc
      </Button>
    </div>
  );
}

export interface PracticePlanListProps {
  plans: readonly PracticePlan[];
}

export function PracticePlanList({ plans }: PracticePlanListProps) {
  const { status, setStatus, query, setQuery, counts, filteredPlans, reset } = usePracticePlanFilters(plans);

  return (
    <section aria-label="Danh sách kế hoạch ôn tập" className="space-y-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div role="group" aria-label="Lọc theo kết quả phỏng vấn" className="flex w-fit flex-wrap gap-1 rounded-2xl bg-(--practice-blue-strong) p-1 sm:rounded-full">
          {filters.map(({ value, label }) => (
            <Button
              key={value}
              type="button"
              variant="ghost"
              size="sm"
              aria-pressed={status === value}
              onClick={() => setStatus(value)}
              className={cn('h-8 rounded-full px-3 text-xs font-semibold sm:px-4',
                status === value ? 'bg-card text-(--practice-primary) shadow-xs hover:bg-card' : 'text-(--practice-muted) hover:bg-white/60')}
            >
              {label} ({counts[value]})
            </Button>
          ))}
        </div>
        <div className="relative block w-full lg:max-w-80">
          <label htmlFor="practice-plan-search" className="sr-only">
            Tìm theo vị trí hoặc công ty
          </label>
          <Search size={16} className="pointer-events-none absolute inset-y-0 left-3 my-auto text-(--practice-muted)" aria-hidden="true" />
          <Input
            id="practice-plan-search"
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Tìm theo vị trí hoặc công ty..."
            className="h-10 rounded-full border-slate-200/60 bg-card pr-4 pl-9 shadow-xs"
          />
        </div>
      </div>
      {filteredPlans.length ? (
        <div className="grid gap-4 lg:grid-cols-2 lg:gap-5">
          {filteredPlans.map((plan) => <PracticePlanCard key={plan.id} plan={plan} />)}
        </div>
      ) : (
        <PracticePlanEmptyState onReset={reset} />
      )}
    </section>
  );
}
