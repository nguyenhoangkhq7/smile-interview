'use client';

import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { IconSearch } from '@/components/ui/icons';
import type { TimeFilter, ScoreFilter } from '@/hooks/useHistoryFilter';

interface HistoryFiltersProps {
  searchTerm:    string;
  timeFilter:    TimeFilter;
  scoreFilter:   ScoreFilter;
  onSearch:      (v: string) => void;
  onTimeFilter:  (v: TimeFilter) => void;
  onScoreFilter: (v: ScoreFilter) => void;
}

export function HistoryFilters({
  searchTerm, timeFilter, scoreFilter,
  onSearch, onTimeFilter, onScoreFilter,
}: HistoryFiltersProps) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row">
      {/* Search */}
      <div className="relative flex-1">
        <IconSearch size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
        <Input
          type="text"
          placeholder="Tìm kiếm theo tên file, level, category..."
          value={searchTerm}
          onChange={(e) => onSearch(e.target.value)}
          className="pl-9"
        />
      </div>

      {/* Time filter */}
      <Select value={timeFilter} onValueChange={(v) => onTimeFilter(v as TimeFilter)}>
        <SelectTrigger className="w-full sm:w-40">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">Tất cả thời gian</SelectItem>
          <SelectItem value="month">Tháng này</SelectItem>
          <SelectItem value="week">Tuần này</SelectItem>
        </SelectContent>
      </Select>

      {/* Score filter */}
      <Select value={scoreFilter} onValueChange={(v) => onScoreFilter(v as ScoreFilter)}>
        <SelectTrigger className="w-full sm:w-40">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">Tất cả điểm số</SelectItem>
          <SelectItem value="high">Trên 80</SelectItem>
          <SelectItem value="medium">60 – 80</SelectItem>
          <SelectItem value="low">Dưới 60</SelectItem>
        </SelectContent>
      </Select>
    </div>
  );
}
