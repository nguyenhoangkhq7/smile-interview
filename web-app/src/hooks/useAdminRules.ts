'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  adminService,
  type JobCategoryDto,
  type EvaluationCriteriaDto,
  type CategoryCriteriaMappingDto,
  type LevelDistributionRuleDto,
  type SystemSettingDto,
} from '@/services/adminService';

export interface AdminData {
  categories:  JobCategoryDto[];
  criteria:    EvaluationCriteriaDto[];
  mappings:    CategoryCriteriaMappingDto[];
  levelRules:  LevelDistributionRuleDto[];
  settings:    SystemSettingDto[];
}

const INITIAL_DATA: AdminData = {
  categories: [], criteria: [], mappings: [], levelRules: [], settings: [],
};

export function useAdminRules() {
  const [data,    setData]    = useState<AdminData>(INITIAL_DATA);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState<string | null>(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [categories, criteria, mappings, levelRules, settings] = await Promise.all([
        adminService.getJobCategories(),
        adminService.getEvaluationCriteria(),
        adminService.getCategoryMappings(),
        adminService.getLevelDistributionRules(),
        adminService.getSystemSettings(),
      ]);
      setData({ categories, criteria, mappings, levelRules, settings });
    } catch (err) {
      setError('Không thể tải dữ liệu. Kiểm tra kết nối đến matching-service (port 8081).');
      console.error('[useAdminRules]', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const stats = [
    { label: 'Danh mục', value: data.categories.length,  tone: 'orange'  as const },
    { label: 'Tiêu chí', value: data.criteria.length,    tone: 'blue'    as const },
    { label: 'Mappings', value: data.mappings.length,     tone: 'violet'  as const },
    { label: 'Cấp bậc',  value: data.levelRules.length,  tone: 'emerald' as const },
  ];

  return { data, loading, error, fetchAll, stats };
}
