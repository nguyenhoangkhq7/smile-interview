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
  formatStudyPercent as formatPercent, studyProgressTone,
  type NewStudyTask, type StudyProgress as PlanProgress, type StudyTask, type StudyTaskStatus, type StudyTaskUpdate,
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

function ProgressTrack({ percent, target, className }: { percent: number | null; target: number; className: string }) {
  return (
    <div
      role={percent === null ? undefined : 'progressbar'}
      aria-hidden={percent === null || undefined}
      aria-label={percent === null ? undefined : 'Tiến độ ôn tập hiện tại'}
      aria-valuenow={percent ?? undefined}
      className={cn('overflow-hidden rounded-full bg-(--practice-blue-strong)', className)}
    >
      {percent !== null && <div className={cn('h-full rounded-full transition-[width] duration-700 ease-out', studyProgressTone(percent, target).fill)} style={{ width: `${percent}%` }} />}
    </div>
  );
}

function ProgressSummary({ progress }: { progress: StudyProgress }) {
  const { done, total, percent } = progress;

  return (
    <div className="flex w-[min(42vw,13rem)] shrink-0 items-center gap-2 rounded-lg bg-(--practice-pale) px-2.5 py-2">
      <strong className="text-base leading-tight tabular-nums text-(--practice-primary)">{percent === null ? '0%' : formatPercent(percent)}</strong>
      <div className="min-w-0 flex-1 space-y-1">
        <ProgressTrack percent={percent} target={100} className="h-2" />
        <p className="truncate text-[10px] text-(--practice-muted)">{done}/{total} hoàn thành</p>
      </div>
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
  const visible = suggestions.filter(objective => objective.criteria.some(criterion => criterion.kind !== 'MET'));
  if (!visible.length) return <p className={mutedText}>Chưa có nội dung cần ôn từ các mục tiêu đã đánh giá.</p>;
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
  completedTaskId: number | null;
  disabled: boolean;
  hasActiveFilters: boolean;
  gapSource: StudyGapActions['source'];
  onGapDrop: (gap: StudyGap, status: StudyTaskStatus) => Promise<boolean>;
}

function TaskBoard({ tasks, skillIds, selectedTaskId, onSelect, onCreate, onMove, onChangeParent, disabled, hasActiveFilters, completedTaskId, gapSource, onGapDrop }: TaskBoardProps) {
  return (
    <section className={workspacePanelStyle}>
      <div className="flex shrink-0 flex-wrap items-start justify-between gap-3">
        <PanelHeading icon={ClipboardList} title="Đầu việc ôn tập" subtitle="Kéo thẻ vào thẻ khác để lồng; kéo ra tiêu đề cột để tách." />
        <StudyTaskCreateDialog skillIds={skillIds} onCreate={onCreate} disabled={disabled} />
      </div>
      <StudyKanban tasks={tasks} selectedTaskId={selectedTaskId} onSelect={onSelect} onCreate={onCreate} onMove={onMove} onChangeParent={onChangeParent} disabled={disabled}
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

  async function createTask(task: NewStudyTask) {
    const result = await save(() => studyPlans.createTask(profile.id, task));
    if (result) setSelectedTaskId(null);
    return Boolean(result);
  }

  function createTaskFromGap(gap: StudyGap, status: StudyTaskStatus) {
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
      <header className="sticky top-0 z-30 flex flex-wrap items-center gap-1.5 rounded-xl border border-slate-200 bg-card/95 p-2 shadow-xs backdrop-blur sm:flex-nowrap sm:gap-2 sm:px-3">
        <div className="mr-auto min-w-0 flex-1 sm:flex-none">
          <h1 className="truncate text-base font-bold leading-tight sm:text-lg">{plan.title}</h1>
          <Link href={`/applications/${profile.id}`} className="text-[11px] text-(--practice-muted) hover:text-(--practice-primary) hover:underline">
            {profile.roleTitle || 'Kế hoạch ôn tập'} · Xem hồ sơ
          </Link>
        </div>
        <ProgressSummary progress={progress} />
        <details className="relative order-3 sm:order-none">
          <summary aria-label="Lỗ hổng kiến thức" title="Lỗ hổng kiến thức" className="flex size-9 cursor-pointer list-none items-center justify-center rounded-lg border border-slate-200 hover:bg-(--practice-pale)">
            <Radar size={17} aria-hidden="true" />
          </summary>
          <div className="absolute right-0 top-11 z-50 max-h-[65vh] w-[min(90vw,24rem)] overflow-y-auto rounded-xl border border-slate-200 bg-card p-3 shadow-xl">
            <KnowledgeGaps profile={profile} request={gaps} compact
              actions={{ source: gapSource, disabled, add: (gap) => createTaskFromGap(gap, 'TODO') }} />
          </div>
        </details>
        <div role="group" aria-label="Chế độ xem kế hoạch" className="order-2 flex w-fit items-center gap-0.5 rounded-lg bg-(--practice-blue) p-0.5 sm:order-none">
          {planViews.map(({ value, label, Icon }) => (
            <Button key={value} type="button" variant="ghost" size="icon-sm" aria-label={label} title={label} aria-pressed={view === value} onClick={() => setView(value)}
              className="size-8 rounded-md aria-pressed:bg-card aria-pressed:text-(--practice-primary) aria-pressed:shadow-xs">
              <Icon size={16} aria-hidden="true" />
            </Button>
          ))}
        </div>
        <Button type="button" variant="outline" size="icon-sm" aria-label="Cài đặt kế hoạch" title="Cài đặt" className="order-1 size-9 rounded-lg sm:order-none" disabled={disabled} onClick={() => setSettingsOpen(true)}>
          <Settings2 size={17} aria-hidden="true" />
        </Button>
      </header>
      <section aria-label="Bộ lọc đầu việc" className="flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-card px-3 py-2 shadow-xs">
        <label className="relative min-w-[12rem] flex-1 sm:max-w-xs">
          <span className="sr-only">Tìm theo tên đầu việc</span>
          <Search size={15} aria-hidden="true" className="pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2 text-(--practice-muted)" />
          <Input type="search" value={taskFilters.query} onChange={(event) => setTaskFilters((current) => ({ ...current, query: event.target.value }))}
            placeholder="Tìm task theo tên…" className="h-9 rounded-lg bg-(--practice-pale) pl-8 text-sm" />
        </label>
        <label>
          <span className="sr-only">Lọc theo kỹ năng</span>
          <select value={taskFilters.skillId} onChange={(event) => setTaskFilters((current) => ({ ...current, skillId: event.target.value }))}
            className="h-9 min-w-36 rounded-lg border border-slate-200 bg-card px-2.5 text-sm outline-none focus-visible:ring-2 focus-visible:ring-(--practice-primary)">
            <option value="">Tất cả kỹ năng</option>
            <option value={noTaskSkill}>Chưa gắn kỹ năng</option>
            {skillOptions.map((skillId) => <option key={skillId} value={skillId}>{skillLabel(skillId)}</option>)}
          </select>
        </label>
        <Button type="button" variant={taskFilters.improvementOnly ? 'secondary' : 'outline'} size="sm" aria-pressed={taskFilters.improvementOnly}
          disabled={gaps.state.status !== 'ready'} title={gaps.state.status === 'ready' ? 'Chỉ hiện task thuộc kỹ năng yếu hoặc cần kiểm chứng' : 'Đang tải dữ liệu kỹ năng cần cải thiện'}
          onClick={() => setTaskFilters((current) => ({ ...current, improvementOnly: !current.improvementOnly }))}
          className="h-9 rounded-lg aria-pressed:border-(--practice-primary) aria-pressed:bg-(--practice-orange) aria-pressed:text-(--practice-primary)">
          <Radar size={15} aria-hidden="true" /> Kỹ năng cần cải thiện
        </Button>
        <Button type="button" variant={taskFilters.checklistOpenOnly ? 'secondary' : 'outline'} size="sm" aria-pressed={taskFilters.checklistOpenOnly}
          onClick={() => setTaskFilters((current) => ({ ...current, checklistOpenOnly: !current.checklistOpenOnly }))}
          className="h-9 rounded-lg aria-pressed:border-(--practice-primary) aria-pressed:bg-(--practice-orange) aria-pressed:text-(--practice-primary)">
          <ListChecks size={15} aria-hidden="true" /> Checklist còn việc
        </Button>
        <span role="status" className="ml-auto text-xs tabular-nums text-(--practice-muted)">Hiện {matchingTasks.length}/{tasks.length}</span>
        {hasActiveTaskFilters && <Button type="button" variant="ghost" size="sm" onClick={() => setTaskFilters({ query: '', skillId: '', improvementOnly: false, checklistOpenOnly: false })}
          className="h-8 rounded-lg px-2 text-(--practice-muted)"><X size={14} aria-hidden="true" /> Xóa lọc</Button>}
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
            onMove={moveTask} onChangeParent={changeTaskParent} completedTaskId={completedTaskId} disabled={disabled} hasActiveFilters={hasActiveTaskFilters} gapSource={gapSource} onGapDrop={createTaskFromGap} />
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
