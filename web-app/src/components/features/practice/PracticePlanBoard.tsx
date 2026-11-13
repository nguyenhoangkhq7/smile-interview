'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import {
  ArrowRight, ClipboardList, LayoutGrid, ListChecks, Network, Radar, Search, Settings2, X, type LucideIcon,
} from 'lucide-react';
import { activeAttempt, finishedAttempt, skillLabel } from '@/components/features/applications/applicationUi';
import { Button, buttonVariants } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { usePracticeKnowledgeGaps } from '@/hooks/usePracticeProfiles';
import { useStudyPlan } from '@/hooks/useStudyPlan';
import { cn } from '@/lib/utils';
import type { ApplicationProfile } from '@/services/applicationProfiles';
import { studyPlans, type ObjectiveSuggestion, type ReportWeakness, type StudyPlanDetails, type StudyPlanView, type StudySkill } from '@/services/studyPlans';
import {
  formatStudyPercent as formatPercent,
  type NewStudyTask, type StudyChecklistItem, type StudyProgress as PlanProgress, type StudyTask, type StudyTaskStatus, type StudyTaskUpdate,
} from './studyPlan';
import { StudyTaskCreateDialog } from './StudyTaskCreateDialog';
import { PracticeMindMap } from './PracticeMindMap';
import type { MindMapPositions } from './useMindMapPosition';
import { PracticeTaskInspector } from './PracticeTaskInspector';
import { StudyPlanSettings } from './StudyPlanSettings';
import { Dialog } from '@/components/ui/dialog';
import { StudyKanban } from './StudyKanban';
import { StudyGapCard, type StudyGap, type StudyGapActions } from './StudyGapCard';
import { StudyGapTaskDialog } from './StudyGapTaskDialog';
import styles from './practice.module.css';

const panelStyle = 'flex min-w-0 flex-col rounded-2xl border border-slate-100 bg-card p-4 shadow-xs sm:p-5';
const workspacePanelStyle = cn(panelStyle, 'min-h-0 gap-4');
const workspaceScrollStyle = 'min-h-0 flex-1 xl:overflow-y-auto';
const mutedText = 'text-sm leading-6 text-(--practice-muted)';
type StudyProgress = PlanProgress & { targetCompletionPercent: number };
type PlanView = 'kanban' | 'mind-map';
type TaskFilterState = { query: string; skillId: string; improvementOnly: boolean; checklistOpenOnly: boolean };

const noTaskSkill = '__unassigned__';

function normalizeTaskSearch(value: string) {
  return value.trim().toLocaleLowerCase('vi').normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/g, 'd');
}

const planViews = [
  { value: 'kanban', label: 'Kanban', Icon: LayoutGrid },
  { value: 'mind-map', label: 'Mind Map', Icon: Network },
] as const;

function PanelHeading({ icon: Icon, title, subtitle }: { icon: LucideIcon; title: string; subtitle: string }) {
  return (
    <div className="flex min-w-0 shrink-0 items-start gap-2.5">
      <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-(--practice-orange) text-(--practice-primary)">
        <Icon size={18} aria-hidden="true" />
      </span>
      <div>
        <h2 className="font-bold leading-snug">{title}</h2>
        <p className="mt-0.5 text-xs leading-5 text-(--practice-muted)">{subtitle}</p>
      </div>
    </div>
  );
}

type ProgressLevel = 'red' | 'yellow' | 'green';

function getProgressLevel(percent: number | null): ProgressLevel {
  const value = percent ?? 0;
  if (value <= 30) return 'red';
  if (value <= 70) return 'yellow';
  return 'green';
}

function ProgressTrack({ percent, className }: { percent: number | null; className?: string }) {
  const value = percent ?? 0;
  const clamped = Math.min(100, Math.max(0, value));
  const level = getProgressLevel(percent);

  const fillClassByLevel: Record<ProgressLevel, string> = {
    red: styles.progressGradientFillRed,
    yellow: styles.progressGradientFillYellow,
    green: styles.progressGradientFillGreen,
  };

  return (
    <div
      role={percent === null ? undefined : 'progressbar'}
      aria-hidden={percent === null || undefined}
      aria-label={percent === null ? undefined : 'Tiến độ ôn tập hiện tại'}
      aria-valuenow={percent ?? undefined}
      className={cn(styles.progressGradientTrack, 'relative h-2.5 w-full overflow-hidden rounded-full p-[1px]', className)}
    >
      {percent !== null && (
        <div
          className={cn(styles.progressGradientFill, fillClassByLevel[level])}
          style={{ width: `${clamped}%` }}
        />
      )}
    </div>
  );
}

function ProgressSummary({ progress }: { progress: StudyProgress }) {
  const { done, total, percent } = progress;
  const level = getProgressLevel(percent);
  const displayPercent = percent === null ? '0%' : formatPercent(percent);

  const textColorByLevel: Record<ProgressLevel, string> = {
    red: 'text-red-600',
    yellow: 'text-amber-500',
    green: 'text-emerald-600',
  };

  return (
    <div className="flex shrink-0 flex-col justify-center gap-1.5 rounded-2xl border border-slate-200/80 bg-slate-50/70 px-3.5 py-2 shadow-2xs w-[min(48vw,16.5rem)] sm:w-[17rem]">
      {/* Tầng 1: Phần trăm và số lượng nằm cùng một hàng */}
      <div className="flex items-baseline justify-between gap-2">
        <span className={cn('text-base sm:text-lg font-black leading-none tabular-nums tracking-tight', textColorByLevel[level])}>
          {displayPercent}
        </span>
        <span className="text-[11px] font-medium text-slate-500 tabular-nums">
          {done}/{total} đầu việc hoàn thành
        </span>
      </div>

      {/* Tầng 2: Thanh tiến trình nằm phía dưới, chiếm toàn bộ chiều rộng */}
      <ProgressTrack percent={percent} className="h-2 w-full" />
    </div>
  );
}

function GapList({ title, skills, actions }: { title: string; skills: StudySkill[]; actions?: StudyGapActions }) {
  if (!skills.length) return null;
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold">{title}</h3>
      {skills.map((skill) => {
        const evidence = skill.objectives.flatMap((objective) => objective.criteria.flatMap((criterion) => criterion.evidence))
          .filter((item) => item.performance === 'BELOW')
          .sort((a, b) => b.source.attemptNumber - a.source.attemptNumber)[0];
        const source = evidence?.source ?? skill.lastChecked;
        const note = evidence?.rationale || skill.objectives[0]?.explanation;
        return <StudyGapCard key={skill.skillId} gap={{ skillId: skill.skillId, notes: note ? [note] : [], source }} actions={actions} />;
      })}
    </div>
  );
}

function InterviewWeaknesses({ findings, actions }: { findings: ReportWeakness[]; actions?: StudyGapActions }) {
  if (!findings.length) return <p className={mutedText}>Báo cáo phỏng vấn chưa ghi nhận điểm yếu.</p>;
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold">Điểm yếu sau phỏng vấn</h3>
      {findings.map(({ skillId, sessionId, attemptNumber, weaknesses }) => (
        <StudyGapCard key={skillId} gap={{ skillId, notes: weaknesses, source: { sessionId, attemptNumber } }} actions={actions} list />
      ))}
    </div>
  );
}

function ObjectiveGaps({ suggestions, actions }: { suggestions: ObjectiveSuggestion[]; actions?: StudyGapActions }) {
  const visible = suggestions.filter(objective => objective.criteria.some(criterion => criterion.selectedByDefault));
  if (!visible.length) return <p className={mutedText}>Không có lỗ hổng kiến thức nào cần luyện tập.</p>;
  return <div className="space-y-3">
    <p className="text-xs leading-5 text-(--practice-muted)">Chọn mục tiêu để xem và chỉnh checklist. Tiêu chí chưa đánh giá không được xem là điểm yếu.</p>
    {visible.map(objective => <StudyGapCard key={objective.objectiveId}
      gap={{ skillId: objective.skillId, notes: [], source: objective.source, objective }} actions={actions} />)}
  </div>;
}

function KnowledgeGaps({ profile, request, compact = false, actions }: {
  profile: ApplicationProfile;
  request: ReturnType<typeof usePracticeKnowledgeGaps>;
  compact?: boolean;
  actions?: StudyGapActions;
}) {
  const hasResult = profile.attempts.some((attempt) => finishedAttempt(attempt) && attempt.answeredCount > 0);
  const attempt = activeAttempt(profile.attempts);
  const applicationUrl = `/applications/${profile.id}`;
  const href = hasResult ? `${applicationUrl}#competency` : attempt ? `/interview/session/${attempt.id}` : applicationUrl;
  const action = hasResult ? 'Xem kết quả đánh giá'
    : attempt?.status === 'In progress' ? 'Tiếp tục phỏng vấn'
    : attempt ? 'Phỏng vấn thử ngay' : 'Mở hồ sơ để phỏng vấn';
  const { state, retry } = request;
  const data = state.status === 'ready' ? state.data : null;

  return (
    <section className={workspacePanelStyle}>
      <PanelHeading icon={Radar} title="Lỗ hổng kiến thức" subtitle="Kỹ năng cần cải thiện" />
      <div className={cn(workspaceScrollStyle, 'flex flex-col')}>
        {state.status === 'loading' ? <p role="status" className={mutedText}>Đang tải kết quả kiểm chứng…</p> :
          state.status === 'error' ? (
            <div role="alert" className="space-y-2">
              <p className={mutedText}>Không tải được kết quả kiểm chứng.</p>
              <Button type="button" variant="outline" size="sm" onClick={retry}>Thử lại</Button>
            </div>
          ) : data && (data.completedAttempts > 0 || (data.reportWeaknesses?.length ?? 0) > 0) ? (
            <div className="space-y-3">
              {actions && <p className="text-xs text-(--practice-muted)">Bấm thêm hoặc kéo thẻ vào cột để chuẩn bị đầu việc.</p>}
              {data.objectiveSuggestions ? <ObjectiveGaps suggestions={data.objectiveSuggestions} actions={actions} /> : <>
              <InterviewWeaknesses findings={data.reportWeaknesses ?? []} actions={actions} />
              <GapList title="Cần ôn tập" skills={data.weak} actions={actions} />
              <GapList title="Cần kiểm chứng thêm" skills={data.needsVerification} actions={actions} />
              </>}
              {data.notAssessedSkillIds.length > 0 && <p className={mutedText}>{data.notAssessedSkillIds.length} kỹ năng chưa đánh giá.</p>}
            </div>
          ) : (
        <div className={cn('my-auto flex flex-col items-center gap-3 py-7 text-center',
          compact && 'items-start py-0 text-left sm:flex-row sm:items-center sm:justify-between')}>
          {!compact && (
            <span className="grid size-12 place-items-center rounded-xl bg-(--practice-pale) text-(--practice-primary)">
              <Radar size={24} aria-hidden="true" />
            </span>
          )}
          <div className="space-y-2">
            <h3 className="text-sm font-semibold">Chưa có kết quả kiểm chứng</h3>
            <p className={mutedText}>
              {hasResult
                ? 'Bạn có thể xem các kỹ năng cần cải thiện trong phần đánh giá của hồ sơ ứng tuyển.'
                : 'Hoàn thành một lượt phỏng vấn AI để nhận đánh giá theo kỹ năng.'}
            </p>
          </div>
          <Link href={href} className={cn(buttonVariants({ variant: 'secondary' }), 'h-auto min-h-9 flex-wrap whitespace-normal rounded-full bg-(--practice-pale) px-3 py-1.5 text-xs hover:bg-(--practice-blue)')}>
            {action} <ArrowRight size={14} aria-hidden="true" />
          </Link>
        </div>
        )}
      </div>
    </section>
  );
}

interface TaskBoardProps {
  tasks: readonly StudyTask[];
  skillIds: readonly string[];
  selectedTaskId: number | null;
  onSelect: (id: number) => void;
  onCreate: (task: NewStudyTask) => Promise<boolean>;
  onMove: (task: StudyTask, status: StudyTaskStatus, beforeTaskId?: number | null) => Promise<boolean>;
  onChangeParent: (task: StudyTask, parentTaskId: number | null, status?: StudyTaskStatus) => Promise<boolean>;
  onToggleChecklist: (taskId: number, item: StudyChecklistItem) => Promise<boolean>;
  completedTaskId: number | null;
  disabled: boolean;
  hasActiveFilters: boolean;
  gapSource: StudyGapActions['source'];
  onGapDrop: (gap: StudyGap, status: StudyTaskStatus) => Promise<boolean>;
}

function TaskBoard({ tasks, skillIds, selectedTaskId, onSelect, onCreate, onMove, onChangeParent, onToggleChecklist, disabled, hasActiveFilters, completedTaskId, gapSource, onGapDrop }: TaskBoardProps) {
  return (
    <section className={workspacePanelStyle}>
      <div className="flex shrink-0 flex-wrap items-start justify-between gap-3">
        <PanelHeading icon={ClipboardList} title="Đầu việc ôn tập" subtitle="Kéo thẻ vào thẻ khác để lồng; kéo ra tiêu đề cột để tách." />
        <StudyTaskCreateDialog skillIds={skillIds} onCreate={onCreate} disabled={disabled} />
      </div>
      <StudyKanban tasks={tasks} selectedTaskId={selectedTaskId} onSelect={onSelect} onCreate={onCreate} onMove={onMove} onChangeParent={onChangeParent} onToggleChecklist={onToggleChecklist} disabled={disabled}
        hasActiveFilters={hasActiveFilters} completedTaskId={completedTaskId} gapSource={gapSource} onGapDrop={onGapDrop} />
    </section>
  );
}

export function PracticePlanBoard({ profile, initialPlan }: {
  profile: ApplicationProfile;
  initialPlan: StudyPlanView;
}) {
  const [selectedTaskId, setSelectedTaskId] = useState<number | null>(null);
  const [gapDraft, setGapDraft] = useState<{ objective: ObjectiveSuggestion; status: StudyTaskStatus } | null>(null);
  const gapSource = useRef<StudyGap | null>(null);
  const gapsDetailsRef = useRef<HTMLDetailsElement>(null);
  const [view, setView] = useState<PlanView>('kanban');
  const [completedTaskId, setCompletedTaskId] = useState<number | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [mindMapPositions, setMindMapPositions] = useState<MindMapPositions>({});
  const [taskFilters, setTaskFilters] = useState<TaskFilterState>({ query: '', skillId: '', improvementOnly: false, checklistOpenOnly: false });
  const { data, pending, error, needsRefresh, save, reload } = useStudyPlan(profile.id, initialPlan);
  const gaps = usePracticeKnowledgeGaps(profile.id);
  const { plan } = data;
  const storedTasks = data.tasks;
  const progress = { ...data.progress, targetCompletionPercent: plan.targetCompletionPercent };
  const disabled = pending || needsRefresh;
  const skillIds = [...new Set(profile.skills.map((skill) => skill.jd_skill_id))];
  const isMindMap = view === 'mind-map';
  const knowledgeGapData = gaps.state.status === 'ready' ? gaps.state.data : null;
  const improvementSkillIds = new Set([
    ...(knowledgeGapData?.weak.map(({ skillId }) => skillId) ?? []),
    ...(knowledgeGapData?.needsVerification.map(({ skillId }) => skillId) ?? []),
    ...(knowledgeGapData?.objectiveSuggestions
      ? knowledgeGapData.objectiveSuggestions.filter(objective => objective.criteria.some(c => c.selectedByDefault)).map(objective => objective.skillId)
      : knowledgeGapData?.reportWeaknesses.map(({ skillId }) => skillId) ?? []),
  ]);
  const latestAssessmentAttemptNumber = plan.sourceSessionId
    ? profile.attempts.find((attempt) => attempt.id === plan.sourceSessionId && attempt.status === 'Completed')?.number ?? 0
    : profile.attempts.filter((attempt) => attempt.status === 'Completed').reduce((latest, attempt) => Math.max(latest, attempt.number), 0);
  const notAssessedSkillIds = new Set(knowledgeGapData?.notAssessedSkillIds ?? []);
  const gapCount = knowledgeGapData
    ? (knowledgeGapData.objectiveSuggestions
        ? knowledgeGapData.objectiveSuggestions.filter((objective) => objective.criteria.some((criterion) => criterion.selectedByDefault)).length
        : ((knowledgeGapData.weak?.length ?? 0) + (knowledgeGapData.needsVerification?.length ?? 0) + (knowledgeGapData.reportWeaknesses?.length ?? 0)))
    : 0;
  const tasks = storedTasks.map((task) => ({
    ...task,
    gapNeedsConfirmation: task.gapSourceObjectiveId ? Boolean(
      task.status !== 'DONE' && task.checklist.some(item => item.sourceCriterionId)
      && task.checklist.filter(item => item.sourceCriterionId).every(item => {
        const criterion = knowledgeGapData?.objectiveSuggestions?.find(o => o.objectiveId === task.gapSourceObjectiveId)
          ?.criteria.find(c => c.criterionId === item.sourceCriterionId);
        return criterion && ['DEMONSTRATED_AT_TARGET', 'DEMONSTRATED_ABOVE_TARGET'].includes(criterion.assessment)
          && (criterion.lastAssessment?.attemptNumber ?? 0) > (item.sourceAttemptNumber ?? task.gapSourceAttemptNumber ?? 0);
      })
    ) : Boolean(
      knowledgeGapData?.completedAttempts && task.status !== 'DONE' && task.gapSourceSkillId
      && latestAssessmentAttemptNumber > (task.gapSourceAttemptNumber ?? 0)
      && !improvementSkillIds.has(task.gapSourceSkillId)
      && !notAssessedSkillIds.has(task.gapSourceSkillId)
    ),
  }));
  const selectedTask = tasks.find((task) => task.id === selectedTaskId);
  const inspectorSide = selectedTask?.status === 'DONE' ? 'left' : 'right';
  const query = normalizeTaskSearch(taskFilters.query);
  const skillOptions = [...new Set(tasks.flatMap((task) => task.skillId ? [task.skillId] : []))]
    .sort((a, b) => skillLabel(a).localeCompare(skillLabel(b), 'vi'));
  const selectedSkillIds = taskFilters.skillId && taskFilters.skillId !== noTaskSkill ? new Set([taskFilters.skillId]) : null;
  const taskById = new Map(tasks.map((task) => [task.id, task]));
  function hasSkillInTaskLineage(task: StudyTask, skills: ReadonlySet<string>) {
    let current: StudyTask | undefined = task;
    while (current) {
      if (current.skillId && skills.has(current.skillId)) return true;
      current = current.parentTaskId == null ? undefined : taskById.get(current.parentTaskId);
    }
    return false;
  }
  const matchingTasks = tasks.filter((task) => {
    if (query && !normalizeTaskSearch(task.title).includes(query)) return false;
    if (taskFilters.skillId === noTaskSkill && task.skillId) return false;
    if (selectedSkillIds && !hasSkillInTaskLineage(task, selectedSkillIds)) return false;
    if (taskFilters.improvementOnly && !hasSkillInTaskLineage(task, improvementSkillIds)) return false;
    if (taskFilters.checklistOpenOnly && !task.checklist.some((item) => !item.isCompleted)) return false;
    return true;
  });
  const matchingTaskIds = new Set(matchingTasks.map(({ id }) => id));
  const visibleTaskIds = new Set(matchingTaskIds);
  for (const task of matchingTasks) {
    let parentId = task.parentTaskId;
    while (parentId != null && !visibleTaskIds.has(parentId)) {
      visibleTaskIds.add(parentId);
      parentId = taskById.get(parentId)?.parentTaskId;
    }
  }
  const visibleTasks = tasks.filter((task) => visibleTaskIds.has(task.id));
  const hasActiveTaskFilters = Boolean(query || taskFilters.skillId || taskFilters.improvementOnly || taskFilters.checklistOpenOnly);

  const gapRetry = useRef(gaps.retry);
  gapRetry.current = gaps.retry;
  useEffect(() => {
    let lastRefresh = 0;
    const refreshGaps = () => {
      if (document.visibilityState !== 'visible' || Date.now() - lastRefresh < 1500) return;
      lastRefresh = Date.now();
      gapRetry.current();
    };
    window.addEventListener('focus', refreshGaps);
    document.addEventListener('visibilitychange', refreshGaps);
    return () => {
      window.removeEventListener('focus', refreshGaps);
      document.removeEventListener('visibilitychange', refreshGaps);
    };
  }, []);

  useEffect(() => {
    if (completedTaskId === null) return;
    const timer = window.setTimeout(() => setCompletedTaskId(null), 650);
    return () => window.clearTimeout(timer);
  }, [completedTaskId]);

  useEffect(() => {
    function handlePointerDown(event: PointerEvent) {
      const target = event.target;
      if (!(target instanceof Element)) return;

      const details = gapsDetailsRef.current;
      if (details?.open && !details.contains(target)) {
        details.open = false;
      }

      if (
        selectedTaskId !== null &&
        !target.closest('[data-task-inspector], [data-kanban-task-id], [data-task-id], [role="dialog"], [data-slot="dialog-overlay"], [data-slot="dialog-content"], [data-slot="dialog-portal"]')
      ) {
        setSelectedTaskId(null);
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key !== 'Escape') return;
      if (gapsDetailsRef.current?.open) {
        gapsDetailsRef.current.open = false;
      }
      if (selectedTaskId !== null && !document.querySelector('[role="dialog"]')) {
        setSelectedTaskId(null);
      }
    }

    document.addEventListener('pointerdown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [selectedTaskId]);

  async function createTask(task: NewStudyTask) {
    const result = await save(() => studyPlans.createTask(profile.id, task));
    if (result) setSelectedTaskId(null);
    return Boolean(result);
  }

  function createTaskFromGap(gap: StudyGap, status: StudyTaskStatus) {
    if (gapsDetailsRef.current) gapsDetailsRef.current.open = false;
    if (gap.objective) {
      setGapDraft({ objective: gap.objective, status });
      return Promise.resolve(true);
    }
    const referenceUrl = gap.source
      ? new URL(`/interview/session/${encodeURIComponent(gap.source.sessionId)}/result`, window.location.origin).href
      : undefined;
    return createTask({
      title: `Ôn tập ${skillLabel(gap.skillId)}`.slice(0, 255),
      skillId: skillIds.includes(gap.skillId) ? gap.skillId : undefined,
      status,
      notes: gap.notes.join('\n\n').slice(0, 10000) || undefined,
      checklist: [],
      referenceUrl: referenceUrl && referenceUrl.length <= 2048 ? referenceUrl : undefined,
      gapOrigin: { skillId: gap.skillId, sessionId: gap.source?.sessionId ?? null, attemptNumber: gap.source?.attemptNumber ?? null },
    });
  }

  async function updateTask(task: StudyTask, update: StudyTaskUpdate) {
    const { title, skillId, notes, status, sortOrder } = task;
    const result = await save(() => studyPlans.updateTask(profile.id, task.id, { title, skillId, notes, status, sortOrder, ...update }));
    if (result && status !== 'DONE' && update.status === 'DONE') setCompletedTaskId(task.id);
    return Boolean(result);
  }

  async function moveTask(task: StudyTask, status: StudyTaskStatus, beforeTaskId?: number | null) {
    if (beforeTaskId === undefined) return updateTask(task, { status });
    const result = await save(() => studyPlans.moveTask(profile.id, task.id, status, beforeTaskId));
    if (result && task.status !== 'DONE' && status === 'DONE') setCompletedTaskId(task.id);
    return Boolean(result);
  }

  async function changeTaskParent(task: StudyTask, parentTaskId: number | null, status?: StudyTaskStatus) {
    const result = await save(() => studyPlans.updateTaskParent(profile.id, task.id, parentTaskId, status));
    if (result && task.status !== 'DONE' && status === 'DONE') setCompletedTaskId(task.id);
    return Boolean(result);
  }

  async function toggleChecklistItem(taskId: number, item: StudyChecklistItem) {
    return Boolean(await save(() => studyPlans.updateChecklist(profile.id, taskId, { ...item, isCompleted: !item.isCompleted })));
  }

  async function deleteTask(task: StudyTask) {
    const result = await save(() => studyPlans.deleteTask(profile.id, task.id));
    if (result) {
      setSelectedTaskId((id) => id === task.id ? null : id);
    }
    return Boolean(result);
  }

  async function updatePlan(input: StudyPlanDetails) {
    const result = await save(() => studyPlans.updatePlan(profile.id, input));
    if (result && input.sourceSessionId !== plan.sourceSessionId) gaps.retry();
    return Boolean(result);
  }

  const inspector = selectedTask && <PracticeTaskInspector key={selectedTask.id} task={selectedTask}
    disabled={disabled} skillIds={skillIds} onUpdate={(update) => updateTask(selectedTask, update)}
    onDelete={() => deleteTask(selectedTask)}
    checklist={{
      add: async (content, sortOrder) => Boolean(await save(() => studyPlans.addChecklist(profile.id, selectedTask.id, content, sortOrder))),
      update: async (item) => Boolean(await save(() => studyPlans.updateChecklist(profile.id, selectedTask.id, item))),
      remove: (item) => save(() => studyPlans.deleteChecklist(profile.id, selectedTask.id, item.id)),
    }}
    resources={{
      add: async (title, url) => Boolean(await save(() => studyPlans.addResource(profile.id, selectedTask.id, title, url))),
      update: async (resource, title, url) => Boolean(await save(() => studyPlans.updateResource(profile.id, selectedTask.id, resource.id, title, url))),
      upload: async (file) => Boolean(await save(() => studyPlans.uploadResource(profile.id, selectedTask.id, file))),
      download: (resource) => studyPlans.downloadResource(profile.id, selectedTask.id, resource.id),
      remove: (resource) => save(() => studyPlans.deleteResource(profile.id, selectedTask.id, resource.id)),
    }}
    onClose={() => setSelectedTaskId(null)} />;

  return (
    <div className="space-y-3">
      {(error || needsRefresh) && (
        <div role="alert" className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-destructive/20 bg-card p-3 text-sm">
          <span>{error ?? 'Hãy tải lại kế hoạch để đồng bộ dữ liệu.'}</span>
          {needsRefresh && <Button type="button" size="sm" variant="outline" disabled={pending} onClick={() => void reload()}>Tải lại kế hoạch</Button>}
        </div>
      )}
      <header className="sticky top-0 z-30 flex flex-wrap items-center gap-2 rounded-2xl border border-slate-200/80 bg-card/95 p-2 shadow-xs backdrop-blur-md sm:flex-nowrap sm:px-3">
        <div className="mr-auto min-w-0 flex-1 sm:flex-none">
          <h1 className="truncate text-base font-extrabold leading-tight tracking-tight sm:text-lg text-slate-900">{plan.title}</h1>
          <Link href={`/applications/${profile.id}`} className="text-[11px] font-medium text-(--practice-muted) hover:text-(--practice-primary) hover:underline">
            {profile.roleTitle || 'Kế hoạch ôn tập'} · Xem hồ sơ
          </Link>
        </div>
        <ProgressSummary progress={progress} />
        <details ref={gapsDetailsRef} className="relative order-3 sm:order-none group">
          <summary
            aria-label="Lỗ hổng kiến thức"
            title={`Lỗ hổng kiến thức (${gapCount} nội dung)`}
            className="flex flex-col items-center justify-center size-10 cursor-pointer list-none rounded-xl border border-slate-200/80 bg-slate-50/70 hover:bg-slate-100/90 transition-all text-slate-700 hover:border-slate-300 focus-visible:outline-2 focus-visible:outline-(--practice-primary) [&::-webkit-details-marker]:hidden"
          >
            <Radar size={15} className={cn(gapCount > 0 && "text-(--practice-primary)")} aria-hidden="true" />
            <span
              className={cn(
                "text-[10px] font-bold leading-none mt-0.5 tabular-nums",
                gapCount > 0 ? "text-(--practice-primary)" : "text-slate-400"
              )}
            >
              {gaps.state.status === 'loading' ? '·' : gapCount}
            </span>
          </summary>
          <div className="absolute right-0 top-12 z-50 max-h-[65vh] w-[min(90vw,24rem)] overflow-y-auto rounded-2xl border border-slate-200 bg-card p-3 shadow-xl">
            <KnowledgeGaps
              profile={profile}
              request={gaps}
              compact
              actions={{ source: gapSource, disabled, add: (gap) => createTaskFromGap(gap, 'TODO') }}
            />
          </div>
        </details>
        <div
          role="group"
          aria-label="Chế độ xem kế hoạch"
          className="relative order-2 inline-flex items-center rounded-xl bg-slate-100 p-0.5 border border-slate-200/60 shadow-inner sm:order-none"
        >
          <span
            aria-hidden="true"
            className={cn(
              "absolute top-0.5 bottom-0.5 w-[calc(50%-2px)] rounded-lg bg-card shadow-xs transition-all duration-300 ease-[cubic-bezier(0.2,0.8,0.25,1)] pointer-events-none",
              view === 'kanban' ? "left-0.5" : "left-[calc(50%+1px)]"
            )}
          />
          {planViews.map(({ value, label, Icon }) => (
            <button
              key={value}
              type="button"
              aria-label={label}
              title={label}
              aria-pressed={view === value}
              onClick={() => setView(value)}
              className={cn(
                "relative z-10 flex h-8 items-center gap-1.5 rounded-lg px-2.5 sm:px-3 text-xs font-semibold transition-colors duration-200 cursor-pointer",
                view === value
                  ? "text-(--practice-primary)"
                  : "text-slate-500 hover:text-slate-800"
              )}
            >
              <Icon size={15} aria-hidden="true" />
              <span className="hidden sm:inline">{label}</span>
            </button>
          ))}
        </div>
        <Button
          type="button"
          variant="outline"
          size="icon-sm"
          aria-label="Cài đặt kế hoạch"
          title="Cài đặt"
          className="order-1 size-10 rounded-xl border-slate-200/80 bg-slate-50/70 hover:bg-slate-100 text-slate-700 sm:order-none transition-colors"
          disabled={disabled}
          onClick={() => setSettingsOpen(true)}
        >
          <Settings2 size={16} aria-hidden="true" />
        </Button>
      </header>
      <section aria-label="Bộ lọc đầu việc" className="flex flex-wrap items-center gap-2 rounded-2xl border border-slate-200/70 bg-card/90 px-3.5 py-2 shadow-xs backdrop-blur-sm">
        <div className="relative min-w-[11rem] flex-1 sm:max-w-xs">
          <label htmlFor="practice-task-search" className="sr-only">Tìm theo tên đầu việc</label>
          <Search size={14} aria-hidden="true" className="pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2 text-slate-400" />
          <Input
            id="practice-task-search"
            type="search"
            value={taskFilters.query}
            onChange={(event) => setTaskFilters((current) => ({ ...current, query: event.target.value }))}
            placeholder="Tìm theo tên đầu việc…"
            className="h-8.5 rounded-xl border-0 bg-slate-100/70 pl-8 pr-3 text-xs placeholder:text-slate-400 focus-visible:bg-card focus-visible:ring-1 focus-visible:ring-(--practice-primary)"
          />
        </div>
        <div className="relative">
          <label htmlFor="practice-skill-filter" className="sr-only">Lọc theo kỹ năng</label>
          <select
            id="practice-skill-filter"
            value={taskFilters.skillId}
            onChange={(event) => setTaskFilters((current) => ({ ...current, skillId: event.target.value }))}
            className="h-8.5 rounded-xl border-0 bg-slate-100/70 px-2.5 pr-7 text-xs font-medium text-slate-700 outline-none cursor-pointer hover:bg-slate-100 focus-visible:ring-1 focus-visible:ring-(--practice-primary) transition-colors"
          >
            <option value="">Tất cả kỹ năng</option>
            <option value={noTaskSkill}>Chưa gắn kỹ năng</option>
            {skillOptions.map((skillId) => <option key={skillId} value={skillId}>{skillLabel(skillId)}</option>)}
          </select>
        </div>
        <button
          type="button"
          aria-pressed={taskFilters.improvementOnly}
          disabled={gaps.state.status !== 'ready'}
          title={gaps.state.status === 'ready' ? 'Chỉ hiện task thuộc kỹ năng yếu hoặc cần kiểm chứng' : 'Đang tải dữ liệu kỹ năng cần cải thiện'}
          onClick={() => setTaskFilters((current) => ({ ...current, improvementOnly: !current.improvementOnly }))}
          className={cn(
            "flex h-8.5 items-center gap-1.5 rounded-xl px-2.5 text-xs font-medium transition-all duration-150 cursor-pointer disabled:cursor-not-allowed disabled:opacity-50",
            taskFilters.improvementOnly
              ? "bg-(--practice-orange) text-(--practice-primary) ring-1 ring-(--practice-primary)/30 font-semibold"
              : "bg-slate-100/70 text-slate-600 hover:bg-slate-100 hover:text-slate-900"
          )}
        >
          <Radar size={13} aria-hidden="true" />
          <span>Kỹ năng cần cải thiện</span>
        </button>
        <button
          type="button"
          aria-pressed={taskFilters.checklistOpenOnly}
          onClick={() => setTaskFilters((current) => ({ ...current, checklistOpenOnly: !current.checklistOpenOnly }))}
          className={cn(
            "flex h-8.5 items-center gap-1.5 rounded-xl px-2.5 text-xs font-medium transition-all duration-150 cursor-pointer",
            taskFilters.checklistOpenOnly
              ? "bg-blue-100 text-blue-800 ring-1 ring-blue-300 font-semibold"
              : "bg-slate-100/70 text-slate-600 hover:bg-slate-100 hover:text-slate-900"
          )}
        >
          <ListChecks size={13} aria-hidden="true" />
          <span>Checklist còn việc</span>
        </button>
        <div className="ml-auto flex items-center gap-2">
          <span role="status" className="text-xs font-medium tabular-nums text-slate-400">
            Hiện {matchingTasks.length}/{tasks.length}
          </span>
          {hasActiveTaskFilters && (
            <button
              type="button"
              onClick={() => setTaskFilters({ query: '', skillId: '', improvementOnly: false, checklistOpenOnly: false })}
              className="flex h-7 items-center gap-1 rounded-lg px-2 text-xs font-medium text-slate-500 hover:bg-slate-100 hover:text-slate-900 transition-colors cursor-pointer"
            >
              <X size={13} aria-hidden="true" />
              <span>Xóa lọc</span>
            </button>
          )}
        </div>
      </section>
      {isMindMap ? (
        <>
          <section aria-label="Mind Map" data-inspector-side={selectedTask ? inspectorSide : undefined}
            data-selection-active={selectedTask ? true : undefined}
            className={cn(styles.mindMapWorkspace, selectedTask && styles.hasInspector, selectedTask && inspectorSide === 'left' && styles.inspectorOnLeft)}>
            <PracticeMindMap title={plan.title} subtitle={profile.roleTitle} tasks={tasks}
              skillIds={skillIds} onCreate={createTask}
              positions={mindMapPositions} onPosition={(id, point) => setMindMapPositions((current) => ({ ...current, [id]: point }))}
              onResetPositions={() => setMindMapPositions({})}
              gaps={gaps.state.status === 'ready' ? gaps.state.data : undefined}
              selectedTaskId={selectedTaskId} onSelect={setSelectedTaskId} disabled={disabled}
              filterTaskIds={visibleTaskIds} matchingTaskIds={matchingTaskIds} hasTaskFilters={hasActiveTaskFilters}
              onMove={moveTask} onChangeParent={(task, parentTaskId) => changeTaskParent(task, parentTaskId)} completedTaskId={completedTaskId} />
            {inspector}
          </section>
        </>
      ) : (
        <div data-inspector-side={selectedTask ? inspectorSide : undefined} data-selection-active={selectedTask ? true : undefined}
          data-selected-task-id={selectedTaskId ?? undefined}
          className={cn(styles.kanbanWithInspector, selectedTask && styles.hasKanbanInspector)}>
          {selectedTask && inspectorSide === 'left' && inspector}
          <TaskBoard tasks={visibleTasks} skillIds={skillIds} selectedTaskId={selectedTaskId} onCreate={createTask} onSelect={setSelectedTaskId}
            onMove={moveTask} onChangeParent={changeTaskParent} onToggleChecklist={toggleChecklistItem} completedTaskId={completedTaskId} disabled={disabled} hasActiveFilters={hasActiveTaskFilters} gapSource={gapSource} onGapDrop={createTaskFromGap} />
          {selectedTask && inspectorSide === 'right' && inspector}
        </div>
      )}
      {gapDraft && <StudyGapTaskDialog key={gapDraft.objective.objectiveId} objective={gapDraft.objective}
        status={gapDraft.status} disabled={disabled} onCreate={createTask} onClose={() => setGapDraft(null)} />}
      <Dialog open={settingsOpen} onOpenChange={setSettingsOpen}>
          <StudyPlanSettings plan={plan} attempts={profile.attempts} disabled={disabled} onSave={updatePlan} onClose={() => setSettingsOpen(false)} />
      </Dialog>
    </div>
  );
}
