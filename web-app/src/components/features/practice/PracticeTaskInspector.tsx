'use client';

import { useRef } from 'react';
import { Lightbulb } from 'lucide-react';
import { skillLabel } from '@/components/features/applications/applicationUi';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import { cn } from '@/lib/utils';
import type { StudyTask, StudyTaskUpdate } from './studyPlan';
import { StudyTaskChecklist, type StudyTaskChecklistActions } from './StudyTaskChecklist';
import { StudyTaskResources, type StudyTaskResourceActions } from './StudyTaskResources';
import { TaskModalHeader, TaskModalTopBar } from './TaskModalHeader';
import { TaskModalSidebar } from './TaskModalSidebar';
import { TaskNotesSection } from './TaskNotesSection';

interface PracticeTaskInspectorProps {
  task: StudyTask;
  className?: string;
  disabled: boolean;
  skillIds: readonly string[];
  onUpdate: (update: StudyTaskUpdate) => Promise<boolean>;
  onDelete: () => Promise<boolean>;
  checklist: StudyTaskChecklistActions;
  resources: StudyTaskResourceActions;
  onClose?: () => void;
}

export function PracticeTaskInspector({
  task,
  className,
  disabled,
  skillIds,
  onUpdate,
  onDelete,
  checklist,
  resources,
  onClose,
}: PracticeTaskInspectorProps) {
  const checklistInputRef = useRef<HTMLInputElement>(null);
  const skillSelectRef = useRef<HTMLSelectElement>(null);
  const resourcesDetailsRef = useRef<HTMLDetailsElement>(null);

  function focusChecklist() {
    window.requestAnimationFrame(() => {
      checklistInputRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      checklistInputRef.current?.focus();
    });
  }

  function focusSkill() {
    window.requestAnimationFrame(() => {
      skillSelectRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      skillSelectRef.current?.focus();
    });
  }

  function focusResources() {
    if (resourcesDetailsRef.current) {
      resourcesDetailsRef.current.open = true;
      window.requestAnimationFrame(() => {
        resourcesDetailsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      });
    }
  }

  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose?.(); }}>
      <DialogContent
        showCloseButton={false}
        overlayClassName="bg-slate-900/55 backdrop-blur-xs duration-200"
        className={cn(
          'flex max-h-[90dvh] w-full flex-col gap-0 overflow-hidden rounded-2xl border-0 bg-card p-0 shadow-2xl ring-1 ring-slate-900/5 duration-200 sm:max-w-5xl',
          className,
        )}
      >
        <DialogTitle className="sr-only">Chi tiết đầu việc: {task.title}</DialogTitle>
        <DialogDescription className="sr-only">
          Chỉnh sửa tiêu đề, trạng thái, ghi chú trọng tâm, danh sách kiểm tra và tài liệu ôn tập.
        </DialogDescription>

        {/* Modal Top Bar + Body */}
        <div data-task-inspector="true" className="flex min-h-0 flex-1 flex-col overflow-hidden">
          <TaskModalTopBar task={task} onClose={() => onClose?.()} />
          <div className="min-h-0 flex-1 overflow-y-auto px-5 pb-6 pt-5 sm:px-6">
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
              {/* LEFT COLUMN (~68%): Main Task Content */}
              <div className="flex min-w-0 flex-col gap-6 lg:col-span-8">
                <TaskModalHeader
                  task={task}
                  disabled={disabled}
                  onUpdate={onUpdate}
                  onFocusChecklist={focusChecklist}
                  onFocusSkill={focusSkill}
                  onFocusResources={focusResources}
                />

                {task.gapNeedsConfirmation && (
                  <div
                    role="status"
                    className="flex items-start gap-3 rounded-xl bg-(--practice-orange)/45 p-3.5 text-sm text-foreground"
                  >
                    <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-(--practice-primary) text-white shadow-xs">
                      <Lightbulb size={16} aria-hidden="true" />
                    </span>
                    <div className="space-y-0.5">
                      <p className="text-xs font-bold text-(--practice-primary)">
                        {task.gapSourceObjectiveId
                          ? 'Các tiêu chí ôn tập đã có bằng chứng đạt yêu cầu'
                          : `Kỹ năng ${skillLabel(task.gapSourceSkillId ?? task.skillId ?? '')} đã cải thiện`}
                      </p>
                      <p className="text-xs leading-relaxed text-(--practice-muted)">
                        Đầu việc vẫn được giữ mở để bạn tự quyết định. Nếu đã nắm vững, hãy nhấn “Xác nhận đã xử lý”.
                      </p>
                    </div>
                  </div>
                )}

                <TaskNotesSection task={task} disabled={disabled} onUpdate={onUpdate} />

                <StudyTaskChecklist
                  items={task.checklist}
                  actions={checklist}
                  disabled={disabled}
                  inputRef={checklistInputRef}
                />

                <StudyTaskResources
                  items={task.resources}
                  actions={resources}
                  disabled={disabled}
                  detailsRef={resourcesDetailsRef}
                />
              </div>

              {/* RIGHT COLUMN (~32%): Trello-style Action Sidebar */}
              <div className="lg:col-span-4">
                <TaskModalSidebar
                  task={task}
                  disabled={disabled}
                  skillIds={skillIds}
                  skillSelectRef={skillSelectRef}
                  onUpdate={onUpdate}
                  onDelete={onDelete}
                  onFocusChecklist={focusChecklist}
                  onFocusResources={focusResources}
                  onClose={() => onClose?.()}
                />
              </div>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
