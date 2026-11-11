import { useState } from 'react';
import { searchText } from '@/components/features/applications/applicationUi';
import type { PracticeFilter, PracticePlan } from '@/components/features/practice/practicePlans';

export function usePracticePlanFilters(plans: readonly PracticePlan[]) {
  const [status, setStatus] = useState<PracticeFilter>('all');
  const [query, setQuery] = useState('');
  const keyword = searchText(query.trim());
  const counts: Record<PracticeFilter, number> = {
    all: plans.length,
    'no-result': 0,
    'has-result': 0,
  };
  for (const plan of plans) counts[plan.status]++;

  const filteredPlans = plans.filter((plan) =>
    (status === 'all' || plan.status === status)
    && searchText(`${plan.title} ${plan.roleTitle} ${plan.company ?? ''}`).includes(keyword),
  );

  function reset() {
    setStatus('all');
    setQuery('');
  }

  return { status, setStatus, query, setQuery, counts, filteredPlans, reset };
}
