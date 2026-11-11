'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import {
  ArrowRight, CalendarDays, ClipboardList, FileText, Flag,
  LayoutGrid, Link2, ListChecks, Network, Radar, StickyNote, type LucideIcon,
} from 'lucide-react';
import { activeAttempt, finishedAttempt, skillLabel } from '@/components/features/applications/applicationUi';
import { Button, buttonVariants } from '@/components/ui/button';
import { usePracticeKnowledgeGaps } from '@/hooks/usePracticeProfiles';
import { useStudyPlan } from '@/hooks/useStudyPlan';
import { cn } from '@/lib/utils';
import type { ApplicationProfile } from '@/services/applicationProfiles';
import { studyPlans, type ReportWeakness, type StudyPlanDetails, type StudyPlanView, type StudySkill } from '@/services/studyPlans';
import {
  formatStudyPercent as formatPercent, studyTaskStatuses, studyTaskTones,
  type NewStudyTask, type StudyProgress as PlanProgress, type StudyTask, type StudyTaskStatus, type StudyTaskUpdate,
} from './studyPlan';
import { StudyTaskCreateDialog } from './StudyTaskCreateDialog';
import { PracticeMindMap } from './PracticeMindMap';
import type { MindMapPositions } from './useMindMapPosition';
import { PracticeTaskInspector } from './PracticeTaskInspector';
import { StudyPlanSettings } from './StudyPlanSettings';
import { StudyKanban } from './StudyKanban';
import styles from './practice.module.css';

const panelStyle = 'flex min-w-0 flex-col rounded-2xl border border-slate-100 bg-card p-4 shadow-xs sm:p-5';
const workspacePanelStyle = cn(panelStyle, 'min-h-0 gap-4');
const workspaceScrollStyle = 'min-h-0 flex-1 xl:overflow-y-auto';
const mutedText = 'text-sm leading-6 text-(--practice-muted)';
type StudyProgress = PlanProgress & { targetCompletionPercent: number };
type PlanView = 'kanban' | 'mind-map';

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

function ProgressTrack({ percent, className }: { percent: number | null; className: string }) {
  return (
    <div
      role={percent === null ? undefined : 'progressbar'}
      aria-hidden={percent === null || undefined}
      aria-label={percent === null ? undefined : 'Tiến độ ôn tập hiện tại'}
      aria-valuenow={percent ?? undefined}
      className={cn('overflow-hidden rounded-full bg-(--practice-blue-strong)', className)}
    >
      {percent !== null && <div className="h-full bg-(--practice-primary)" style={{ width: `${percent}%` }} />}
    </div>
  );
}

function ProgressSummary({ progress }: { progress: StudyProgress }) {
  const { targetCompletionPercent, done, total, percent, meetsTarget } = progress;

  return (
    <div className="w-full shrink-0 space-y-2.5 rounded-xl bg-(--practice-pale) p-4 lg:max-w-72">
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <span className="font-semibold">Tiến độ ôn tập</span>
        <span className={cn('rounded-full px-2.5 py-1 text-xs',
          meetsTarget ? 'bg-(--practice-green-bg) text-(--practice-green)' : 'bg-(--practice-blue) text-(--practice-muted)')}>
          {percent === null ? 'Chưa theo dõi' : meetsTarget ? 'Đạt mục tiêu' : 'Chưa đạt mục tiêu'}
        </span>
      </div>
      {percent !== null && (
        <>
          <strong className="block text-2xl tabular-nums text-(--practice-primary)">{formatPercent(percent)}</strong>
          <ProgressTrack percent={percent} className="h-2" />
        </>
      )}
      <div className="flex flex-wrap justify-between gap-1 text-xs text-(--practice-muted)">
        <span>{percent === null ? 'Chưa có đầu việc' : `Đã hoàn thành ${done}/${total} đầu việc`}</span>
        <span>Mục tiêu: {formatPercent(targetCompletionPercent)}</span>
      </div>
    </div>
  );
}

function BoardOverview({ profile, plan, progress, isMindMap }: {
  profile: ApplicationProfile;
  plan: StudyPlanDetails;
  progress: StudyProgress;
  isMindMap: boolean;
}) {
  return (
    <section className={cn(panelStyle, 'gap-5 lg:flex-row lg:items-center lg:justify-between lg:p-6')}>
      <div className="flex min-w-0 items-start gap-3">
        {!isMindMap && <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-(--practice-orange) text-(--practice-primary)">
          <CalendarDays size={22} aria-hidden="true" />
        </span>}
        <div className="min-w-0 space-y-1">
          <div className={cn(isMindMap && 'flex flex-wrap items-center gap-x-2 gap-y-1')}>
            <h1 className={cn('text-2xl font-extrabold tracking-tight', !isMindMap && 'sm:text-3xl')}>Kế hoạch tự ôn tập</h1>
            <p className={cn('break-words text-sm font-semibold', isMindMap && 'rounded-full bg-(--practice-orange)/60 px-2.5 py-0.5 text-xs text-(--practice-primary)')}>
              {plan.title}{profile.company ? ` · ${profile.company}` : ''}
            </p>
          </div>
          <p className={mutedText}>{isMindMap
            ? 'Theo dõi các kỹ năng cần cải thiện và chọn đầu việc trên sơ đồ để xem chi tiết.'
            : 'Theo dõi các kỹ năng cần cải thiện trước lượt phỏng vấn tiếp theo.'}</p>
          <Link href={`/applications/${profile.id}`} className="inline-flex items-center gap-1.5 text-sm font-medium text-(--practice-primary) hover:underline">
            Xem hồ sơ ứng tuyển <ArrowRight size={14} aria-hidden="true" />
          </Link>
        </div>
      </div>
      {isMindMap ? (
        <div className="grid w-full shrink-0 grid-cols-2 gap-3 rounded-xl bg-(--practice-pale) p-4 text-xs lg:max-w-80">
          <div className="space-y-1.5">
            <p>Tiến độ hiện tại</p>
            <strong className="block text-base text-(--practice-primary)">{progress.percent === null ? 'Chưa theo dõi' : formatPercent(progress.percent)}</strong>
            <ProgressTrack percent={progress.percent} className="h-1.5" />
            <p className="text-(--practice-muted)">{progress.total ? `${progress.done}/${progress.total} hoàn thành` : 'Chưa có đầu việc'}</p>
          </div>
          <div className="space-y-1.5 border-l border-(--practice-blue-strong) pl-3">
            <p>Mục tiêu gợi ý</p>
            <strong className="block text-base text-(--practice-green)">{formatPercent(progress.targetCompletionPercent)}</strong>
            <div className="h-1.5 overflow-hidden rounded-full bg-(--practice-blue-strong)" aria-hidden="true">
              <div className="h-full bg-(--practice-green)" style={{ width: `${progress.targetCompletionPercent}%` }} />
            </div>
          </div>
        </div>
      ) : <ProgressSummary progress={progress} />}
    </section>
  );
}

function GapList({ title, skills }: { title: string; skills: StudySkill[] }) {
  if (!skills.length) return null;
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold">{title}</h3>
      {skills.map((skill) => {
        const evidence = skill.objectives.flatMap((objective) => objective.criteria.flatMap((criterion) => criterion.evidence))
          .filter((item) => item.performance === 'BELOW')
          .sort((a, b) => b.source.attemptNumber - a.source.attemptNumber)[0];
        const source = evidence?.source ?? skill.lastChecked;
        return (
          <div key={skill.skillId} className="space-y-1 rounded-lg bg-(--practice-pale) p-2.5 text-xs [overflow-wrap:anywhere]">
            <p className="font-semibold">{skillLabel(skill.skillId)}</p>
            <p className="text-(--practice-muted)">{evidence?.rationale || skill.objectives[0]?.explanation}</p>
            {source && <Link className="font-medium text-(--practice-primary) hover:underline"
              href={`/interview/session/${encodeURIComponent(source.sessionId)}/result`}>
              Xem kết quả lượt {source.attemptNumber}
            </Link>}
          </div>
        );
      })}
    </div>
  );
}

function InterviewWeaknesses({ findings }: { findings: ReportWeakness[] }) {
  if (!findings.length) return <p className={mutedText}>Báo cáo phỏng vấn chưa ghi nhận điểm yếu.</p>;
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold">Điểm yếu sau phỏng vấn</h3>
      {findings.map(({ skillId, sessionId, attemptNumber, weaknesses }) => (
        <div key={skillId} className="space-y-1.5 rounded-lg bg-(--practice-pale) p-2.5 text-xs wrap-anywhere">
          <p className="font-semibold">{skillLabel(skillId)}</p>
          <ul className="list-disc space-y-1 pl-4 text-(--practice-muted)">
            {weaknesses.map((weakness) => <li key={weakness}>{weakness}</li>)}
          </ul>
          <Link className="font-medium text-(--practice-primary) hover:underline"
            href={`/interview/session/${encodeURIComponent(sessionId)}/result`}>
            Xem kết quả lượt {attemptNumber}
          </Link>
        </div>
      ))}
    </div>
  );
}

function KnowledgeGaps({ profile, request, compact = false }: {
  profile: ApplicationProfile;
  request: ReturnType<typeof usePracticeKnowledgeGaps>;
  compact?: boolean;
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
              <InterviewWeaknesses findings={data.reportWeaknesses ?? []} />
              <GapList title="Cần kiểm chứng thêm" skills={data.needsVerification} />
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
  completedTaskId: number | null;
  disabled: boolean;
}

function TaskBoard({ tasks, skillIds, selectedTaskId, onSelect, onCreate, onMove, disabled, completedTaskId }: TaskBoardProps) {
  return (
    <section className={workspacePanelStyle}>
      <div className="flex shrink-0 flex-wrap items-start justify-between gap-3">
        <PanelHeading icon={ClipboardList} title="Đầu việc ôn tập" subtitle="Kéo thả để đổi cột hoặc chọn thẻ để cập nhật trạng thái." />
        <StudyTaskCreateDialog skillIds={skillIds} onCreate={onCreate} disabled={disabled} />
      </div>
      <StudyKanban tasks={tasks} selectedTaskId={selectedTaskId} onSelect={onSelect} onMove={onMove} disabled={disabled} completedTaskId={completedTaskId} />
    </section>
  );
}

const notesFeatures = [
  { Icon: StickyNote, label: 'Ghi chú ôn tập' },
  { Icon: ListChecks, label: 'Checklist nhiệm vụ' },
  { Icon: Link2, label: 'Tài liệu tham khảo' },
];

function TaskNotes() {
  return (
    <section className={workspacePanelStyle}>
      <PanelHeading icon={StickyNote} title="Chi tiết / Ghi chú" subtitle="Thông tin của từng đầu việc" />
      <div className={cn(workspaceScrollStyle, 'flex flex-col gap-4')}>
        <div className="my-auto flex flex-col items-center gap-2 py-4 text-center">
          <span className="grid size-12 place-items-center rounded-xl bg-(--practice-pale) text-(--practice-muted)">
            <FileText size={24} aria-hidden="true" />
          </span>
          <h3 className="text-sm font-semibold">Chưa chọn đầu việc</h3>
          <p className={mutedText}>Chi tiết và tài liệu ôn tập sẽ hiển thị khi có đầu việc để chọn.</p>
        </div>
        <ul className="shrink-0 space-y-2 rounded-xl bg-(--practice-pale) p-3">
          {notesFeatures.map(({ Icon, label }) => (
            <li key={label} className="flex items-center gap-2 text-xs text-(--practice-muted)">
              <Icon size={15} className="shrink-0 text-(--practice-primary)" aria-hidden="true" /> {label}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

function PracticeGoal({ progress }: { progress: StudyProgress }) {
  const { targetCompletionPercent, percent } = progress;
  const target = formatPercent(targetCompletionPercent);

  return (
    <section className={cn(panelStyle, 'gap-4 sm:flex-row sm:items-center sm:justify-between')}>
      <PanelHeading
        icon={Flag}
        title="Mục tiêu trước buổi phỏng vấn tiếp theo"
        subtitle={`Củng cố các kỹ năng còn yếu và hoàn thành ít nhất ${target} đầu việc trong kế hoạch.`}
      />
      <div className="grid w-full max-w-64 shrink-0 grid-cols-[auto_minmax(0,1fr)] items-center gap-4 rounded-2xl bg-(--practice-pale) px-4 py-3">
        <div className="space-y-1">
          <p className="text-xs font-semibold">Chỉ số cần đạt</p>
          <strong className="block text-[1.75rem] leading-none tabular-nums text-(--practice-primary)">{target}</strong>
        </div>
        <div className="space-y-1.5">
          <p className="text-xs leading-5 tabular-nums text-(--practice-muted)">
            Hiện tại: {percent === null ? 'Chưa theo dõi' : formatPercent(percent)}
          </p>
          <ProgressTrack percent={percent} className="h-1.5" />
        </div>
      </div>
    </section>
  );
}

export function PracticePlanBoard({ profile, initialPlan }: {
  profile: ApplicationProfile;
  initialPlan: StudyPlanView;
}) {
  const [selectedTaskId, setSelectedTaskId] = useState<number | null>(null);
  const [view, setView] = useState<PlanView>('kanban');
  const [completedTaskId, setCompletedTaskId] = useState<number | null>(null);
  const [mindMapPositions, setMindMapPositions] = useState<MindMapPositions>({});
  const { data, pending, error, needsRefresh, save, reload } = useStudyPlan(profile.id, initialPlan);
  const gaps = usePracticeKnowledgeGaps(profile.id);
  const { plan, tasks } = data;
  const progress = { ...data.progress, targetCompletionPercent: plan.targetCompletionPercent };
  const disabled = pending || needsRefresh;
  const skillIds = [...new Set(profile.skills.map((skill) => skill.jd_skill_id))];
  const isMindMap = view === 'mind-map';
  const selectedTask = tasks.find((task) => task.id === selectedTaskId);

  useEffect(() => {
    if (completedTaskId === null) return;
    const timer = window.setTimeout(() => setCompletedTaskId(null), 650);
    return () => window.clearTimeout(timer);
  }, [completedTaskId]);

  async function createTask(task: NewStudyTask) {
    const result = await save(() => studyPlans.createTask(profile.id, task));
    if (result) setSelectedTaskId(result.value.id);
    return Boolean(result);
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

  async function deleteTask(task: StudyTask) {
    if (!window.confirm(`Xóa đầu việc “${task.title}” cùng checklist và tài liệu?`)) return;
    if (await save(() => studyPlans.deleteTask(profile.id, task.id))) {
      setSelectedTaskId((id) => id === task.id ? null : id);
    }
  }

  async function updatePlan(input: StudyPlanDetails) {
    const result = await save(() => studyPlans.updatePlan(profile.id, input));
    if (result && input.sourceSessionId !== plan.sourceSessionId) gaps.retry();
    return Boolean(result);
  }

  const inspector = selectedTask && <PracticeTaskInspector key={selectedTask.id} task={selectedTask}
    className={isMindMap ? undefined : 'overflow-hidden rounded-2xl border border-slate-100 shadow-xs'}
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
    onClose={isMindMap ? () => setSelectedTaskId(null) : undefined} />;

  return (
    <div className="space-y-5">
      <BoardOverview profile={profile} plan={plan} progress={progress} isMindMap={isMindMap} />
      {(error || needsRefresh) && (
        <div role="alert" className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-destructive/20 bg-card p-3 text-sm">
          <span>{error ?? 'Hãy tải lại kế hoạch để đồng bộ dữ liệu.'}</span>
          {needsRefresh && <Button type="button" size="sm" variant="outline" disabled={pending} onClick={() => void reload()}>Tải lại kế hoạch</Button>}
        </div>
      )}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div role="group" aria-label="Chế độ xem kế hoạch" className="flex w-fit items-center gap-1 rounded-full bg-(--practice-blue) p-1">
          {planViews.map(({ value, label, Icon }) => (
            <Button key={value} type="button" variant="ghost" aria-pressed={view === value} onClick={() => setView(value)}
              className="rounded-full px-3 aria-pressed:bg-card aria-pressed:text-(--practice-primary) aria-pressed:shadow-xs">
              <Icon size={15} aria-hidden="true" /> {label}
            </Button>
          ))}
        </div>
        {isMindMap && (
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <ul aria-label="Chú thích trạng thái" className="flex flex-wrap items-center gap-3 text-xs text-(--practice-muted)">
              {studyTaskStatuses.map(({ value, label }) => (
                <li key={value} className="flex items-center gap-1.5">
                  <span className="size-2 rounded-full" style={{ backgroundColor: studyTaskTones[value].color }} aria-hidden="true" />
                  {label}
                </li>
              ))}
            </ul>
            <StudyTaskCreateDialog skillIds={skillIds} onCreate={createTask} disabled={disabled} />
          </div>
        )}
      </div>
      {isMindMap ? (
        <>
          <section aria-label="Mind Map" className={cn(styles.mindMapWorkspace, selectedTask && styles.hasInspector)}>
            <PracticeMindMap title={plan.title} subtitle={profile.roleTitle} tasks={tasks}
              skillIds={skillIds} onCreate={createTask}
              positions={mindMapPositions} onPosition={(id, point) => setMindMapPositions((current) => ({ ...current, [id]: point }))}
              onResetPositions={() => setMindMapPositions({})}
              gaps={gaps.state.status === 'ready' ? gaps.state.data : undefined}
              selectedTaskId={selectedTaskId} onSelect={setSelectedTaskId} disabled={disabled}
              onMove={moveTask} completedTaskId={completedTaskId} />
            {inspector}
          </section>
          <KnowledgeGaps profile={profile} request={gaps} compact />
        </>
      ) : (
        <div className={styles.workspace}>
          <KnowledgeGaps profile={profile} request={gaps} />
          <TaskBoard tasks={tasks} skillIds={skillIds} selectedTaskId={selectedTaskId} onCreate={createTask} onSelect={setSelectedTaskId}
            onMove={moveTask} completedTaskId={completedTaskId} disabled={disabled} />
          {inspector || <TaskNotes />}
        </div>
      )}
      <PracticeGoal progress={progress} />
      <StudyPlanSettings plan={plan} attempts={profile.attempts} disabled={disabled} onSave={updatePlan} />
    </div>
  );
}
