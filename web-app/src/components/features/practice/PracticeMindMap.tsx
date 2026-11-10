'use client';

import { useEffect, useRef, useState, type MouseEvent } from 'react';
import { Circle, CircleCheck, Clock, Focus, Maximize, Minus, Network, Plus, RotateCcw } from 'lucide-react';
import { skillLabel } from '@/components/features/applications/applicationUi';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { SkillGapResult } from '@/services/cvJdMatching';
import { formatStudyPercent, studyTaskStatuses, studyTaskTones, type StudyTask } from './studyPlan';

const root = { x: 32, width: 194 };
const skill = { x: 330, width: 182 };
const leaf = { x: 600, width: 238 };
const rowHeight = 62;
const groupGap = 36;
const minZoom = 0.1;
const maxZoom = 1.5;
const taskIcons = { TODO: Circle, IN_PROGRESS: Clock, DONE: CircleCheck };
const alignmentLabels = { MATCH: 'Khớp CV', PARTIAL: 'Khớp một phần', MISSING: 'Thiếu CV' };
const alignmentColors = { MATCH: '#146535', PARTIAL: '#a34c06', MISSING: '#b02700' };

function layoutMap(tasks: readonly StudyTask[], skills: readonly SkillGapResult[]) {
  const groups = new Map<string | undefined, StudyTask[]>();
  const alignments = new Map(skills.map((item) => [item.jd_skill_id, item.semantic_alignment]));
  for (const task of tasks) {
    const group = groups.get(task.skillId);
    if (group) group.push(task);
    else groups.set(task.skillId, [task]);
  }

  const contentHeight = tasks.length * rowHeight + Math.max(0, groups.size - 1) * groupGap;
  const height = Math.max(460, contentHeight + 48);
  let top = (height - contentHeight) / 2;
  const branches = Array.from(groups, ([skillId, items]) => {
    const nodes = items.map((task, index) => ({ task, y: top + (index + 0.5) * rowHeight }));
    const y = top + Math.min(items.length / 2, 2) * rowHeight;
    top += items.length * rowHeight + groupGap;
    const done = items.filter((task) => task.status === 'DONE').length;
    const alignment = alignments.get(skillId ?? '');
    return { skillId, nodes, y, done, alignment, color: alignment ? alignmentColors[alignment] : '#665956' };
  });

  return {
    branches,
    height,
    width: branches.length ? leaf.x + leaf.width + 32 : root.x * 2 + root.width,
    rootY: Math.min(height / 2, 230),
  };
}

function connection(fromX: number, fromY: number, toX: number, toY: number) {
  const middle = (fromX + toX) / 2;
  return `M ${fromX} ${fromY} C ${middle} ${fromY}, ${middle} ${toY}, ${toX} ${toY}`;
}

function NodeProgress({ percent, color }: { percent: number; color: string }) {
  return (
    <div aria-hidden="true" className="h-1 overflow-hidden rounded-full bg-(--practice-blue)">
      <div className="h-full rounded-full" style={{ width: `${percent}%`, backgroundColor: color }} />
    </div>
  );
}

interface PracticeMindMapProps {
  title: string;
  subtitle: string;
  tasks: readonly StudyTask[];
  skills: readonly SkillGapResult[];
  selectedTaskId: string | null;
  onSelect: (id: string) => void;
}

export function PracticeMindMap({ title, subtitle, tasks, skills, selectedTaskId, onSelect }: PracticeMindMapProps) {
  const map = useRef<HTMLDivElement>(null);
  const viewport = useRef<HTMLDivElement>(null);
  const content = useRef<HTMLDivElement>(null);
  const [zoom, setZoom] = useState(1);
  const [windowBox, setWindowBox] = useState({ x: 0, y: 0, width: 0, height: 0 });
  const [fullscreenAvailable, setFullscreenAvailable] = useState(false);
  const { branches, height, width, rootY } = layoutMap(tasks, skills);
  const done = branches.reduce((count, branch) => count + branch.done, 0);
  const percent = tasks.length ? done / tasks.length * 100 : 0;

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

  function resetView(scale: number) {
    setZoom(scale);
    viewport.current?.scrollTo({ top: 0, left: 0 });
  }

  function fitView() {
    const view = viewport.current;
    if (view) resetView(Math.min(1, view.clientWidth / width, view.clientHeight / height));
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
    <div ref={map} className="relative min-h-0 min-w-0 bg-[#fafbfe] fullscreen:h-dvh">
      <div ref={viewport} role="region" aria-label="Sơ đồ ôn tập, có thể cuộn" tabIndex={0}
        className="relative h-full min-h-80 overflow-auto overscroll-contain bg-[radial-gradient(#d8dfea_1px,transparent_1px)] bg-size-[20px_20px] focus-visible:outline-2 focus-visible:outline-offset-[-2px]">
        <div ref={content} className="relative mx-auto overflow-clip" style={{ width: width * zoom, height: height * zoom }}>
          <div className="absolute inset-0 origin-top-left" style={{ width, height, transform: `scale(${zoom})` }}>
            <svg width={width} height={height} aria-hidden="true" className="pointer-events-none absolute inset-0 fill-none">
              {branches.map(({ skillId, nodes, y, color }) => (
                <g key={skillId ?? ''}>
                  <path d={connection(root.x + root.width, rootY, skill.x, y)} stroke={color} strokeWidth="2" opacity=".75" />
                  {nodes.map(({ task, y: taskY }) => (
                    <path key={task.id} d={connection(skill.x + skill.width, y, leaf.x, taskY)}
                      stroke={studyTaskTones[task.status].color} strokeDasharray={task.status === 'TODO' ? '4 3' : undefined}
                      strokeWidth={task.id === selectedTaskId ? 3 : 1.5} />
                  ))}
                </g>
              ))}
            </svg>
            <div className="absolute -translate-y-1/2 rounded-xl bg-card p-3 shadow-[0_12px_25px_-10px_#b0270060]"
              style={{ left: root.x, top: rootY, width: root.width }}>
              <div className="flex items-center justify-between gap-2 text-(--practice-primary)">
                <span className="rounded-full bg-(--practice-orange)/60 px-2 py-0.5 text-[10px] font-bold tracking-wide uppercase">Gốc kế hoạch</span>
                <Network size={16} aria-hidden="true" />
              </div>
              <p className="mt-2 line-clamp-2 text-sm font-bold [overflow-wrap:anywhere]" title={title}>{title}</p>
              {subtitle && <p className="truncate text-xs text-(--practice-muted)" title={subtitle}>{subtitle}</p>}
              <div className="mt-2 space-y-1.5 border-t border-slate-100 pt-2 text-[11px]">
                <div className="flex justify-between gap-2">
                  <span>Tổng quan</span>
                  <strong className="text-(--practice-primary)">{tasks.length ? `${done}/${tasks.length} (${formatStudyPercent(percent)})` : 'Chưa có đầu việc'}</strong>
                </div>
                <NodeProgress percent={percent} color="var(--practice-primary)" />
              </div>
            </div>
            {branches.map(({ skillId, nodes, y, done: completed, alignment, color }) => {
              const branchProgress = completed / nodes.length * 100;
              return (
                <div key={skillId ?? ''}>
                  <div className="absolute -translate-y-1/2 rounded-xl border-l-2 bg-card px-3 py-2 shadow-sm"
                    style={{ left: skill.x, top: y, width: skill.width, borderColor: color }}>
                    <span className="absolute top-1/2 -left-1 size-2 -translate-y-1/2 rounded-full border bg-card" style={{ borderColor: color }} />
                    <span className="absolute top-1/2 -right-1 size-2 -translate-y-1/2 rounded-full border bg-card" style={{ borderColor: color }} />
                    <div className="flex flex-wrap items-center gap-x-1.5 gap-y-1">
                      <p className="line-clamp-2 text-xs font-bold [overflow-wrap:anywhere]">{skillId ? skillLabel(skillId) : 'Chưa gắn kỹ năng'}</p>
                      {alignment && <span className="rounded-full bg-(--practice-pale) px-1.5 py-0.5 text-[10px] font-medium" style={{ color }}>{alignmentLabels[alignment]}</span>}
                    </div>
                    <p className="mt-1.5 mb-1 flex justify-between gap-1 text-[11px] text-(--practice-muted)">
                      <span>{completed}/{nodes.length} hoàn thành</span>
                      <strong style={{ color }}>{formatStudyPercent(branchProgress)}</strong>
                    </p>
                    <NodeProgress percent={branchProgress} color={color} />
                  </div>
                  {nodes.map(({ task, y: taskY }) => {
                    const tone = studyTaskTones[task.status];
                    const Icon = taskIcons[task.status];
                    const label = studyTaskStatuses.find(({ value }) => value === task.status)?.label;
                    return (
                      <button key={task.id} type="button" aria-pressed={task.id === selectedTaskId} onClick={() => onSelect(task.id)}
                        className="absolute flex h-11 -translate-y-1/2 cursor-pointer items-center gap-2 rounded-xl border border-transparent bg-card px-2.5 text-left shadow-sm hover:border-(--practice-blue-strong) focus-visible:outline-2 aria-pressed:border-blue-400 aria-pressed:ring-2 aria-pressed:ring-blue-100"
                        style={{ left: leaf.x, top: taskY, width: leaf.width }}>
                        <span className="absolute top-1/2 -left-1 size-2 -translate-y-1/2 rounded-full" style={{ backgroundColor: tone.color }} />
                        <Icon size={14} className="shrink-0" style={{ color: tone.color }} aria-hidden="true" />
                        <span className={cn('line-clamp-2 min-w-0 flex-1 text-xs leading-4 font-semibold [overflow-wrap:anywhere]', task.status === 'DONE' && 'text-(--practice-muted) line-through')} title={task.title}>{task.title}</span>
                        <span className={cn('shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-semibold', tone.badge)}>{label}</span>
                      </button>
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
              <rect x={root.x} y={rootY - 35} width={root.width} height={70} rx="12" fill="#b02700" opacity=".55" />
              {branches.map(({ skillId, y, nodes, color }) => (
                <g key={skillId ?? ''}>
                  <rect x={skill.x} y={y - 20} width={skill.width} height={40} rx="10" fill={color} />
                  {nodes.map(({ task, y: taskY }) => (
                    <rect key={task.id} x={leaf.x} y={taskY - 12} width={leaf.width} height={24} rx="8" fill={studyTaskTones[task.status].color} opacity=".55" />
                  ))}
                </g>
              ))}
              <rect x={windowBox.x / zoom} y={windowBox.y / zoom} width={windowBox.width / zoom} height={windowBox.height / zoom}
                rx="8" fill="#b0270010" stroke="#b02700" strokeWidth="1" vectorEffect="non-scaling-stroke" />
            </svg>
          </button>
        </div>
      )}
    </div>
  );
}
