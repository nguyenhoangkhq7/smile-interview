import axiosClient from '@/lib/axiosClient';
import type {
  NewStudyTask, StudyChecklistItem, StudyProgress, StudyTask, StudyTaskFields, StudyResource,
} from '@/components/features/practice/studyPlan';
import type { CompetencySource, CompetencyStatus, CurrentCompetency } from './applicationProfiles';

type TaskRecord = Omit<StudyTask, 'checklist' | 'resources'>;
export type StudySkill = CurrentCompetency['skills'][number];

export interface CriterionSuggestion {
  criterionId: string;
  description: string;
  essential: boolean;
  assessment: CompetencyStatus;
  kind: 'REVIEW' | 'VERIFY' | 'REINFORCE' | 'UNASSESSED' | 'MET';
  selectedByDefault: boolean;
  reason: string;
  goal: string;
  source: CompetencySource | null;
  lastAssessment: CompetencySource | null;
}

export interface ObjectiveSuggestion {
  skillId: string;
  objectiveId: string;
  claim: string;
  assessment: CompetencyStatus;
  source: CompetencySource | null;
  criteria: CriterionSuggestion[];
}

export interface ReportWeakness {
  skillId: string;
  sessionId: string;
  attemptNumber: number;
  weaknesses: string[];
}

export interface KnowledgeGaps {
  completedAttempts: number;
  weak: StudySkill[];
  needsVerification: StudySkill[];
  notAssessedSkillIds: string[];
  reportWeaknesses: ReportWeakness[];
  objectiveSuggestions?: ObjectiveSuggestion[];
}

export interface StudyPlanDetails {
  title: string;
  description: string | null;
  targetCompletionPercent: number;
  targetDate: string | null;
  sourceSessionId: string | null;
}

interface PlanResponse {
  plan: StudyPlanDetails;
  progress: StudyProgress;
  tasks: { task: TaskRecord; checklist: StudyChecklistItem[]; resources: StudyResource[] }[];
}

export interface StudyPlanView extends Omit<PlanResponse, 'tasks'> {
  tasks: StudyTask[];
}

interface PlanProgress {
  applicationProfileId: string;
  progress: StudyProgress;
}

const profilesPath = '/api/v1/application-profiles';
const planPath = (profileId: string) => `${profilesPath}/${encodeURIComponent(profileId)}/study-plan`;
const taskPath = (profileId: string, taskId: number) => `${planPath(profileId)}/tasks/${taskId}`;

function toPlanView({ plan, progress, tasks }: PlanResponse): StudyPlanView {
  return { plan, progress, tasks: tasks.map(({ task, checklist, resources }) => ({ ...task, checklist, resources })) };
}

export const studyPlans = {
  async get(profileId: string, signal?: AbortSignal) {
    return toPlanView((await axiosClient.get<PlanResponse>(planPath(profileId), { signal })).data);
  },
  async listProgress(signal: AbortSignal) {
    return (await axiosClient.get<PlanProgress[]>(`${profilesPath}/study-plan-progress`, { signal })).data;
  },
  async gaps(profileId: string, signal: AbortSignal) {
    return (await axiosClient.get<KnowledgeGaps>(`${planPath(profileId)}/knowledge-gaps`, { signal })).data;
  },
  async updatePlan(profileId: string, input: StudyPlanDetails) {
    return toPlanView((await axiosClient.put<PlanResponse>(planPath(profileId), input)).data);
  },
  async createTask(profileId: string, { checklist, checklistOrigins, referenceUrl, gapOrigin, ...task }: NewStudyTask) {
    return (await axiosClient.post<TaskRecord>(`${planPath(profileId)}/tasks`, {
      ...task,
      gapOrigin,
      checklist: checklist.map((content, sortOrder) => ({ content, sortOrder, ...checklistOrigins?.[sortOrder] })),
      resource: referenceUrl ? { title: 'Tài liệu tham khảo', url: referenceUrl } : undefined,
    })).data;
  },
  async updateTask(profileId: string, taskId: number, input: StudyTaskFields) {
    await axiosClient.put(taskPath(profileId, taskId), input);
  },
  async moveTask(profileId: string, taskId: number, status: StudyTaskFields['status'], beforeTaskId: number | null) {
    await axiosClient.put(`${taskPath(profileId, taskId)}/position`, { status, beforeTaskId });
  },
  async updateTaskParent(profileId: string, taskId: number, parentTaskId: number | null, status?: StudyTaskFields['status']) {
    await axiosClient.put(`${taskPath(profileId, taskId)}/parent`, { parentTaskId, status });
  },
  async deleteTask(profileId: string, taskId: number) {
    await axiosClient.delete(taskPath(profileId, taskId));
  },
  async addChecklist(profileId: string, taskId: number, content: string, sortOrder: number) {
    await axiosClient.post(`${taskPath(profileId, taskId)}/checklist`, { content, sortOrder });
  },
  async updateChecklist(profileId: string, taskId: number, { id, content, sortOrder, isCompleted }: StudyChecklistItem) {
    await axiosClient.put(`${taskPath(profileId, taskId)}/checklist/${id}`, { content, sortOrder, isCompleted });
  },
  async deleteChecklist(profileId: string, taskId: number, itemId: number) {
    await axiosClient.delete(`${taskPath(profileId, taskId)}/checklist/${itemId}`);
  },
  async addResource(profileId: string, taskId: number, title: string, url: string) {
    await axiosClient.post(`${taskPath(profileId, taskId)}/resources`, { title, url });
  },
  async updateResource(profileId: string, taskId: number, resourceId: number, title: string, url: string) {
    await axiosClient.put(`${taskPath(profileId, taskId)}/resources/${resourceId}`, { title, url });
  },
  async uploadResource(profileId: string, taskId: number, file: File) {
    const body = new FormData();
    body.append('file', file);
    await axiosClient.postForm(`${taskPath(profileId, taskId)}/resources/upload`, body);
  },
  async downloadResource(profileId: string, taskId: number, resourceId: number) {
    return (await axiosClient.get<Blob>(`${taskPath(profileId, taskId)}/resources/${resourceId}/file`, { responseType: 'blob' })).data;
  },
  async deleteResource(profileId: string, taskId: number, resourceId: number) {
    await axiosClient.delete(`${taskPath(profileId, taskId)}/resources/${resourceId}`);
  },
};
