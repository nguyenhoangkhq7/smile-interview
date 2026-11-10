'use client';

import { useRef, useState } from 'react';
import Link from 'next/link';
import {
  ArrowRight, CalendarDays, CircleCheck, ClipboardList, Clock, FileText, Flag, FolderOpen,
  LayoutGrid, Link2, ListChecks, Network, Radar, StickyNote, Trash2, type LucideIcon,
} from 'lucide-react';
import { activeAttempt, finishedAttempt } from '@/components/features/applications/applicationUi';
import { Button, buttonVariants } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { ApplicationProfile } from '@/services/applicationProfiles';
import {
  DEFAULT_TARGET_COMPLETION_PERCENT, formatStudyPercent as formatPercent, getStudyProgress, studyTaskStatuses, studyTaskTones,
  type NewStudyTask, type StudyPlan, type StudyTask, type StudyTaskUpdate,
} from './studyPlan';
import { StudyTaskCreateDialog } from './StudyTaskCreateDialog';
import { PracticeMindMap } from './PracticeMindMap';
import { PracticeTaskInspector } from './PracticeTaskInspector';
import styles from './practice.module.css';

const panelStyle = 'flex min-w-0 flex-col rounded-2xl border border-slate-100 bg-card p-4 shadow-xs sm:p-5';
const workspacePanelStyle = cn(panelStyle, 'min-h-0 gap-4');
const workspaceScrollStyle = 'min-h-0 flex-1 xl:overflow-y-auto';
const mutedText = 'text-sm leading-6 text-(--practice-muted)';
const emptyStudyPlan: StudyPlan = { targetCompletionPercent: DEFAULT_TARGET_COMPLETION_PERCENT, tasks: [] };
type StudyProgress = ReturnType<typeof getStudyProgress>;
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

function BoardOverview({ profile, progress, isMindMap }: { profile: ApplicationProfile; progress: StudyProgress; isMindMap: boolean }) {
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
              {profile.title}{profile.company ? ` · ${profile.company}` : ''}
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

function KnowledgeGaps({ profile, compact = false }: { profile: ApplicationProfile; compact?: boolean }) {
  const hasResult = profile.attempts.some((attempt) => finishedAttempt(attempt) && attempt.answeredCount > 0);
  const attempt = activeAttempt(profile.attempts);
  const applicationUrl = `/applications/${profile.id}`;
  const href = hasResult ? `${applicationUrl}#competency` : attempt ? `/interview/session/${attempt.id}` : applicationUrl;
  const action = hasResult ? 'Xem kết quả đánh giá'
    : attempt?.status === 'In progress' ? 'Tiếp tục phỏng vấn'
    : attempt ? 'Phỏng vấn thử ngay' : 'Mở hồ sơ để phỏng vấn';

  return (
    <section className={workspacePanelStyle}>
      <PanelHeading icon={Radar} title="Lỗ hổng kiến thức" subtitle="Kỹ năng cần cải thiện" />
      <div className={cn(workspaceScrollStyle, 'flex flex-col')}>
        <div className={cn('my-auto flex flex-col items-center gap-3 py-7 text-center',
          compact && 'items-start py-0 text-left sm:flex-row sm:items-center sm:justify-between')}>
          {!compact && (
            <span className="grid size-12 place-items-center rounded-xl bg-(--practice-pale) text-(--practice-primary)">
              <Radar size={24} aria-hidden="true" />
            </span>
          )}
          <div className="space-y-2">
            <h3 className="text-sm font-semibold">Chưa có dữ liệu lỗ hổng ôn tập</h3>
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
      </div>
    </section>
  );
}

const taskColumns = {
  TODO: { Icon: FolderOpen, tone: 'bg-(--practice-primary)', hint: 'Các đầu việc mới sẽ xuất hiện ở đây.' },
  IN_PROGRESS: { Icon: Clock, tone: 'bg-orange-500', hint: 'Các đầu việc đang thực hiện sẽ xuất hiện ở đây.' },
  DONE: { Icon: CircleCheck, tone: 'bg-(--practice-green)', hint: 'Các đầu việc đã hoàn thành sẽ xuất hiện ở đây.' },
};

interface TaskBoardProps {
  tasks: readonly StudyTask[];
  skillIds: readonly string[];
  selectedTaskId: string | null;
  onSelect: (id: string) => void;
  onCreate: (task: NewStudyTask) => void;
}

function TaskBoard({ tasks, skillIds, selectedTaskId, onSelect, onCreate }: TaskBoardProps) {
  return (
    <section className={workspacePanelStyle}>
      <div className="flex shrink-0 flex-wrap items-start justify-between gap-3">
        <PanelHeading icon={ClipboardList} title="Đầu việc ôn tập" subtitle="Theo dõi từng đầu việc trong kế hoạch" />
        <StudyTaskCreateDialog skillIds={skillIds} onCreate={onCreate} />
      </div>
      <KanbanColumns tasks={tasks} selectedTaskId={selectedTaskId} onSelect={onSelect} />
    </section>
  );
}

function KanbanColumns({ tasks, selectedTaskId, onSelect }: Pick<TaskBoardProps, 'tasks' | 'selectedTaskId' | 'onSelect'>) {
  return (
    <div className="grid min-h-0 flex-1 gap-3 sm:grid-cols-3 xl:grid-rows-[minmax(0,1fr)]">
      {studyTaskStatuses.map(({ value: status, label: title }) => {
        const { Icon, tone, hint } = taskColumns[status];
        const columnTasks = tasks.filter((task) => task.status === status);

        return (
          <section key={status} className="flex min-h-0 min-w-0 flex-col gap-2 rounded-xl bg-(--practice-pale) p-2.5">
            <div className="flex shrink-0 items-center justify-between gap-2 px-1 py-1">
              <h3 className="flex items-center gap-1.5 text-xs font-semibold">
                <span className={cn('size-2 shrink-0 rounded-full', tone)} aria-hidden="true" />
                {title}
              </h3>
              <span className="rounded-full bg-card px-2 py-0.5 text-xs text-(--practice-muted)">{columnTasks.length}</span>
            </div>
            {columnTasks.length ? (
              <ul tabIndex={0} aria-label={`Đầu việc: ${title}`}
                className={cn(workspaceScrollStyle, 'space-y-2 rounded-lg focus-visible:outline-2 xl:pr-1')}>
                {columnTasks.map((task) => (
                  <li key={task.id}>
                    <button type="button" aria-pressed={selectedTaskId === task.id} onClick={() => onSelect(task.id)}
                      className="w-full cursor-pointer rounded-lg border border-transparent bg-card p-3 text-left text-sm leading-5 font-medium [overflow-wrap:anywhere] hover:border-(--practice-blue-strong) aria-pressed:border-(--practice-primary)">
                      {task.title}
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="flex min-h-32 flex-1 flex-col items-center justify-center gap-2 rounded-lg bg-card px-2 py-4 text-center sm:min-h-52 xl:min-h-0">
                <span className="grid size-10 place-items-center rounded-full bg-(--practice-pale) text-(--practice-muted)">
                  <Icon size={20} aria-hidden="true" />
                </span>
                <p className="text-xs font-semibold">Chưa có đầu việc</p>
                <p className="text-xs leading-5 text-(--practice-muted)">{hint}</p>
              </div>
            )}
          </section>
        );
      })}
    </div>
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
      <div className="flex shrink-0 gap-2">
        <Button type="button" variant="outline" disabled className="flex-1 rounded-full">Sửa</Button>
        <Button type="button" variant="outline" size="icon" disabled aria-label="Xóa đầu việc" className="rounded-full">
          <Trash2 size={15} aria-hidden="true" />
        </Button>
        <Button type="button" disabled className="flex-1 rounded-full bg-(--practice-primary)">Lưu</Button>
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

export function PracticePlanBoard({ profile, studyPlan = emptyStudyPlan }: {
  profile: ApplicationProfile;
  studyPlan?: StudyPlan;
}) {
  const [addedTasks, setAddedTasks] = useState<StudyTask[]>([]);
  const [taskUpdates, setTaskUpdates] = useState<Record<string, StudyTaskUpdate>>({});
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [view, setView] = useState<PlanView>('kanban');
  const nextLocalTaskId = useRef(0);
  const tasks = [...studyPlan.tasks, ...addedTasks].map((task) => ({ ...task, ...taskUpdates[task.id] }));
  const progress = getStudyProgress({ ...studyPlan, tasks });
  const skillIds = [...new Set(profile.skills.map((skill) => skill.jd_skill_id))];
  const isMindMap = view === 'mind-map';
  const selectedTask = tasks.find((task) => task.id === selectedTaskId);

  function createTask(task: NewStudyTask) {
    let id: string;
    do {
      id = `local-${nextLocalTaskId.current++}`;
    } while (tasks.some((existingTask) => existingTask.id === id));
    setAddedTasks((current) => [...current, { ...task, id }]);
    setSelectedTaskId(id);
  }

  function updateSelectedTask(update: StudyTaskUpdate) {
    if (selectedTask) {
      const { id } = selectedTask;
      setTaskUpdates((current) => ({ ...current, [id]: { ...current[id], ...update } }));
    }
  }

  const inspector = selectedTask && <PracticeTaskInspector key={selectedTask.id} task={selectedTask}
    onUpdate={updateSelectedTask} onClose={isMindMap ? () => setSelectedTaskId(null) : undefined} />;

  return (
    <div className="space-y-5">
      <BoardOverview profile={profile} progress={progress} isMindMap={isMindMap} />
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
            <StudyTaskCreateDialog skillIds={skillIds} onCreate={createTask} />
          </div>
        )}
      </div>
      {isMindMap ? (
        <>
          <section aria-label="Mind Map" className={cn(styles.mindMapWorkspace, selectedTask && styles.hasInspector)}>
            <PracticeMindMap title={profile.title} subtitle={profile.roleTitle} tasks={tasks} skills={profile.skills}
              selectedTaskId={selectedTaskId} onSelect={setSelectedTaskId} />
            {inspector}
          </section>
          <KnowledgeGaps profile={profile} compact />
        </>
      ) : (
        <div className={styles.workspace}>
          <KnowledgeGaps profile={profile} />
          <TaskBoard tasks={tasks} skillIds={skillIds} selectedTaskId={selectedTaskId} onCreate={createTask} onSelect={setSelectedTaskId} />
          {inspector ? <div className="grid min-h-0 min-w-0 overflow-hidden rounded-2xl border border-slate-100 shadow-xs">{inspector}</div> : <TaskNotes />}
        </div>
      )}
      <PracticeGoal progress={progress} />
    </div>
  );
}
