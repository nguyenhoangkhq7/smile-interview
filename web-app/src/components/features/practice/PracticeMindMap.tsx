'use client';

import { useEffect, useRef, useState, type MouseEvent } from 'react';
import { Circle, CircleCheck, Clock, Focus, GripVertical, LayoutGrid, Maximize, Minus, Network, Plus, RotateCcw } from 'lucide-react';
import { skillLabel } from '@/components/features/applications/applicationUi';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { KnowledgeGaps } from '@/services/studyPlans';
import { formatStudyPercent, studyTaskStatuses, studyTaskTones, type NewStudyTask, type StudyTask, type StudyTaskStatus } from './studyPlan';
import { StudyTaskCreateDialog } from './StudyTaskCreateDialog';
import { useStudyTaskDrag } from './useStudyTaskDrag';
import { useMindMapPosition, type MindMapNodeId, type MindMapPoint, type MindMapPositions } from './useMindMapPosition';
import styles from './practice.module.css';

const root = { x: 44, width: 254 };
const skill = { x: 460, width: 230 };
const leaf = { x: 790, width: 238 };
const cardHalfHeight = 22;
const skillNodeId = (id: string | null): MindMapNodeId => `skill:${id ?? ''}`;
const taskNodeId = (id: number): MindMapNodeId => `task:${id}`;

function nodeSize(id: MindMapNodeId) {
  if (id === 'root') return { width: root.width, halfHeight: 86 };
  if (id.startsWith('skill:')) return { width: skill.width, halfHeight: 48 };
  return { width: leaf.width, halfHeight: cardHalfHeight };
}

function NodeHandle({ id, title, point, position }: {
  id: MindMapNodeId;
  title: string;
  point: MindMapPoint;
  position: ReturnType<typeof useMindMapPosition>;
}) {
  return (
    <button type="button" aria-label={`Di chuyển vị trí: ${title}`} aria-describedby="mind-map-position-help"
      title="Kéo để sắp xếp thẻ" className={cn(
        'absolute grid touch-none cursor-grab place-items-center text-(--practice-muted) hover:bg-(--practice-pale) focus-visible:outline-2 active:cursor-grabbing',
        id.startsWith('task:') ? 'inset-y-0 right-0 w-8 rounded-r-xl' : 'top-2 left-2 size-6 rounded-md text-[#9a8179]',
      )}
      onPointerDown={(event) => position.start(event, id, point)}
      onPointerMove={position.move} onPointerUp={position.finish}
      onPointerCancel={position.cancel} onLostPointerCapture={position.cancel}
      onKeyDown={(event) => position.nudge(event, id, point)}>
      <GripVertical size={15} aria-hidden="true" />
    </button>
  );
}
const rowHeight = 62;
const groupGap = 36;
const minZoom = 0.1;
const maxZoom = 1.5;
const taskIcons = { TODO: Circle, IN_PROGRESS: Clock, DONE: CircleCheck };
const gapTones = {
  weak: { label: 'Cần ôn', color: '#b02700', lineColor: '#d53e15', badge: 'bg-[#ffded6] text-[#81230f]' },
  needsVerification: { label: 'Cần kiểm chứng', color: '#92400e', lineColor: '#e68b0a', badge: 'bg-[#fef0bd] text-[#78350f]' },
};

function layoutMap(tasks: readonly StudyTask[], gaps?: KnowledgeGaps) {
  const groups = new Map<string | null, StudyTask[]>();
  const children = new Map<number, StudyTask[]>();
  const ids = new Set(tasks.map((task) => task.id));
  const tones = new Map<string, (typeof gapTones)[keyof typeof gapTones]>();
  gaps?.weak.forEach(({ skillId }) => tones.set(skillId, gapTones.weak));
  gaps?.needsVerification.forEach(({ skillId }) => tones.set(skillId, gapTones.needsVerification));
  for (const task of tasks) {
    if (task.parentTaskId != null && ids.has(task.parentTaskId)) {
      const siblings = children.get(task.parentTaskId) ?? [];
      siblings.push(task);
      children.set(task.parentTaskId, siblings);
      continue;
    }
    const skillId = task.skillId ?? null;
    const group = groups.get(skillId);
    if (group) group.push(task);
    else groups.set(skillId, [task]);
  }

  const contentHeight = tasks.length * rowHeight + Math.max(0, groups.size - 1) * groupGap;
  const height = Math.max(460, contentHeight + 48);
  let top = (height - contentHeight) / 2;
  let right = leaf.x;
  const defaultPoints = new Map<number, MindMapPoint>();
  const branches = Array.from(groups, ([skillId, items]) => {
    const nodes: { task: StudyTask; parentId?: number; point: MindMapPoint }[] = [];
    const stack: { task: StudyTask; depth: number; parentId?: number }[] = items.map((task) => ({ task, depth: 0 })).reverse();
    while (stack.length) {
      const { task, depth, parentId } = stack.pop()!;
      const point = { x: leaf.x + depth * (leaf.width + 86), y: top + (nodes.length + 0.5) * rowHeight };
      right = Math.max(right, point.x);
      nodes.push({ task, parentId, point });
      defaultPoints.set(task.id, point);
      const next = children.get(task.id) ?? [];
      for (let index = next.length - 1; index >= 0; index--) {
        stack.push({ task: next[index], depth: depth + 1, parentId: task.id });
      }
    }
    const y = top + Math.min(nodes.length / 2, 2) * rowHeight;
    top += nodes.length * rowHeight + groupGap;
    const done = nodes.filter(({ task }) => task.status === 'DONE').length;
    const tone = tones.get(skillId ?? '');
    return { skillId, nodes, y, done, tone, color: tone?.color ?? '#665956' };
  });

  return {
    branches,
    height,
    defaultPoints,
    width: branches.length ? right + leaf.width + 32 : root.x * 2 + root.width,
    rootY: Math.min(height / 2, 230),
  };
}

function connection(fromX: number, fromY: number, toX: number, toY: number) {
  const middle = (fromX + toX) / 2;
  return `M ${fromX} ${fromY} C ${middle} ${fromY}, ${middle} ${toY}, ${toX} ${toY}`;
}

function NodeProgress({ percent, color, className }: { percent: number; color: string; className?: string }) {
  return (
    <div aria-hidden="true" className={cn('h-1 overflow-hidden rounded-full bg-(--practice-blue)', className)}>
      <div className="h-full rounded-full" style={{ width: `${percent}%`, backgroundColor: color }} />
    </div>
  );
}

interface PracticeMindMapProps {
  title: string;
  subtitle: string;
  tasks: readonly StudyTask[];
  skillIds: readonly string[];
  onCreate: (task: NewStudyTask) => Promise<boolean>;
  gaps?: KnowledgeGaps;
  selectedTaskId: number | null;
  positions: MindMapPositions;
  onPosition: (id: MindMapNodeId, point: MindMapPoint) => void;
  onResetPositions: () => void;
  disabled: boolean;
  completedTaskId: number | null;
  onSelect: (id: number) => void;
  onMove: (task: StudyTask, status: StudyTaskStatus) => Promise<boolean>;
}

export function PracticeMindMap({ title, subtitle, tasks, skillIds, onCreate, gaps, selectedTaskId, positions, onPosition, onResetPositions, disabled, completedTaskId, onSelect, onMove }: PracticeMindMapProps) {
  const map = useRef<HTMLDivElement>(null);
  const viewport = useRef<HTMLDivElement>(null);
  const content = useRef<HTMLDivElement>(null);
  const [zoom, setZoom] = useState(1);
  const [windowBox, setWindowBox] = useState({ x: 0, y: 0, width: 0, height: 0 });
  const [fullscreenAvailable, setFullscreenAvailable] = useState(false);
  const drag = useStudyTaskDrag({ disabled, onSelect, onMove });
  const { branches, defaultPoints, height: layoutHeight, width: layoutWidth, rootY } = layoutMap(tasks, gaps);
  let placedWidth = layoutWidth;
  let placedHeight = layoutHeight;
  let hasPositions = false;
  const nodeIds = ['root' as const, ...branches.map(({ skillId }) => skillNodeId(skillId)), ...tasks.map(({ id }) => taskNodeId(id))];
  for (const id of nodeIds) {
    const point = positions[id];
    if (!point) continue;
    const size = nodeSize(id);
    hasPositions = true;
    placedWidth = Math.max(placedWidth, point.x + size.width + 12);
    placedHeight = Math.max(placedHeight, point.y + size.halfHeight);
  }
  const width = Math.max(placedWidth, windowBox.width / zoom);
  const height = Math.max(placedHeight, windowBox.height / zoom);
  const position = useMindMapPosition(
    (id, point) => {
      const size = nodeSize(id);
      return {
        x: Math.max(0, Math.min(width - size.width - 12, point.x)),
        y: Math.max(size.halfHeight, Math.min(height - size.halfHeight, point.y)),
      };
    },
    (x, y) => {
      const rect = content.current?.getBoundingClientRect();
      return { x: (x - (rect?.left ?? 0)) / zoom, y: (y - (rect?.top ?? 0)) / zoom };
    },
    onPosition,
  );
  const done = branches.reduce((count, branch) => count + branch.done, 0);
  const percent = tasks.length ? done / tasks.length * 100 : 0;
  const selectedChildId = tasks.find((task) => task.id === selectedTaskId && task.parentTaskId != null)?.id;

  function nodePoint(id: MindMapNodeId, fallback: MindMapPoint) {
    return position.draft?.id === id ? position.draft.point : positions[id] ?? fallback;
  }

  const rootPoint = nodePoint('root', { x: root.x, y: rootY });

  useEffect(() => {
    const view = viewport.current;
    const scene = content.current;
    if (!view || !scene) return;
    const measure = () => setWindowBox({
      x: view.scrollLeft - scene.offsetLeft,
      y: view.scrollTop - scene.offsetTop,
      width: view.clientWidth,
      height: view.clientHeight,
    });
    const observer = new ResizeObserver(measure);
    observer.observe(view);
    observer.observe(scene);
    view.addEventListener('scroll', measure, { passive: true });
    setFullscreenAvailable(document.fullscreenEnabled);
    return () => {
      observer.disconnect();
      view.removeEventListener('scroll', measure);
    };
  }, []);

  useEffect(() => {
    if (selectedChildId === undefined) return;
    content.current?.querySelector(`[data-task-id="${selectedChildId}"]`)
      ?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
  }, [selectedChildId]);

  function resetView(scale: number) {
    setZoom(scale);
    viewport.current?.scrollTo({ top: 0, left: 0 });
  }

  function fitView() {
    const view = viewport.current;
    if (view) resetView(Math.min(1, view.clientWidth / placedWidth, view.clientHeight / placedHeight));
  }

  function moveFromOverview(event: MouseEvent<HTMLButtonElement>) {
    const view = viewport.current;
    const scene = content.current;
    if (!view || !scene) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    const x = event.detail ? (event.clientX - bounds.left) / bounds.width : 0.5;
    const y = event.detail ? (event.clientY - bounds.top) / bounds.height : 0.5;
    view.scrollTo({
      left: scene.offsetLeft + x * width * zoom - view.clientWidth / 2,
      top: scene.offsetTop + y * height * zoom - view.clientHeight / 2,
    });
  }

  async function toggleFullscreen() {
    try {
      if (document.fullscreenElement === map.current) await document.exitFullscreen();
      else await map.current?.requestFullscreen();
    } catch {
      setFullscreenAvailable(false);
    }
  }

  return (
    <div ref={map} className="relative flex min-h-0 min-w-0 flex-col bg-[#fafbfe] fullscreen:h-dvh">
      <p role="status" className="sr-only">{drag.announcement}</p>
      <p id="mind-map-position-help" className="sr-only">Kéo tay nắm để sắp xếp thẻ. Bạn cũng có thể dùng các phím mũi tên khi tay nắm được chọn.</p>
      {tasks.length > 0 && (
        <div role="group" aria-label="Thả đầu việc để đổi trạng thái"
          className="grid shrink-0 grid-cols-3 gap-1.5 border-b border-(--practice-blue-strong) bg-card p-2 sm:gap-2">
          {studyTaskStatuses.map(({ value, label }) => {
            const saving = drag.savingStatus === value;
            const highlighted = saving || (!disabled && drag.dropStatus === value);
            return (
              <div key={value} role="region" aria-label={`Thả vào ${label}`} aria-busy={saving || undefined}
                data-drop-active={highlighted || undefined}
                onDragOver={(event) => drag.dragOver(event, value)}
                onDragLeave={(event) => drag.dragLeave(event, value)}
                onDrop={(event) => void drag.drop(event, value, label)}
                className={cn(styles.kanbanColumn, 'flex min-h-9 min-w-0 items-center justify-center gap-1.5 rounded-lg border border-dashed px-1 text-center text-xs font-semibold',
                  highlighted ? 'border-(--practice-primary) bg-(--practice-orange)/50' : 'border-(--practice-blue-strong) bg-(--practice-pale)')}>
                <span className="size-1.5 shrink-0 rounded-full" style={{ backgroundColor: studyTaskTones[value].color }} aria-hidden="true" />
                {saving ? 'Đang chuyển…' : label}
              </div>
            );
          })}
        </div>
      )}
      <div ref={viewport} role="region" aria-label="Sơ đồ ôn tập, có thể cuộn" tabIndex={0}
        className="relative min-h-0 flex-1 overflow-auto overscroll-contain bg-[#f8f9fb] bg-[radial-gradient(#d8c9c6_1px,transparent_1px)] bg-size-[20px_20px] focus-visible:outline-2 focus-visible:outline-offset-[-2px]">
        <div ref={content} className="relative mx-auto overflow-clip" style={{ width: width * zoom, height: height * zoom }}>
          <div className="absolute inset-0 origin-top-left" style={{ width, height, transform: `scale(${zoom})` }}>
            <svg width={width} height={height} aria-hidden="true" className="pointer-events-none absolute inset-0 fill-none">
              {branches.map(({ skillId, nodes, y, done, color, tone }) => {
                const branchPoint = nodePoint(skillNodeId(skillId), { x: skill.x, y });
                return (
                  <g key={skillId ?? ''}>
                    <path d={connection(rootPoint.x + root.width, rootPoint.y, branchPoint.x, branchPoint.y)}
                      className={styles.mindMapConnection}
                      stroke={done === nodes.length ? studyTaskTones.DONE.color : tone?.lineColor ?? color} strokeWidth="2.25" />
                    {nodes.map(({ task, point: defaultPoint, parentId }) => {
                      const point = nodePoint(taskNodeId(task.id), defaultPoint);
                      const parent = parentId === undefined ? undefined : defaultPoints.get(parentId);
                      const start = parent && parentId !== undefined ? nodePoint(taskNodeId(parentId), parent) : branchPoint;
                      return <path key={task.id} d={connection(start.x + (parent ? leaf.width : skill.width), start.y, point.x, point.y)}
                        className={styles.mindMapConnection}
                        stroke={studyTaskTones[task.status].color} strokeDasharray={task.status === 'TODO' ? '4 3' : undefined}
                        strokeWidth={task.id === selectedTaskId ? 3 : 1.5} />;
                    })}
                  </g>
                );
              })}
            </svg>
            <div className={cn('absolute -translate-y-1/2 rounded-xl border border-[#f2e9e6] bg-card p-4 shadow-[0_12px_28px_-9px_#b027003b]', position.draft?.id === 'root' && 'z-10')}
              style={{ left: rootPoint.x, top: rootPoint.y, width: root.width }}>
              <div className="flex items-center justify-between gap-2 pl-5 text-(--practice-primary)">
                <span className="flex items-center gap-1.5 rounded-full bg-[#fce9e3] px-2 py-0.5 text-[11px] font-bold tracking-wide uppercase">
                  <span className="size-1.5 rounded-full bg-current" aria-hidden="true" /> Gốc kế hoạch
                </span>
                <Network size={18} aria-hidden="true" />
              </div>
              <p className="mt-2 line-clamp-2 text-lg leading-snug font-extrabold wrap-anywhere" title={title}>{title}</p>
              {subtitle && <p className="mt-0.5 truncate text-sm text-[#735951]" title={subtitle}>{subtitle}</p>}
              <div className="mt-3 space-y-1.5 border-t border-slate-100 pt-2.5 text-xs font-semibold text-[#735951]">
                <div className="flex justify-between gap-2">
                  <span>Tổng quan</span>
                  <strong className="text-right text-(--practice-primary) tabular-nums">{tasks.length ? `${done}/${tasks.length} đầu việc (${formatStudyPercent(percent)})` : 'Chưa có đầu việc'}</strong>
                </div>
                <NodeProgress percent={percent} color="var(--practice-primary)" className="h-1.5" />
              </div>
              <NodeHandle id="root" title="Gốc kế hoạch" point={rootPoint} position={position} />
              <StudyTaskCreateDialog branch={{ title: 'Gốc kế hoạch' }} connector={{ color: 'var(--practice-primary)', filled: true }}
                skillIds={skillIds} onCreate={onCreate} disabled={disabled} />
            </div>
            {branches.map(({ skillId, nodes, y, done: completed, tone: gapTone, color }) => {
              const branchProgress = completed / nodes.length * 100;
              const branchId = skillNodeId(skillId);
              const branchPoint = nodePoint(branchId, { x: skill.x, y });
              const branchTitle = skillId ? skillLabel(skillId) : 'Chưa gắn kỹ năng';
              return (
                <div key={skillId ?? ''}>
                  <div className={cn('absolute -translate-y-1/2 rounded-xl border-l-4 bg-card px-4 py-2.5 shadow-[0_3px_7px_#141c2420]', position.draft?.id === branchId && 'z-10')}
                    style={{ left: branchPoint.x, top: branchPoint.y, width: skill.width, borderColor: gapTone?.lineColor ?? color }}>
                    <span className="absolute top-1/2 left-0 size-3 -translate-x-2/3 -translate-y-1/2 rounded-full border-[1.5px] bg-card"
                      style={{ borderColor: gapTone?.lineColor ?? color }} />
                    <div className="flex items-center gap-1.5 pl-5">
                      <p title={branchTitle} className="min-w-0 truncate text-sm font-bold">{branchTitle}</p>
                      {gapTone && <span className={cn('shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-bold', gapTone.badge)}>{gapTone.label}</span>}
                      <strong className="ml-auto shrink-0 text-xs tabular-nums" style={{ color }}>{formatStudyPercent(branchProgress)}</strong>
                    </div>
                    <div className="mt-2 flex items-center justify-between gap-2 text-xs text-[#735951]">
                      <span className="tabular-nums">{completed}/{nodes.length} hoàn thành</span>
                      <NodeProgress percent={branchProgress} color={color} className="w-16 shrink-0" />
                    </div>
                    <NodeHandle id={branchId} title={branchTitle} point={branchPoint} position={position} />
                    <StudyTaskCreateDialog branch={{ title: branchTitle, skillId }} connector={{ color: gapTone?.lineColor ?? color }}
                      skillIds={skillIds} onCreate={onCreate} disabled={disabled} />
                  </div>
                  {nodes.map(({ task, point: defaultPoint }) => {
                    const tone = studyTaskTones[task.status];
                    const Icon = taskIcons[task.status];
                    const label = studyTaskStatuses.find(({ value }) => value === task.status)?.label;
                    const id = taskNodeId(task.id);
                    const point = nodePoint(id, defaultPoint);
                    return (
                      <div key={task.id} className={cn(styles.kanbanCardSlot, 'absolute -translate-y-1/2', position.draft?.id === id && 'z-10')}
                        data-task-id={task.id}
                        data-arrival={drag.arrival?.id === task.id && drag.arrival.status === task.status ? drag.arrival.direction : undefined}
                        onAnimationEnd={(event) => {
                          if (event.target === event.currentTarget) drag.finishArrival(task);
                        }}
                        style={{ left: point.x, top: point.y, width: leaf.width }}>
                        <button type="button" aria-pressed={task.id === selectedTaskId} onClick={() => onSelect(task.id)}
                          data-completed={task.id === completedTaskId || undefined}
                          draggable={!disabled} onDragStart={(event) => drag.startDrag(event, task)} onDragEnd={drag.finishDrag}
                          className={cn(styles.kanbanCard, 'relative flex h-11 w-full items-center gap-2 rounded-xl border border-transparent bg-card py-1 pl-2.5 pr-9 text-left shadow-sm select-none hover:border-(--practice-blue-strong) focus-visible:outline-2 aria-pressed:border-blue-400 aria-pressed:ring-2 aria-pressed:ring-blue-100',
                            disabled ? 'cursor-pointer' : 'cursor-grab active:cursor-grabbing', drag.draggingId === task.id && 'opacity-45')}>
                          <span className="absolute top-1/2 -left-1 size-2 -translate-y-1/2 rounded-full" style={{ backgroundColor: tone.color }} />
                          <Icon size={14} className="shrink-0" style={{ color: tone.color }} aria-hidden="true" />
                          <span className={cn('line-clamp-2 min-w-0 flex-1 text-xs leading-4 font-semibold [overflow-wrap:anywhere]', task.status === 'DONE' && 'text-(--practice-muted) line-through')} title={task.title}>{task.title}</span>
                          <span className={cn('shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-semibold', tone.badge)}>{label}</span>
                        </button>
                        <NodeHandle id={id} title={task.title} point={point} position={position} />
                        <StudyTaskCreateDialog parent={task} skillIds={skillIds} onCreate={onCreate} disabled={disabled} />
                      </div>
                    );
                  })}
                </div>
              );
            })}
          </div>
        </div>
      </div>
      <div role="group" aria-label="Điều khiển sơ đồ" className="absolute bottom-3 left-3 flex items-center gap-0.5 rounded-full bg-card p-1 shadow-md sm:left-4">
        <Button type="button" variant="ghost" size="icon-sm" aria-label="Phóng to" title="Phóng to" disabled={zoom >= maxZoom}
          onClick={() => setZoom((value) => Math.min(maxZoom, value + 0.1))}><Plus aria-hidden="true" /></Button>
        <Button type="button" variant="ghost" size="icon-sm" aria-label="Thu nhỏ" title="Thu nhỏ" disabled={zoom <= minZoom}
          onClick={() => setZoom((value) => Math.max(minZoom, value - 0.1))}><Minus aria-hidden="true" /></Button>
        <Button type="button" variant="ghost" size="icon-sm" aria-label="Vừa khung nhìn" title="Vừa khung nhìn"
          onClick={fitView}><Focus aria-hidden="true" /></Button>
        <Button type="button" variant="ghost" size="icon-sm" aria-label="Đặt lại vị trí và mức thu phóng" title="Đặt lại vị trí và mức thu phóng"
          onClick={() => resetView(1)}><RotateCcw aria-hidden="true" /></Button>
        {hasPositions && <Button type="button" variant="ghost" size="icon-sm" aria-label="Khôi phục bố cục thẻ" title="Khôi phục bố cục thẻ"
          onClick={onResetPositions}><LayoutGrid aria-hidden="true" /></Button>}
        {fullscreenAvailable && <Button type="button" variant="ghost" size="icon-sm" aria-label="Bật hoặc tắt toàn màn hình" title="Toàn màn hình"
          onClick={toggleFullscreen}><Maximize aria-hidden="true" /></Button>}
        <span className="px-2 text-xs tabular-nums text-(--practice-muted)">{formatStudyPercent(Math.round(zoom * 100))}</span>
      </div>
      {!!branches.length && (
        <div className="absolute right-4 bottom-3 hidden w-36 rounded-lg bg-card p-2 shadow-md sm:block">
          <p className="mb-1 text-[10px] font-bold tracking-wide text-(--practice-muted) uppercase">Mini map</p>
          <button type="button" onClick={moveFromOverview} aria-label="Di chuyển khung nhìn sơ đồ"
            className="block w-full cursor-crosshair overflow-hidden rounded-sm bg-(--practice-pale) focus-visible:outline-2">
            <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" aria-hidden="true" className="block h-16 w-full">
              <rect x={rootPoint.x} y={rootPoint.y - 35} width={root.width} height={70} rx="12" fill="#b02700" opacity=".55" />
              {branches.map(({ skillId, y, nodes, color }) => {
                const point = nodePoint(skillNodeId(skillId), { x: skill.x, y });
                return (
                <g key={skillId ?? ''}>
                  <rect x={point.x} y={point.y - 20} width={skill.width} height={40} rx="10" fill={color} />
                  {nodes.map(({ task, point: defaultPoint }) => {
                    const taskPosition = nodePoint(taskNodeId(task.id), defaultPoint);
                    return <rect key={task.id} x={taskPosition.x} y={taskPosition.y - 12} width={leaf.width} height={24} rx="8" fill={studyTaskTones[task.status].color} opacity=".55" />;
                  })}
                </g>
                );
              })}
              <rect x={windowBox.x / zoom} y={windowBox.y / zoom} width={windowBox.width / zoom} height={windowBox.height / zoom}
                rx="8" fill="#b0270010" stroke="#b02700" strokeWidth="1" vectorEffect="non-scaling-stroke" />
            </svg>
          </button>
        </div>
      )}
    </div>
  );
}
