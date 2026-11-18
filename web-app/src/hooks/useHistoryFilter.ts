'use client';

import { useState, useEffect, useMemo } from 'react';
import { historyService, type SessionHistoryItem } from '@/services/historyService';
import { useAuthStore } from '@/store/authStore';

export type TimeFilter = 'all' | 'week' | 'month';
export type ScoreFilter = 'all' | 'high' | 'medium' | 'low';

function normalizeScore(item: SessionHistoryItem): number {
  if (item.overallScore !== undefined && item.overallScore !== null) {
    return item.overallScore <= 10 ? item.overallScore * 10 : item.overallScore;
  }
  return 0;
}

export function useHistoryFilter() {
  const token = useAuthStore((state) => state.token);
  const [searchTerm, setSearchTerm]   = useState('');
  const [timeFilter, setTimeFilter]   = useState<TimeFilter>('all');
  const [scoreFilter, setScoreFilter] = useState<ScoreFilter>('all');
  const [historyData, setHistoryData] = useState<SessionHistoryItem[]>([]);
  const [loading, setLoading]         = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!token) return;
    let active = true;
    historyService.getHistory()
      .then((items) => { if (active) setHistoryData(items); })
      .catch(() => {
        if (active) setError('Không thể tải lịch sử phỏng vấn. Vui lòng thử lại.');
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [token, reloadKey]);

  const retry = () => {
    setError(null);
    setLoading(true);
    setReloadKey((key) => key + 1);
  };

  const filtered = useMemo(() => {
    return historyData.filter((item) => {
      // Search
      const title = [item.roleTitle, item.cvFilename, item.applicationProfileTitle].filter(Boolean).join(' ');
      const matchSearch =
        !searchTerm ||
        title.toLowerCase().includes(searchTerm.toLowerCase());
      if (!matchSearch) return false;

      // Time
      if (timeFilter !== 'all') {
        const diffDays = Math.ceil(
          Math.abs(Date.now() - new Date(item.date).getTime()) / 86_400_000
        );
        if (timeFilter === 'week' && diffDays > 7) return false;
        if (timeFilter === 'month' && diffDays > 30) return false;
      }

      // Score
      if (scoreFilter !== 'all') {
        const score = normalizeScore(item);
        if (scoreFilter === 'high'   && score < 80)               return false;
        if (scoreFilter === 'medium' && (score < 60 || score > 80)) return false;
        if (scoreFilter === 'low'    && score >= 60)              return false;
      }

      return true;
    });
  }, [historyData, searchTerm, timeFilter, scoreFilter]);

  return {
    filtered,
    loading,
    error, retry,
    searchTerm, setSearchTerm,
    timeFilter, setTimeFilter,
    scoreFilter, setScoreFilter,
  };
}
