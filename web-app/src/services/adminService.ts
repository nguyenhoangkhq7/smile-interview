import axiosClient from '@/lib/axiosClient';
import { HrEvaluationAdminItem } from '@/components/features/admin/evaluations/types';

// ─── TypeScript Interfaces matching Backend DTOs ──────────────────────────────

export interface JobCategoryDto {
  id: number;
  code: string;
  name: string;
  parent_id: number | null;
}

export interface EvaluationCriteriaDto {
  id: number;
  name: string;
  category: string | null;
  question_type: string | null;
  prompt_instruction: string | null;
  /** Distinct seniority levels that have a CategoryCriteriaMapping for this criteria */
  mapped_levels?: string[];
}

export interface CategoryCriteriaMappingDto {
  category_id: number;
  criteria_id: number;
  level: string;
  weight_percentage: number;
}

export interface LevelDistributionRuleDto {
  id: number;
  level: string;
  behavioral_pct: number;
  technical_pct: number;
  coding_pct: number;
  system_design_pct: number;
  total_questions?: number;
}

export interface SystemSettingDto {
  id: number;
  setting_key: string;
  setting_value: string;
  description: string | null;
  updated_at: string | null;
}

// ─── Payload types for mutating operations ────────────────────────────────────

export type CreateJobCategoryPayload = Pick<JobCategoryDto, 'code' | 'name' | 'parent_id'>;
export type UpdateJobCategoryPayload = Pick<JobCategoryDto, 'code' | 'name' | 'parent_id'>;

export type CreateEvaluationCriteriaPayload = Pick<EvaluationCriteriaDto, 'name' | 'category' | 'question_type' | 'prompt_instruction'>;
export type UpdateEvaluationCriteriaPayload = Pick<EvaluationCriteriaDto, 'name' | 'category' | 'question_type' | 'prompt_instruction'>;

export type CreateMappingPayload = Pick<CategoryCriteriaMappingDto, 'category_id' | 'criteria_id' | 'level' | 'weight_percentage'>;
export type UpdateMappingPayload = Pick<CategoryCriteriaMappingDto, 'weight_percentage'>;

export type UpdateLevelRulePayload = Pick<LevelDistributionRuleDto, 'behavioral_pct' | 'technical_pct' | 'coding_pct' | 'system_design_pct' | 'total_questions'>;
export type UpdateSystemSettingPayload = Pick<SystemSettingDto, 'setting_value'>;

// ─── Service ──────────────────────────────────────────────────────────────────

export const adminService = {

  // ── Job Categories ──────────────────────────────────────────────────────────

  async getJobCategories(): Promise<JobCategoryDto[]> {
    const { data } = await axiosClient.get<JobCategoryDto[]>('/api/admin/job-categories');
    return data;
  },

  async createJobCategory(payload: CreateJobCategoryPayload): Promise<JobCategoryDto> {
    const { data } = await axiosClient.post<JobCategoryDto>('/api/admin/job-categories', payload);
    return data;
  },

  async updateJobCategory(id: number, payload: UpdateJobCategoryPayload): Promise<JobCategoryDto> {
    const { data } = await axiosClient.put<JobCategoryDto>(`/api/admin/job-categories/${id}`, payload);
    return data;
  },

  async deleteJobCategory(id: number): Promise<void> {
    await axiosClient.delete(`/api/admin/job-categories/${id}`);
  },

  // ── Evaluation Criteria ─────────────────────────────────────────────────────

  async getEvaluationCriteria(): Promise<EvaluationCriteriaDto[]> {
    const { data } = await axiosClient.get<EvaluationCriteriaDto[]>('/api/admin/evaluation-criteria');
    return data;
  },

  async createEvaluationCriteria(payload: CreateEvaluationCriteriaPayload): Promise<EvaluationCriteriaDto> {
    const { data } = await axiosClient.post<EvaluationCriteriaDto>('/api/admin/evaluation-criteria', payload);
    return data;
  },

  async updateEvaluationCriteria(id: number, payload: UpdateEvaluationCriteriaPayload): Promise<EvaluationCriteriaDto> {
    const { data } = await axiosClient.put<EvaluationCriteriaDto>(`/api/admin/evaluation-criteria/${id}`, payload);
    return data;
  },

  async deleteEvaluationCriteria(id: number): Promise<void> {
    await axiosClient.delete(`/api/admin/evaluation-criteria/${id}`);
  },

  // ── Category–Criteria Mappings ──────────────────────────────────────────────

  async getCategoryMappings(): Promise<CategoryCriteriaMappingDto[]> {
    const { data } = await axiosClient.get<CategoryCriteriaMappingDto[]>('/api/admin/category-criteria-mappings');
    return data;
  },

  async createCategoryMapping(payload: CreateMappingPayload): Promise<CategoryCriteriaMappingDto> {
    const { data } = await axiosClient.post<CategoryCriteriaMappingDto>('/api/admin/category-criteria-mappings', payload);
    return data;
  },

  async updateCategoryMapping(
    categoryId: number,
    criteriaId: number,
    level: string,
    payload: UpdateMappingPayload
  ): Promise<CategoryCriteriaMappingDto> {
    const { data } = await axiosClient.put<CategoryCriteriaMappingDto>(
      `/api/admin/category-criteria-mappings/${categoryId}/${criteriaId}/${level}`,
      payload
    );
    return data;
  },

  async deleteCategoryMapping(categoryId: number, criteriaId: number, level: string): Promise<void> {
    await axiosClient.delete(`/api/admin/category-criteria-mappings/${categoryId}/${criteriaId}/${level}`);
  },

  // ── Level Distribution Rules ─────────────────────────────────────────────────

  async getLevelDistributionRules(): Promise<LevelDistributionRuleDto[]> {
    const { data } = await axiosClient.get<LevelDistributionRuleDto[]>('/api/admin/level-distribution-rules');
    return data;
  },

  async updateLevelDistributionRule(level: string, payload: UpdateLevelRulePayload): Promise<LevelDistributionRuleDto> {
    const { data } = await axiosClient.put<LevelDistributionRuleDto>(
      `/api/admin/level-distribution-rules/${level}`,
      payload
    );
    return data;
  },

  // ── System Settings ──────────────────────────────────────────────────────────

  async getSystemSettings(): Promise<SystemSettingDto[]> {
    const { data } = await axiosClient.get<SystemSettingDto[]>('/api/admin/system-settings');
    return data;
  },

  async updateSystemSetting(key: string, payload: UpdateSystemSettingPayload): Promise<SystemSettingDto> {
    const { data } = await axiosClient.put<SystemSettingDto>(`/api/admin/system-settings/${key}`, payload);
    return data;
  },

  // ── HR Evaluations ────────────────────────────────────────────────────────────

  async getHrEvaluations(): Promise<HrEvaluationAdminItem[]> {
    const { data } = await axiosClient.get<HrEvaluationAdminItem[]>('/api/v1/hr-evaluations/all');
    return data;
  },
};
