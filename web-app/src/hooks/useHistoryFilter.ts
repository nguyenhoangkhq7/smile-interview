'use client';

import { useState, useEffect, useMemo } from 'react';
import { historyService, type SessionHistoryItem } from '@/services/historyService';

export type TimeFilter = 'all' | 'week' | 'month';
export type ScoreFilter = 'all' | 'high' | 'medium' | 'low';

function normalizeScore(item: SessionHistoryItem): number {
  if (item.overallScore !== undefined && item.overallScore !== null) {
    return item.overallScore <= 10 ? item.overallScore * 10 : item.overallScore;
  }
  return item.competencyFitScore ?? 0;
}

export function useHistoryFilter() {
  const [searchTerm, setSearchTerm]   = useState('');
  const [timeFilter, setTimeFilter]   = useState<TimeFilter>('all');
  const [scoreFilter, setScoreFilter] = useState<ScoreFilter>('all');
  const [historyData, setHistoryData] = useState<SessionHistoryItem[]>([]);
  const [loading, setLoading]         = useState(true);

  useEffect(() => {
    historyService.getHistory()
      .then(setHistoryData)
      .catch((err) => console.error('[useHistoryFilter]', err))
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    return historyData.filter((item) => {
      // Search
      const title = item.roleTitle || item.cvFilename || '';
      const matchSearch =
        !searchTerm ||
        title.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (item.candidateLevel || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
        (item.roleTypeDetected || '').toLowerCase().includes(searchTerm.toLowerCase());
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
    searchTerm, setSearchTerm,
    timeFilter, setTimeFilter,
    scoreFilter, setScoreFilter,
  };
}
