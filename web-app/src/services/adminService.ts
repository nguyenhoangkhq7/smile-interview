import axiosClient from '@/lib/axiosClient';
import { HrEvaluationAdminItem } from '@/components/features/admin/evaluations/types';

export const adminService = {
  async getHrEvaluations(): Promise<HrEvaluationAdminItem[]> {
    const { data } = await axiosClient.get<HrEvaluationAdminItem[]>('/api/v1/hr-evaluations/all');
    return data;
  },
};
