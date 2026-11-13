'use client';

import { useCallback, useEffect, useMemo, useRef, useState, type DragEvent, type PointerEvent } from 'react';
import {
  Circle, CircleCheck, Clock, Download, Focus, Grid3X3, GripVertical, Hand, LayoutGrid, Map as MapIcon,
  Maximize, Minimize, Minus, MousePointer2, Network, Plus, RotateCcw,
} from 'lucide-react';
import { skillLabel } from '@/components/features/applications/applicationUi';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import type { KnowledgeGaps } from '@/services/studyPlans';
import { formatStudyPercent, studyTaskStatuses, studyTaskTones, type NewStudyTask, type StudyTask, type StudyTaskStatus } from './studyPlan';
import { StudyTaskCreateDialog } from './StudyTaskCreateDialog';
import { useStudyTaskDrag } from './useStudyTaskDrag';
import { useMindMapPosition, type MindMapNodeId, type MindMapPoint, type MindMapPositions } from './useMindMapPosition';
import { exportMindMapToPng } from './exportMindMapPng';
import styles from './practice.module.css';

const root = { x: 44, width: 254 };
const skill = { x: 460, width: 230 };
const leaf = { x: 790, width: 238 };
const cardHalfHeight = 22;
const rowHeight = 62;
const groupGap = 36;
const minZoom = 0.15;
const maxZoom = 2;

const skillNodeId = (id: string | null): MindMapNodeId => `skill:${id ?? ''}`;
const taskNodeId = (id: number): MindMapNodeId => `task:${id}`;

type ToolMode = 'select' | 'hand';
type Camera = { x: number; y: number; zoom: number };

function clampZoom(value: number) {
  return Math.min(maxZoom, Math.max(minZoom, value));
}

function isEditableTarget(target: EventTarget | null) {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || target.isContentEditable;
}

function nodeSize(id: MindMapNodeId) {
  if (id === 'root') return { width: root.width, halfHeight: 86 };
  if (id.startsWith('skill:')) return { width: skill.width, halfHeight: 48 };
  return { width: leaf.width, halfHeight: cardHalfHeight };
}

function NodeHandle({ id, title, point, position, className }: {
  id: MindMapNodeId;
  title: string;
  point: MindMapPoint;
  position: ReturnType<typeof useMindMapPosition>;
  className?: string;
}) {
  return (
    <button
      type="button"
      aria-label={`Di chuyển vị trí: ${title}`}
      aria-describedby="mind-map-position-help"
      title="Kéo để sắp xếp thẻ"
      className={cn(
        'absolute grid touch-none cursor-grab place-items-center text-(--practice-muted) hover:bg-(--practice-pale) focus-visible:outline-2 active:cursor-grabbing',
        id.startsWith('task:')
          ? 'top-1.5 right-1.5 size-5 rounded-md opacity-0 transition-opacity group-hover/task:opacity-100 focus-visible:opacity-100'
          : 'top-2 left-2 size-6 rounded-md text-[#9a8179]',
        className,
      )}
      onPointerDown={(event) => position.start(event, id, point)}
      onPointerMove={position.move}
      onPointerUp={position.finish}
      onPointerCancel={position.cancel}
      onLostPointerCapture={position.cancel}
      onKeyDown={(event) => position.nudge(event, id, point)}
    >
      <GripVertical size={id.startsWith('task:') ? 13 : 15} aria-hidden="true" />
    </button>
  );
}

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
    width: branches.length ? right + leaf.width + 48 : root.x * 2 + root.width,
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
      <div
        className={cn('h-full rounded-full', styles.mindMapProgressFill)}
        style={{ width: `${percent}%`, backgroundColor: color }}
      />
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
  filterTaskIds: ReadonlySet<number>;
  matchingTaskIds: ReadonlySet<number>;
  hasTaskFilters: boolean;
  onSelect: (id: number | null) => void;
  onMove: (task: StudyTask, status: StudyTaskStatus) => Promise<boolean>;
  onChangeParent: (task: StudyTask, parentTaskId: number | null) => Promise<boolean>;
}

export function PracticeMindMap({
  title,
  subtitle,
  tasks,
  skillIds,
  onCreate,
  gaps,
  selectedTaskId,
  positions,
  onPosition,
  onResetPositions,
  disabled,
  completedTaskId,
  filterTaskIds,
  matchingTaskIds,
  hasTaskFilters,
  onSelect,
  onMove,
  onChangeParent,
}: PracticeMindMapProps) {
  const map = useRef<HTMLDivElement>(null);
  const viewport = useRef<HTMLDivElement>(null);
  const content = useRef<HTMLDivElement>(null);

  const [camera, setCamera] = useState<Camera>({ x: 0, y: 0, zoom: 1 });
  const [animateCamera, setAnimateCamera] = useState(false);
  const cameraAnimTimer = useRef<number | null>(null);

  const [viewportSize, setViewportSize] = useState({ width: 0, height: 0 });
  const [toolMode, setToolMode] = useState<ToolMode>('select');
  const [spacePressed, setSpacePressed] = useState(false);
  const [isPanning, setIsPanning] = useState(false);
  const panGesture = useRef<{
    pointerId: number;
    startClientX: number;
    startClientY: number;
    startCamX: number;
    startCamY: number;
  } | null>(null);
  const backgroundClick = useRef<{ pointerId: number; x: number; y: number } | null>(null);

  const [showMiniMap, setShowMiniMap] = useState(true);
  const [showGrid, setShowGrid] = useState(true);
  const [exportingPng, setExportingPng] = useState(false);
  const [toolbarOpen, setToolbarOpen] = useState(false);
  const toolbarCollapseTimer = useRef<number | null>(null);
  const miniMapDragging = useRef<number | null>(null);

  const [fullscreenAvailable, setFullscreenAvailable] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [filterStatus, setFilterStatus] = useState<StudyTaskStatus | null>(null);
  const [hoveredNodeId, setHoveredNodeId] = useState<MindMapNodeId | null>(null);
  const [nestTargetId, setNestTargetId] = useState<number | null>(null);
  const [nestAnimation, setNestAnimation] = useState<{ sourceId: number; targetId: number } | null>(null);
  const nestAnimationTimer = useRef<number | null>(null);

  // Track newly added tasks for entry & path drawing animation
  const prevTaskIds = useRef<Set<number> | null>(null);
  const [enteringTaskIds, setEnteringTaskIds] = useState<ReadonlySet<number>>(() => new Set());
  const enteringTimer = useRef<number | null>(null);

  const drag = useStudyTaskDrag({ disabled, onMove });
  const { branches, defaultPoints, height: layoutHeight, width: layoutWidth, rootY } = useMemo(
    () => layoutMap(tasks, gaps),
    [tasks, gaps],
  );

  const isHandActive = toolMode === 'hand' || spacePressed;

  let placedWidth = layoutWidth;
  let placedHeight = layoutHeight;
  let hasPositions = false;
  const nodeIds: MindMapNodeId[] = [
    'root',
    ...branches.map(({ skillId }) => skillNodeId(skillId)),
    ...tasks.map(({ id }) => taskNodeId(id)),
  ];
  for (const id of nodeIds) {
    const point = positions[id];
    if (!point) continue;
    const size = nodeSize(id);
    hasPositions = true;
    placedWidth = Math.max(placedWidth, point.x + size.width + 48);
    placedHeight = Math.max(placedHeight, point.y + size.halfHeight + 32);
  }
  const width = placedWidth;
  const height = placedHeight;

  const position = useMindMapPosition(
    (id, point) => {
      const size = nodeSize(id);
      return {
        x: Math.max(0, point.x),
        y: Math.max(size.halfHeight, point.y),
      };
    },
    (clientX, clientY) => {
      const rect = content.current?.getBoundingClientRect();
      return {
        x: (clientX - (rect?.left ?? 0)) / camera.zoom,
        y: (clientY - (rect?.top ?? 0)) / camera.zoom,
      };
    },
    onPosition,
  );

  const done = branches.reduce((count, branch) => count + branch.done, 0);
  const percent = tasks.length ? (done / tasks.length) * 100 : 0;
  const filterActive = filterStatus !== null || hasTaskFilters;

  function nodePoint(id: MindMapNodeId, fallback: MindMapPoint) {
    return position.draft?.id === id ? position.draft.point : positions[id] ?? fallback;
  }

  const rootPoint = nodePoint('root', { x: root.x, y: rootY });

  const selectedTaskPathIds = useMemo(() => {
    const set = new Set<number>();
    let current = selectedTaskId == null ? undefined : tasks.find((task) => task.id === selectedTaskId);
    while (current) {
      set.add(current.id);
      const parentId = current.parentTaskId;
      current = parentId == null ? undefined : tasks.find((task) => task.id === parentId);
    }
    return set;
  }, [selectedTaskId, tasks]);

  // Compute hovered path context (ancestors + skill branch)
  const hoverContext = useMemo(() => {
    if (!hoveredNodeId) return null;
    const skillIdsInPath = new Set<string | null>();
    const taskIdsInPath = new Set<number>();
    if (hoveredNodeId === 'root') {
      branches.forEach((b) => skillIdsInPath.add(b.skillId));
      tasks.forEach((t) => taskIdsInPath.add(t.id));
    } else if (hoveredNodeId.startsWith('skill:')) {
      const sid = hoveredNodeId.slice(6) || null;
      skillIdsInPath.add(sid);
      const branch = branches.find((b) => (b.skillId ?? '') === (sid ?? ''));
      branch?.nodes.forEach((n) => taskIdsInPath.add(n.task.id));
    } else if (hoveredNodeId.startsWith('task:')) {
      const tid = Number(hoveredNodeId.slice(5));
      let current = tasks.find((t) => t.id === tid);
      while (current) {
        taskIdsInPath.add(current.id);
        if (current.parentTaskId == null) {
          skillIdsInPath.add(current.skillId ?? null);
          break;
        }
        const pid = current.parentTaskId;
        current = tasks.find((t) => t.id === pid);
      }
      // Also highlight direct children of hovered task
      tasks.forEach((t) => {
        if (t.parentTaskId === tid) taskIdsInPath.add(t.id);
      });
    }
    return { skillIdsInPath, taskIdsInPath };
  }, [hoveredNodeId, branches, tasks]);

  const scheduleCameraAnimation = useCallback(() => {
    setAnimateCamera(true);
    if (cameraAnimTimer.current !== null) window.clearTimeout(cameraAnimTimer.current);
    cameraAnimTimer.current = window.setTimeout(() => setAnimateCamera(false), 300);
  }, []);

  const resetView = useCallback((scale = 1) => {
    const view = viewport.current;
    const nextZoom = clampZoom(scale);
    const vh = view?.clientHeight ?? 0;
    const vw = view?.clientWidth ?? 0;
    const nextX = Math.max(0, (vw - placedWidth * nextZoom) / 2);
    const nextY = Math.max(0, (vh - placedHeight * nextZoom) / 2);
    scheduleCameraAnimation();
    setCamera({ x: nextX, y: nextY, zoom: nextZoom });
  }, [placedWidth, placedHeight, scheduleCameraAnimation]);

  const fitView = useCallback(() => {
    const view = viewport.current;
    if (!view || !view.clientWidth || !view.clientHeight) return;
    const pad = 48;
    const availW = Math.max(120, view.clientWidth - pad);
    const availH = Math.max(120, view.clientHeight - pad);
    const nextZoom = clampZoom(Math.min(1, availW / placedWidth, availH / placedHeight));
    const nextX = (view.clientWidth - placedWidth * nextZoom) / 2;
    const nextY = (view.clientHeight - placedHeight * nextZoom) / 2;
    scheduleCameraAnimation();
    setCamera({ x: nextX, y: nextY, zoom: nextZoom });
  }, [placedWidth, placedHeight, scheduleCameraAnimation]);

  const zoomAtCenter = useCallback((delta: number) => {
    const view = viewport.current;
    const cx = (view?.clientWidth ?? 0) / 2;
    const cy = (view?.clientHeight ?? 0) / 2;
    scheduleCameraAnimation();
    setCamera((prev) => {
      const nextZoom = clampZoom(Number((prev.zoom + delta).toFixed(2)));
      if (nextZoom === prev.zoom) return prev;
      const wx = (cx - prev.x) / prev.zoom;
      const wy = (cy - prev.y) / prev.zoom;
      return {
        x: cx - wx * nextZoom,
        y: cy - wy * nextZoom,
        zoom: nextZoom,
      };
    });
  }, [scheduleCameraAnimation]);

  // Measure viewport size & fullscreen availability
  useEffect(() => {
    const view = viewport.current;
    if (!view) return;
    const measure = () => setViewportSize({ width: view.clientWidth, height: view.clientHeight });
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(view);
    setFullscreenAvailable(document.fullscreenEnabled);
    const onFsChange = () => setIsFullscreen(document.fullscreenElement === map.current);
    document.addEventListener('fullscreenchange', onFsChange);
    return () => {
      observer.disconnect();
      document.removeEventListener('fullscreenchange', onFsChange);
    };
  }, []);

  // Cleanup timers on unmount
  useEffect(() => () => {
    if (nestAnimationTimer.current !== null) window.clearTimeout(nestAnimationTimer.current);
    if (cameraAnimTimer.current !== null) window.clearTimeout(cameraAnimTimer.current);
    if (enteringTimer.current !== null) window.clearTimeout(enteringTimer.current);
    if (toolbarCollapseTimer.current !== null) window.clearTimeout(toolbarCollapseTimer.current);
  }, []);

  // Detect newly added tasks for smooth entry + edge path-drawing animation
  useEffect(() => {
    const currentIds = new Set(tasks.map((t) => t.id));
    if (prevTaskIds.current !== null) {
      const added: number[] = [];
      currentIds.forEach((id) => {
        if (!prevTaskIds.current!.has(id)) added.push(id);
      });
      if (added.length > 0) {
        setEnteringTaskIds(new Set(added));
        if (enteringTimer.current !== null) window.clearTimeout(enteringTimer.current);
        enteringTimer.current = window.setTimeout(() => setEnteringTaskIds(new Set()), 650);
      }
    }
    prevTaskIds.current = currentIds;
  }, [tasks]);

  const prevSelectedIdRef = useRef<number | null>(null);
  const cameraRef = useRef(camera);
  cameraRef.current = camera;

  // Center camera if newly selected task is outside the current viewport
  useEffect(() => {
    if (selectedTaskId === prevSelectedIdRef.current) return;
    prevSelectedIdRef.current = selectedTaskId;
    if (selectedTaskId == null) return;
    const view = viewport.current;
    if (!view) return;
    const task = tasks.find((t) => t.id === selectedTaskId);
    if (!task) return;
    const fallback = defaultPoints.get(task.id);
    if (!fallback) return;
    const pt = positions[taskNodeId(task.id)] ?? fallback;
    const cam = cameraRef.current;
    const screenX = pt.x * cam.zoom + cam.x;
    const screenY = pt.y * cam.zoom + cam.y;
    const margin = 40;
    if (
      screenX < margin ||
      screenX + leaf.width * cam.zoom > view.clientWidth - margin ||
      screenY - cardHalfHeight < margin ||
      screenY + cardHalfHeight > view.clientHeight - margin
    ) {
      scheduleCameraAnimation();
      setCamera((prev) => ({
        ...prev,
        x: view.clientWidth / 2 - (pt.x + leaf.width / 2) * prev.zoom,
        y: view.clientHeight / 2 - pt.y * prev.zoom,
      }));
    }
  }, [selectedTaskId, tasks, defaultPoints, positions, scheduleCameraAnimation]);

  // Wheel scroll (vertical/horizontal) & Ctrl/Meta+Wheel (or pinch) zoom-at-cursor
  useEffect(() => {
    const view = viewport.current;
    if (!view) return;
    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      setAnimateCamera(false);
      const isZoomGesture = event.ctrlKey || event.metaKey;
      if (!isZoomGesture) {
        const dx = event.shiftKey && event.deltaX === 0 ? event.deltaY : event.deltaX;
        const dy = event.shiftKey && event.deltaX === 0 ? 0 : event.deltaY;
        setCamera((prev) => ({
          ...prev,
          x: prev.x - dx,
          y: prev.y - dy,
        }));
        return;
      }
      const rect = view.getBoundingClientRect();
      const cx = event.clientX - rect.left;
      const cy = event.clientY - rect.top;
      const factor = Math.exp(-event.deltaY * 0.008);
      setCamera((prev) => {
        const nextZoom = clampZoom(prev.zoom * factor);
        if (nextZoom === prev.zoom) return prev;
        const wx = (cx - prev.x) / prev.zoom;
        const wy = (cy - prev.y) / prev.zoom;
        return {
          x: cx - wx * nextZoom,
          y: cy - wy * nextZoom,
          zoom: nextZoom,
        };
      });
    };
    view.addEventListener('wheel', onWheel, { passive: false });
    return () => view.removeEventListener('wheel', onWheel);
  }, []);

  // Global keyboard shortcuts (H, V, Space, +/-, 0, M, Esc)
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (isEditableTarget(event.target)) return;
      if (document.querySelector('[role="dialog"]')) return;

      if (event.code === 'Space' && !event.ctrlKey && !event.metaKey && !event.altKey) {
        if (event.target instanceof HTMLButtonElement) return;
        event.preventDefault();
        setSpacePressed(true);
        return;
      }

      if (event.ctrlKey || event.metaKey || event.altKey) return;
      const key = event.key.toLowerCase();

      if (key === 'h') {
        event.preventDefault();
        setToolMode('hand');
      } else if (key === 'v') {
        event.preventDefault();
        setToolMode('select');
      } else if (key === 'm') {
        event.preventDefault();
        setShowMiniMap((prev) => !prev);
      } else if (key === 'g') {
        event.preventDefault();
        setShowGrid((prev) => !prev);
      } else if (key === '=' || key === '+') {
        event.preventDefault();
        zoomAtCenter(0.15);
      } else if (key === '-' || key === '_') {
        event.preventDefault();
        zoomAtCenter(-0.15);
      } else if (key === '0') {
        event.preventDefault();
        fitView();
      } else if (event.key === 'Escape') {
        if (isPanning) {
          panGesture.current = null;
          setIsPanning(false);
        } else if (selectedTaskId !== null) {
          onSelect(null);
        } else if (toolMode === 'hand') {
          setToolMode('select');
        }
      }
    };

    const onKeyUp = (event: KeyboardEvent) => {
      if (event.code === 'Space') setSpacePressed(false);
    };
    const onBlur = () => setSpacePressed(false);

    window.addEventListener('keydown', onKeyDown);
    window.addEventListener('keyup', onKeyUp);
    window.addEventListener('blur', onBlur);
    return () => {
      window.removeEventListener('keydown', onKeyDown);
      window.removeEventListener('keyup', onKeyUp);
      window.removeEventListener('blur', onBlur);
    };
  }, [fitView, isPanning, onSelect, selectedTaskId, toolMode, zoomAtCenter]);

  // Viewport pointer handlers (Hand Tool, Middle Mouse Pan, Background Deselect)
  function handleViewportPointerDownCapture(event: PointerEvent<HTMLDivElement>) {
    const isMiddleClick = event.button === 1;
    const isHandDrag = isHandActive && event.button === 0;
    if (isMiddleClick || isHandDrag) {
      event.preventDefault();
      event.stopPropagation();
      setAnimateCamera(false);
      panGesture.current = {
        pointerId: event.pointerId,
        startClientX: event.clientX,
        startClientY: event.clientY,
        startCamX: camera.x,
        startCamY: camera.y,
      };
      setIsPanning(true);
      event.currentTarget.setPointerCapture(event.pointerId);
      return;
    }

    if (
      !isHandActive &&
      event.button === 0 &&
      (event.target === viewport.current || event.target === content.current)
    ) {
      backgroundClick.current = { pointerId: event.pointerId, x: event.clientX, y: event.clientY };
    }
  }

  function handleViewportPointerMove(event: PointerEvent<HTMLDivElement>) {
    const active = panGesture.current;
    if (!active || active.pointerId !== event.pointerId) return;
    const dx = event.clientX - active.startClientX;
    const dy = event.clientY - active.startClientY;
    setCamera((prev) => ({
      ...prev,
      x: active.startCamX + dx,
      y: active.startCamY + dy,
    }));
  }

  function handleViewportPointerUp(event: PointerEvent<HTMLDivElement>) {
    if (panGesture.current?.pointerId === event.pointerId) {
      panGesture.current = null;
      setIsPanning(false);
      if (event.currentTarget.hasPointerCapture(event.pointerId)) {
        event.currentTarget.releasePointerCapture(event.pointerId);
      }
      return;
    }

    if (backgroundClick.current?.pointerId === event.pointerId) {
      const dist = Math.hypot(
        event.clientX - backgroundClick.current.x,
        event.clientY - backgroundClick.current.y,
      );
      backgroundClick.current = null;
      if (dist < 5 && selectedTaskId !== null) {
        onSelect(null);
      }
    }
  }

  function navigateFromMiniMap(clientX: number, clientY: number, element: HTMLButtonElement, animated: boolean) {
    const bounds = element.getBoundingClientRect();
    const rx = Math.min(1, Math.max(0, (clientX - bounds.left) / bounds.width));
    const ry = Math.min(1, Math.max(0, (clientY - bounds.top) / bounds.height));
    const targetCanvasX = rx * width;
    const targetCanvasY = ry * height;
    if (animated) scheduleCameraAnimation();
    else setAnimateCamera(false);
    setCamera((prev) => ({
      ...prev,
      x: viewportSize.width / 2 - targetCanvasX * prev.zoom,
      y: viewportSize.height / 2 - targetCanvasY * prev.zoom,
    }));
  }

  async function nestTaskOnDrop(event: DragEvent<HTMLButtonElement>, target: StudyTask) {
    const source = tasks.find((task) => task.id === drag.draggingId);
    if (!source) return;
    event.preventDefault();
    event.stopPropagation();
    setNestTargetId(null);
    let ancestor: number | null | undefined = target.parentTaskId;
    while (ancestor != null) {
      if (ancestor === source.id) return;
      ancestor = tasks.find((task) => task.id === ancestor)?.parentTaskId;
    }
    if (source.id === target.id || source.parentTaskId === target.id) return;
    drag.finishDrag();
    const saved = await onChangeParent(source, target.id);
    if (!saved) return;
    setNestAnimation({ sourceId: source.id, targetId: target.id });
    if (nestAnimationTimer.current !== null) window.clearTimeout(nestAnimationTimer.current);
    nestAnimationTimer.current = window.setTimeout(() => setNestAnimation(null), 900);
  }

  async function detachDroppedTask(event: DragEvent<HTMLDivElement>) {
    const source = tasks.find((task) => task.id === drag.draggingId);
    if (!source || source.parentTaskId == null) return;
    event.preventDefault();
    event.stopPropagation();
    setNestTargetId(null);
    drag.finishDrag();
    await onChangeParent(source, null);
  }

  async function toggleFullscreen() {
    try {
      if (document.fullscreenElement === map.current) await document.exitFullscreen();
      else await map.current?.requestFullscreen();
    } catch {
      setFullscreenAvailable(false);
    }
  }

  const scheduleToolbarCollapse = useCallback(() => {
    if (toolbarCollapseTimer.current !== null) window.clearTimeout(toolbarCollapseTimer.current);
    toolbarCollapseTimer.current = window.setTimeout(() => {
      setToolbarOpen(false);
      toolbarCollapseTimer.current = null;
    }, 7000);
  }, []);

  const keepToolbarOpen = useCallback(() => {
    setToolbarOpen(true);
    scheduleToolbarCollapse();
  }, [scheduleToolbarCollapse]);

  async function handleExportPng() {
    if (exportingPng) return;
    setExportingPng(true);
    try {
      await exportMindMapToPng({
        title,
        subtitle,
        tasksCount: tasks.length,
        doneCount: done,
        percent,
        width,
        height,
        rootPoint,
        rootWidth: root.width,
        skillX: skill.x,
        skillWidth: skill.width,
        leafWidth: leaf.width,
        branches,
        defaultPoints,
        positions,
        showGrid,
        gaps,
      });
    } finally {
      setExportingPng(false);
    }
  }

  // Visible viewport box in canvas coordinates for Mini Map
  const windowBox = {
    x: -camera.x / camera.zoom,
    y: -camera.y / camera.zoom,
    width: viewportSize.width / camera.zoom,
    height: viewportSize.height / camera.zoom,
  };

  return (
    <div ref={map} className={cn('relative flex min-h-0 min-w-0 flex-col bg-[#fafbfe] fullscreen:h-dvh', styles.mindMapCanvasEnter)}>
      <p role="status" className="sr-only">{drag.announcement}</p>
      <p id="mind-map-position-help" className="sr-only">
        Dùng tay nắm trên thẻ để sắp xếp sơ đồ. Nhấn H để bật Hand Tool hoặc giữ Space để kéo bảng vẽ.
      </p>

      {tasks.length > 0 && (
        <div
          role="group"
          aria-label="Lọc theo trạng thái hoặc thả để đổi trạng thái"
          className="shrink-0 border-b border-(--practice-blue-strong) bg-card px-2 py-2.5 sm:px-3"
        >
          <div className="grid grid-cols-3 gap-1.5 sm:gap-2">
            {studyTaskStatuses.map(({ value, label }) => {
              const saving = drag.savingStatus === value;
              const highlighted = saving || (!disabled && drag.dropStatus === value);
              const StatusIcon = taskIcons[value];
              const count = tasks.filter((task) => task.status === value && (!hasTaskFilters || matchingTaskIds.has(task.id))).length;
              const selected = filterStatus === value;
              return (
                <button
                  key={value}
                  type="button"
                  aria-pressed={selected}
                  aria-label={selected ? `Bỏ lọc trạng thái ${label}` : `Lọc task trạng thái ${label}; cũng có thể thả task vào đây để đổi trạng thái`}
                  aria-busy={saving || undefined}
                  data-drop-active={highlighted || undefined}
                  data-filter-selected={selected || undefined}
                  onClick={() => setFilterStatus((current) => (current === value ? null : value))}
                  onDragOver={(event) => drag.dragOver(event, value)}
                  onDragLeave={(event) => drag.dragLeave(event, value)}
                  onDrop={(event) => void drag.drop(event, value, label)}
                  className={cn(
                    styles.mindMapStatusFilter,
                    'flex min-h-10 min-w-0 items-center justify-center gap-1.5 rounded-xl border px-2 text-center text-xs font-semibold sm:gap-2 sm:text-sm',
                    selected ? 'bg-card shadow-sm' : 'border-transparent bg-(--practice-pale) hover:bg-(--practice-blue)',
                  )}
                  style={{ color: studyTaskTones[value].color, ...(selected ? { borderColor: studyTaskTones[value].color } : {}) }}
                >
                  <StatusIcon size={15} className="shrink-0" aria-hidden="true" />
                  <span className="truncate">{saving ? 'Đang chuyển…' : label}</span>
                  <span className="rounded-full bg-white/80 px-1.5 py-0.5 text-[10px] tabular-nums sm:text-[11px]">{count}</span>
                </button>
              );
            })}
          </div>
          <p className="mt-1.5 text-center text-[10px] text-(--practice-muted)">
            {filterStatus
              ? `Đang lọc: ${studyTaskStatuses.find(({ value }) => value === filterStatus)?.label} · nhấn lại để bỏ lọc`
              : 'Nhấn trạng thái để làm nổi bật task · kéo vào đây để đổi trạng thái · giữ Space hoặc nhấn H để kéo bảng'}
          </p>
        </div>
      )}

      <div
        ref={viewport}
        role="region"
        aria-label="Sơ đồ ôn tập tương tác"
        tabIndex={0}
        onPointerDownCapture={handleViewportPointerDownCapture}
        onPointerMove={handleViewportPointerMove}
        onPointerUp={handleViewportPointerUp}
        onPointerCancel={handleViewportPointerUp}
        className={cn(
          'relative min-h-0 flex-1 touch-none overflow-hidden bg-[#f8f9fb] select-none focus-visible:outline-2 focus-visible:outline-offset-[-2px]',
          isPanning ? 'cursor-grabbing' : isHandActive ? 'cursor-grab' : 'cursor-default',
        )}
        style={{
          backgroundImage: showGrid ? 'radial-gradient(#d8c9c6 1px, transparent 1px)' : undefined,
          backgroundPosition: `${camera.x}px ${camera.y}px`,
          backgroundSize: `${20 * camera.zoom}px ${20 * camera.zoom}px`,
        }}
      >
        <div
          ref={content}
          data-filter-active={filterActive || undefined}
          data-selection-active={selectedTaskId !== null || undefined}
          data-hover-active={hoveredNodeId !== null || undefined}
          data-hand-active={isHandActive || undefined}
          className={cn(
            styles.mindMapScene,
            'absolute top-0 left-0 origin-top-left',
            animateCamera && styles.mindMapCameraAnimated,
          )}
          style={{
            width,
            height,
            transform: `translate3d(${camera.x}px, ${camera.y}px, 0) scale(${camera.zoom})`,
          }}
          onDragOver={(event) => {
            if (drag.draggingId != null) {
              event.preventDefault();
              event.dataTransfer.dropEffect = 'move';
            }
          }}
          onDrop={(event) => void detachDroppedTask(event)}
        >
          <svg width={width} height={height} aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-visible fill-none">
            {branches.map(({ skillId, nodes, y, done: branchDone, color, tone }) => {
              const branchPoint = nodePoint(skillNodeId(skillId), { x: skill.x, y });
              const branchPath = connection(rootPoint.x + root.width, rootPoint.y, branchPoint.x, branchPoint.y);
              const branchStroke = branchDone === nodes.length ? studyTaskTones.DONE.color : tone?.lineColor ?? color;
              const branchHovered = hoverContext?.skillIdsInPath.has(skillId) ?? false;
              const branchHasInProgress = nodes.some((n) => n.task.status === 'IN_PROGRESS');

              return (
                <g key={skillId ?? ''}>
                  <path
                    d={branchPath}
                    data-mindmap-context
                    data-selection-context
                    data-hover-context={branchHovered || undefined}
                    className={cn(
                      styles.mindMapConnection,
                      branchDone === nodes.length && nodes.length > 0 && styles.mindMapDonePulse,
                    )}
                    stroke={branchStroke}
                    strokeWidth={branchHovered ? 2.75 : 2.25}
                  />
                  {(branchHasInProgress || branchHovered) && (
                    <path
                      d={branchPath}
                      data-hover-context={branchHovered || undefined}
                      className={styles.mindMapFlowLight}
                      stroke={branchHasInProgress ? '#3b82f6' : branchStroke}
                      strokeWidth={branchHovered ? 2.5 : 2}
                      opacity={branchHovered ? 0.75 : 0.45}
                    />
                  )}
                  {nodes.map(({ task, point: defaultPoint, parentId }) => {
                    const point = nodePoint(taskNodeId(task.id), defaultPoint);
                    const parent = parentId === undefined ? undefined : defaultPoints.get(parentId);
                    const start = parent && parentId !== undefined ? nodePoint(taskNodeId(parentId), parent) : branchPoint;
                    const taskPath = connection(start.x + (parent ? leaf.width : skill.width), start.y, point.x, point.y);
                    const isNewNesting = nestAnimation?.sourceId === task.id && nestAnimation.targetId === parentId;
                    const isEntering = enteringTaskIds.has(task.id);
                    const filterMatch = (!filterStatus || task.status === filterStatus) && (!hasTaskFilters || matchingTaskIds.has(task.id));
                    const filterContext = hasTaskFilters && filterTaskIds.has(task.id) && !matchingTaskIds.has(task.id);
                    const isSelectedPath = selectedTaskPathIds.has(task.id);
                    const isHoveredPath = hoverContext?.taskIdsInPath.has(task.id) ?? false;
                    const shouldFlow = task.status === 'IN_PROGRESS' || isSelectedPath || isHoveredPath;
                    const statusColor = studyTaskTones[task.status].color;

                    return (
                      <g key={task.id}>
                        <path
                          d={taskPath}
                          pathLength={isEntering ? 1 : undefined}
                          className={cn(
                            styles.mindMapConnection,
                            task.status === 'DONE' && !isEntering && styles.mindMapDonePulse,
                          )}
                          data-task-status={task.status}
                          data-selection-context={isSelectedPath || undefined}
                          data-hover-context={isHoveredPath || undefined}
                          data-task-selected={selectedTaskId === task.id || undefined}
                          data-task-dimmed={(selectedTaskId !== null && !isSelectedPath) || undefined}
                          data-task-filter-state={filterMatch ? 'match' : filterContext ? 'context' : 'hidden'}
                          data-nested-arrival={isNewNesting || undefined}
                          data-edge-entering={isEntering || undefined}
                          stroke={statusColor}
                          strokeDasharray={isEntering ? undefined : task.status === 'TODO' ? '4 3' : undefined}
                          strokeWidth={task.id === selectedTaskId || isHoveredPath ? 2.75 : 1.65}
                        />
                        {shouldFlow && !isEntering && (
                          <path
                            d={taskPath}
                            data-hover-context={isHoveredPath || undefined}
                            className={styles.mindMapFlowLight}
                            stroke={task.status === 'IN_PROGRESS' ? '#60a5fa' : statusColor}
                            strokeWidth={task.id === selectedTaskId || isHoveredPath ? 2.5 : 2}
                            opacity={isSelectedPath || isHoveredPath ? 0.85 : 0.65}
                          />
                        )}
                      </g>
                    );
                  })}
                </g>
              );
            })}
          </svg>

          {/* Root Node */}
          <div
            data-mindmap-context
            data-selection-context
            data-node-dragging={position.draft?.id === 'root' || undefined}
            data-node-settled={position.settledId === 'root' || undefined}
            onMouseEnter={() => !isHandActive && setHoveredNodeId('root')}
            onMouseLeave={() => setHoveredNodeId((curr) => (curr === 'root' ? null : curr))}
            className={cn(
              styles.mindMapNode,
              'absolute -translate-y-1/2 rounded-xl border border-[#f2e9e6] bg-card p-4 shadow-[0_12px_28px_-9px_#b027003b]',
              position.draft?.id === 'root' && 'z-20',
              isHandActive && 'pointer-events-none',
            )}
            style={{ left: rootPoint.x, top: rootPoint.y, width: root.width }}
          >
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
                <strong className="text-right text-(--practice-primary) tabular-nums">
                  {tasks.length ? `${done}/${tasks.length} đầu việc (${formatStudyPercent(percent)})` : 'Chưa có đầu việc'}
                </strong>
              </div>
              <NodeProgress percent={percent} color="var(--practice-primary)" className="h-1.5" />
            </div>
            <NodeHandle id="root" title="Gốc kế hoạch" point={rootPoint} position={position} />
            <StudyTaskCreateDialog
              branch={{ title: 'Gốc kế hoạch' }}
              connector={{ color: 'var(--practice-primary)', filled: true }}
              skillIds={skillIds}
              onCreate={onCreate}
              disabled={disabled}
            />
          </div>

          {/* Skill Branches & Task Nodes */}
          {branches.map(({ skillId, nodes, y, done: completed, tone: gapTone, color }) => {
            const branchProgress = (completed / nodes.length) * 100;
            const branchId = skillNodeId(skillId);
            const branchPoint = nodePoint(branchId, { x: skill.x, y });
            const branchTitle = skillId ? skillLabel(skillId) : 'Chưa gắn kỹ năng';
            return (
              <div key={skillId ?? ''}>
                <div
                  data-mindmap-context
                  data-selection-context
                  data-node-dragging={position.draft?.id === branchId || undefined}
                  data-node-settled={position.settledId === branchId || undefined}
                  onMouseEnter={() => !isHandActive && setHoveredNodeId(branchId)}
                  onMouseLeave={() => setHoveredNodeId((curr) => (curr === branchId ? null : curr))}
                  className={cn(
                    styles.mindMapNode,
                    'absolute -translate-y-1/2 rounded-xl border-l-4 bg-card px-4 py-2.5 shadow-[0_3px_7px_#141c2420]',
                    position.draft?.id === branchId && 'z-20',
                    isHandActive && 'pointer-events-none',
                  )}
                  style={{ left: branchPoint.x, top: branchPoint.y, width: skill.width, borderColor: gapTone?.lineColor ?? color }}
                >
                  <span
                    className="absolute top-1/2 left-0 size-3 -translate-x-2/3 -translate-y-1/2 rounded-full border-[1.5px] bg-card"
                    style={{ borderColor: gapTone?.lineColor ?? color }}
                  />
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
                  <StudyTaskCreateDialog
                    branch={{ title: branchTitle, skillId }}
                    connector={{ color: gapTone?.lineColor ?? color }}
                    skillIds={skillIds}
                    onCreate={onCreate}
                    disabled={disabled}
                  />
                </div>

                {nodes.map(({ task, point: defaultPoint }) => {
                  const tone = studyTaskTones[task.status];
                  const Icon = taskIcons[task.status];
                  const label = studyTaskStatuses.find(({ value }) => value === task.status)?.label;
                  const id = taskNodeId(task.id);
                  const point = nodePoint(id, defaultPoint);
                  const filterMatch = (!filterStatus || task.status === filterStatus) && (!hasTaskFilters || matchingTaskIds.has(task.id));
                  const filterContext = hasTaskFilters && filterTaskIds.has(task.id) && !matchingTaskIds.has(task.id);
                  const filterState = filterMatch ? 'match' : filterContext ? 'context' : 'hidden';
                  const isDraggingPos = position.draft?.id === id;

                  return (
                    <div
                      key={task.id}
                      className={cn(styles.kanbanCardSlot, 'group/task absolute -translate-y-1/2', isDraggingPos && 'z-20', isHandActive && 'pointer-events-none')}
                      data-task-id={task.id}
                      data-task-status={task.status}
                      data-task-selected={selectedTaskId === task.id || undefined}
                      data-task-dimmed={(selectedTaskId !== null && !selectedTaskPathIds.has(task.id)) || undefined}
                      data-selection-context={(selectedTaskPathIds.has(task.id) && selectedTaskId !== task.id) || undefined}
                      data-task-filter-state={filterState}
                      data-arrival={drag.arrival?.id === task.id && drag.arrival.status === task.status ? drag.arrival.direction : undefined}
                      onMouseEnter={() => !isHandActive && setHoveredNodeId(id)}
                      onMouseLeave={() => setHoveredNodeId((curr) => (curr === id ? null : curr))}
                      onAnimationEnd={(event) => {
                        if (event.target === event.currentTarget) drag.finishArrival(task);
                      }}
                      style={{ left: point.x, top: point.y, width: leaf.width }}
                    >
                      <button
                        type="button"
                        aria-pressed={task.id === selectedTaskId}
                        onClick={() => onSelect(task.id)}
                        data-completed={task.id === completedTaskId || undefined}
                        data-filter-match={filterActive ? filterMatch : undefined}
                        data-node-selected={task.id === selectedTaskId || undefined}
                        data-node-dragging={isDraggingPos || undefined}
                        data-node-settled={position.settledId === id || undefined}
                        data-node-entering={enteringTaskIds.has(task.id) || undefined}
                        style={filterMatch ? { color: tone.color } : undefined}
                        data-nest-target={nestTargetId === task.id || undefined}
                        draggable={!disabled && !isHandActive}
                        onDragStart={(event) => drag.startDrag(event, task)}
                        onDragEnd={() => {
                          setNestTargetId(null);
                          drag.finishDrag();
                        }}
                        onDragOver={(event) => {
                          if (disabled || drag.draggingId == null) return;
                          event.preventDefault();
                          event.dataTransfer.dropEffect = 'move';
                          if (drag.draggingId !== task.id) setNestTargetId(task.id);
                        }}
                        onDragLeave={(event) => {
                          if (!(event.relatedTarget instanceof Node && event.currentTarget.contains(event.relatedTarget))) {
                            setNestTargetId(null);
                          }
                        }}
                        onDrop={(event) => void nestTaskOnDrop(event, task)}
                        className={cn(
                          styles.kanbanCard,
                          styles.mindMapNode,
                          'relative flex h-11 w-full items-center gap-2 rounded-xl border border-transparent bg-card py-1 pl-2.5 pr-6 text-left shadow-sm select-none hover:border-(--practice-blue-strong) hover:shadow-md focus-visible:outline-2 aria-pressed:border-blue-400 aria-pressed:ring-2 aria-pressed:ring-blue-100',
                          disabled ? 'cursor-pointer' : 'cursor-grab active:cursor-grabbing',
                          drag.draggingId === task.id && 'opacity-45',
                        )}
                      >
                        <span className="absolute top-1/2 -left-1 size-2 -translate-y-1/2 rounded-full" style={{ backgroundColor: tone.color }} />
                        <Icon size={14} className="shrink-0" style={{ color: tone.color }} aria-hidden="true" />
                        <span
                          className={cn(
                            'line-clamp-2 min-w-0 flex-1 text-xs leading-4 font-semibold [overflow-wrap:anywhere]',
                            task.status === 'DONE' && 'text-(--practice-muted) line-through',
                          )}
                          title={task.title}
                        >
                          {task.title}
                        </span>
                        <span className={cn('shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-semibold', tone.badge)}>{label}</span>
                        {task.gapNeedsConfirmation && (
                          <span
                            role="img"
                            aria-label="Kỹ năng đã cải thiện, task chờ xác nhận"
                            title="Kỹ năng đã cải thiện · task chờ xác nhận"
                            className="shrink-0 text-emerald-700"
                          >
                            <CircleCheck size={14} aria-hidden="true" />
                          </span>
                        )}
                      </button>
                      {!isHandActive && (
                        <NodeHandle id={id} title={task.title} point={point} position={position} className="top-1/2 -translate-y-1/2 right-1.5" />
                      )}
                      <StudyTaskCreateDialog parent={task} skillIds={skillIds} onCreate={onCreate} disabled={disabled} />
                    </div>
                  );
                })}
              </div>
            );
          })}
        </div>
      </div>

      {/* Upgraded Collapsible Interactive Canvas Toolbar */}
      <div
        role="toolbar"
        aria-label="Điều khiển bảng vẽ sơ đồ"
        onMouseEnter={keepToolbarOpen}
        onMouseMove={keepToolbarOpen}
        onPointerDown={keepToolbarOpen}
        onClick={keepToolbarOpen}
        onFocusCapture={keepToolbarOpen}
        onMouseLeave={scheduleToolbarCollapse}
        className="absolute bottom-3 left-3 z-20 flex max-w-[calc(100%-1.5rem)] items-center rounded-2xl border border-slate-200/80 bg-card/95 p-1 shadow-lg backdrop-blur-md sm:left-4"
      >
        {/* Single collapsed anchor button (shows active tool, expands drawer on hover/click) */}
        <Tooltip>
          <TooltipTrigger
            render={
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                aria-label={toolbarOpen ? 'Thu gọn thanh công cụ' : 'Mở thanh công cụ bảng vẽ'}
                aria-expanded={toolbarOpen}
                onClick={(event) => {
                  event.stopPropagation();
                  if (toolbarOpen) {
                    if (toolbarCollapseTimer.current !== null) window.clearTimeout(toolbarCollapseTimer.current);
                    setToolbarOpen(false);
                  } else {
                    keepToolbarOpen();
                  }
                }}
                className={cn(
                  'shrink-0 rounded-xl transition-colors',
                  isHandActive
                    ? 'bg-(--practice-orange) text-(--practice-primary) hover:bg-(--practice-orange)'
                    : 'bg-slate-100/80 text-slate-700 hover:bg-slate-200/80',
                )}
              />
            }
          >
            {isHandActive ? <Hand size={15} aria-hidden="true" /> : <MousePointer2 size={15} aria-hidden="true" />}
          </TooltipTrigger>
          <TooltipContent>
            {toolbarOpen ? 'Công cụ bảng vẽ (tự thu sau 7s)' : 'Đưa chuột hoặc nhấn để mở công cụ'}
          </TooltipContent>
        </Tooltip>

        {/* Smoothly sliding tool drawer */}
        <div className={styles.mindMapToolbarDrawer} data-open={toolbarOpen}>
          <div className={cn(styles.mindMapToolbarDrawerInner, 'pl-0.5')}>
            <span aria-hidden="true" className="mx-0.5 h-4 w-px shrink-0 bg-slate-200" />

            <Tooltip>
              <TooltipTrigger
                render={
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    aria-label="Công cụ chọn và kéo thẻ (V)"
                    aria-pressed={!isHandActive}
                    onClick={() => setToolMode('select')}
                    className={cn(
                      'rounded-xl transition-colors',
                      !isHandActive && 'bg-(--practice-orange) text-(--practice-primary) hover:bg-(--practice-orange)',
                    )}
                  />
                }
              >
                <MousePointer2 size={15} aria-hidden="true" />
              </TooltipTrigger>
              <TooltipContent>Công cụ chọn (V)</TooltipContent>
            </Tooltip>

            <Tooltip>
              <TooltipTrigger
                render={
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    aria-label="Công cụ kéo bảng vẽ (H)"
                    aria-pressed={isHandActive}
                    onClick={() => setToolMode('hand')}
                    className={cn(
                      'rounded-xl transition-colors',
                      isHandActive && 'bg-(--practice-orange) text-(--practice-primary) hover:bg-(--practice-orange)',
                    )}
                  />
                }
              >
                <Hand size={15} aria-hidden="true" />
              </TooltipTrigger>
              <TooltipContent>Kéo bảng vẽ (H / giữ Space)</TooltipContent>
            </Tooltip>

            <span aria-hidden="true" className="mx-0.5 h-4 w-px shrink-0 bg-slate-200" />

            <Tooltip>
              <TooltipTrigger
                render={
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    aria-label="Thu nhỏ (-)"
                    disabled={camera.zoom <= minZoom}
                    onClick={() => zoomAtCenter(-0.15)}
                    className="rounded-xl"
                  />
                }
              >
                <Minus size={15} aria-hidden="true" />
              </TooltipTrigger>
              <TooltipContent>Thu nhỏ (-)</TooltipContent>
            </Tooltip>

            <Tooltip>
              <TooltipTrigger
                render={
                  <button
                    type="button"
                    onClick={() => resetView(1)}
                    aria-label="Đặt mức thu phóng về 100%"
                    className="min-w-11 rounded-lg px-1.5 py-1 text-center text-xs font-medium tabular-nums text-(--practice-muted) transition-colors hover:bg-slate-100 hover:text-slate-900"
                  >
                    {formatStudyPercent(Math.round(camera.zoom * 100))}
                  </button>
                }
              />
              <TooltipContent>Nhấn để đặt lại 100%</TooltipContent>
            </Tooltip>

            <Tooltip>
              <TooltipTrigger
                render={
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    aria-label="Phóng to (+)"
                    disabled={camera.zoom >= maxZoom}
                    onClick={() => zoomAtCenter(0.15)}
                    className="rounded-xl"
                  />
                }
              >
                <Plus size={15} aria-hidden="true" />
              </TooltipTrigger>
              <TooltipContent>Phóng to (+)</TooltipContent>
            </Tooltip>

            <Tooltip>
              <TooltipTrigger
                render={
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    aria-label="Vừa khung nhìn (0)"
                    onClick={fitView}
                    className="rounded-xl"
                  />
                }
              >
                <Focus size={15} aria-hidden="true" />
              </TooltipTrigger>
              <TooltipContent>Vừa khung nhìn (0)</TooltipContent>
            </Tooltip>

            <Tooltip>
              <TooltipTrigger
                render={
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    aria-label="Khôi phục góc nhìn mặc định"
                    onClick={() => resetView(1)}
                    className="rounded-xl"
                  />
                }
              >
                <RotateCcw size={15} aria-hidden="true" />
              </TooltipTrigger>
              <TooltipContent>Đặt lại góc nhìn</TooltipContent>
            </Tooltip>

            <span aria-hidden="true" className="mx-0.5 h-4 w-px shrink-0 bg-slate-200" />

            <Tooltip>
              <TooltipTrigger
                render={
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    aria-label={showMiniMap ? 'Ẩn Mini Map (M)' : 'Hiện Mini Map (M)'}
                    aria-pressed={showMiniMap}
                    onClick={() => setShowMiniMap((prev) => !prev)}
                    className={cn(
                      'rounded-xl transition-colors',
                      showMiniMap && 'bg-(--practice-pale) text-(--practice-primary)',
                    )}
                  />
                }
              >
                <MapIcon size={15} aria-hidden="true" />
              </TooltipTrigger>
              <TooltipContent>{showMiniMap ? 'Ẩn Mini Map (M)' : 'Hiện Mini Map (M)'}</TooltipContent>
            </Tooltip>

            <Tooltip>
              <TooltipTrigger
                render={
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    aria-label={showGrid ? 'Ẩn lưới chấm nền (G)' : 'Hiện lưới chấm nền (G)'}
                    aria-pressed={showGrid}
                    onClick={() => setShowGrid((prev) => !prev)}
                    className={cn(
                      'rounded-xl transition-colors',
                      showGrid && 'bg-(--practice-pale) text-(--practice-primary)',
                    )}
                  />
                }
              >
                <Grid3X3 size={15} aria-hidden="true" />
              </TooltipTrigger>
              <TooltipContent>{showGrid ? 'Ẩn lưới chấm nền (G)' : 'Hiện lưới chấm nền (G)'}</TooltipContent>
            </Tooltip>

            <Tooltip>
              <TooltipTrigger
                render={
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    aria-label="Xuất sơ đồ ra ảnh PNG"
                    disabled={exportingPng}
                    onClick={() => void handleExportPng()}
                    className="rounded-xl"
                  />
                }
              >
                <Download size={15} aria-hidden="true" />
              </TooltipTrigger>
              <TooltipContent>{exportingPng ? 'Đang xuất ảnh…' : 'Xuất ảnh PNG'}</TooltipContent>
            </Tooltip>

            {hasPositions && (
              <Tooltip>
                <TooltipTrigger
                  render={
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-sm"
                      aria-label="Khôi phục bố cục thẻ"
                      onClick={onResetPositions}
                      className="rounded-xl"
                    />
                  }
                >
                  <LayoutGrid size={15} aria-hidden="true" />
                </TooltipTrigger>
                <TooltipContent>Khôi phục bố cục thẻ</TooltipContent>
              </Tooltip>
            )}

            {fullscreenAvailable && (
              <Tooltip>
                <TooltipTrigger
                  render={
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-sm"
                      aria-label={isFullscreen ? 'Thoát toàn màn hình' : 'Toàn màn hình'}
                      onClick={toggleFullscreen}
                      className="rounded-xl"
                    />
                  }
                >
                  {isFullscreen ? <Minimize size={15} aria-hidden="true" /> : <Maximize size={15} aria-hidden="true" />}
                </TooltipTrigger>
                <TooltipContent>{isFullscreen ? 'Thoát toàn màn hình' : 'Toàn màn hình'}</TooltipContent>
              </Tooltip>
            )}
          </div>
        </div>
      </div>

      {/* Collapsible Mini Map with Click & Drag Navigation */}
      {!!branches.length && showMiniMap && (
        <div
          className={cn(
            styles.mindMapOverviewEnter,
            'absolute right-4 bottom-3 z-20 hidden w-44 rounded-xl border border-slate-200/80 bg-card/95 p-2 shadow-lg backdrop-blur-md sm:block',
          )}
        >
          <div className="mb-1 flex items-center justify-between">
            <p className="text-[10px] font-bold tracking-wide text-(--practice-muted) uppercase">Mini map</p>
            <span className="text-[10px] tabular-nums text-(--practice-muted)">{tasks.length} task</span>
          </div>
          <button
            type="button"
            aria-label="Di chuyển khung nhìn sơ đồ"
            onPointerDown={(event) => {
              miniMapDragging.current = event.pointerId;
              event.currentTarget.setPointerCapture(event.pointerId);
              navigateFromMiniMap(event.clientX, event.clientY, event.currentTarget, true);
            }}
            onPointerMove={(event) => {
              if (miniMapDragging.current !== event.pointerId) return;
              navigateFromMiniMap(event.clientX, event.clientY, event.currentTarget, false);
            }}
            onPointerUp={(event) => {
              if (miniMapDragging.current !== event.pointerId) return;
              miniMapDragging.current = null;
              if (event.currentTarget.hasPointerCapture(event.pointerId)) {
                event.currentTarget.releasePointerCapture(event.pointerId);
              }
            }}
            onPointerCancel={() => {
              miniMapDragging.current = null;
            }}
            className="block w-full cursor-crosshair overflow-hidden rounded-md bg-(--practice-pale) focus-visible:outline-2"
          >
            <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" aria-hidden="true" className="block h-20 w-full">
              {branches.map(({ skillId, y, nodes, color, tone }) => {
                const branchPt = nodePoint(skillNodeId(skillId), { x: skill.x, y });
                return (
                  <g key={`mm-edge-${skillId ?? ''}`}>
                    <path
                      d={connection(rootPoint.x + root.width, rootPoint.y, branchPt.x, branchPt.y)}
                      stroke={tone?.lineColor ?? color}
                      strokeWidth="6"
                      opacity="0.35"
                      fill="none"
                    />
                    {nodes.map(({ task, point: defaultPoint, parentId }) => {
                      const taskPt = nodePoint(taskNodeId(task.id), defaultPoint);
                      const parent = parentId === undefined ? undefined : defaultPoints.get(parentId);
                      const start = parent && parentId !== undefined ? nodePoint(taskNodeId(parentId), parent) : branchPt;
                      return (
                        <path
                          key={`mm-e-${task.id}`}
                          d={connection(start.x + (parent ? leaf.width : skill.width), start.y, taskPt.x, taskPt.y)}
                          stroke={studyTaskTones[task.status].color}
                          strokeWidth="4"
                          opacity="0.35"
                          fill="none"
                        />
                      );
                    })}
                  </g>
                );
              })}

              <rect x={rootPoint.x} y={rootPoint.y - 35} width={root.width} height={70} rx="12" fill="#b02700" opacity=".65" />
              {branches.map(({ skillId, y, nodes, color }) => {
                const point = nodePoint(skillNodeId(skillId), { x: skill.x, y });
                return (
                  <g key={skillId ?? ''}>
                    <rect x={point.x} y={point.y - 20} width={skill.width} height={40} rx="10" fill={color} opacity=".8" />
                    {nodes.map(({ task, point: defaultPoint }) => {
                      const taskPosition = nodePoint(taskNodeId(task.id), defaultPoint);
                      return (
                        <rect
                          key={task.id}
                          x={taskPosition.x}
                          y={taskPosition.y - 12}
                          width={leaf.width}
                          height={24}
                          rx="8"
                          fill={studyTaskTones[task.status].color}
                          opacity=".65"
                        />
                      );
                    })}
                  </g>
                );
              })}

              <rect
                x={windowBox.x}
                y={windowBox.y}
                width={Math.max(10, windowBox.width)}
                height={Math.max(10, windowBox.height)}
                rx="8"
                fill="#b0270014"
                stroke="#b02700"
                strokeWidth="1.5"
                vectorEffect="non-scaling-stroke"
              />
            </svg>
          </button>
        </div>
      )}
    </div>
  );
}
