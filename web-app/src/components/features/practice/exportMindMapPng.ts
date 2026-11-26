import { skillLabel } from '@/components/features/applications/applicationUi';
import type { KnowledgeGaps } from '@/services/studyPlans';
import { formatStudyPercent, studyTaskStatuses, studyTaskTones, type StudyTask } from './studyPlan';
import type { MindMapNodeId, MindMapPoint, MindMapPositions } from './useMindMapPosition';

export interface ExportMindMapBranch {
  skillId: string | null;
  y: number;
  done: number;
  color: string;
  tone?: { label: string; color: string; lineColor: string };
  nodes: { task: StudyTask; parentId?: number; point: MindMapPoint }[];
}

export interface ExportMindMapParams {
  title: string;
  subtitle: string;
  tasksCount: number;
  doneCount: number;
  percent: number;
  width: number;
  height: number;
  rootPoint: MindMapPoint;
  rootWidth: number;
  skillX: number;
  skillWidth: number;
  leafWidth: number;
  branches: readonly ExportMindMapBranch[];
  defaultPoints: ReadonlyMap<number, MindMapPoint>;
  positions: MindMapPositions;
  showGrid: boolean;
  gaps?: KnowledgeGaps;
}

const FONT_FAMILY = "'Inter', system-ui, -apple-system, sans-serif";

function roundRectPath(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  const radius = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + radius, y);
  ctx.arcTo(x + w, y, x + w, y + h, radius);
  ctx.arcTo(x + w, y + h, x, y + h, radius);
  ctx.arcTo(x, y + h, x, y, radius);
  ctx.arcTo(x, y, x + w, y, radius);
  ctx.closePath();
}

function truncateText(ctx: CanvasRenderingContext2D, text: string, maxWidth: number) {
  if (ctx.measureText(text).width <= maxWidth) return text;
  let trimmed = text;
  while (trimmed.length > 1 && ctx.measureText(`${trimmed}…`).width > maxWidth) {
    trimmed = trimmed.slice(0, -1);
  }
  return `${trimmed}…`;
}

function drawBezierEdge(
  ctx: CanvasRenderingContext2D,
  fromX: number,
  fromY: number,
  toX: number,
  toY: number,
  color: string,
  lineWidth: number,
  dashed = false,
) {
  const middle = (fromX + toX) / 2;
  ctx.save();
  ctx.beginPath();
  ctx.moveTo(fromX, fromY);
  ctx.bezierCurveTo(middle, fromY, middle, toY, toX, toY);
  ctx.strokeStyle = color;
  ctx.lineWidth = lineWidth;
  if (dashed) ctx.setLineDash([4, 3]);
  ctx.stroke();
  ctx.restore();
}

function getNodePoint(positions: MindMapPositions, id: MindMapNodeId, fallback: MindMapPoint) {
  return positions[id] ?? fallback;
}

export async function exportMindMapToPng(params: ExportMindMapParams): Promise<void> {
  const {
    title,
    subtitle,
    tasksCount,
    doneCount,
    percent,
    width,
    height,
    rootPoint,
    rootWidth,
    skillX,
    skillWidth,
    leafWidth,
    branches,
    defaultPoints,
    positions,
    showGrid,
  } = params;

  const scale = 2;
  const padding = 24;
  const canvasWidth = width + padding * 2;
  const canvasHeight = height + padding * 2;

  const canvas = document.createElement('canvas');
  canvas.width = Math.ceil(canvasWidth * scale);
  canvas.height = Math.ceil(canvasHeight * scale);
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('Canvas 2D context is unavailable');

  ctx.scale(scale, scale);

  // Background
  ctx.fillStyle = '#f8f9fb';
  ctx.fillRect(0, 0, canvasWidth, canvasHeight);

  if (showGrid) {
    ctx.fillStyle = '#d8c9c6';
    for (let gx = 10; gx < canvasWidth; gx += 20) {
      for (let gy = 10; gy < canvasHeight; gy += 20) {
        ctx.beginPath();
        ctx.arc(gx, gy, 1, 0, Math.PI * 2);
        ctx.fill();
      }
    }
  }

  ctx.translate(padding, padding);

  // 1. Draw Edges
  for (const branch of branches) {
    const branchPt = getNodePoint(positions, `skill:${branch.skillId ?? ''}`, { x: skillX, y: branch.y });
    const branchStroke = branch.done === branch.nodes.length ? studyTaskTones.DONE.color : branch.tone?.lineColor ?? branch.color;
    drawBezierEdge(ctx, rootPoint.x + rootWidth, rootPoint.y, branchPt.x, branchPt.y, branchStroke, 2.25);

    for (const { task, point: defaultPoint, parentId } of branch.nodes) {
      const pt = getNodePoint(positions, `task:${task.id}`, defaultPoint);
      const parentDefault = parentId === undefined ? undefined : defaultPoints.get(parentId);
      const startPt = parentDefault && parentId !== undefined
        ? getNodePoint(positions, `task:${parentId}`, parentDefault)
        : branchPt;
      const fromX = startPt.x + (parentDefault ? leafWidth : skillWidth);
      drawBezierEdge(
        ctx,
        fromX,
        startPt.y,
        pt.x,
        pt.y,
        studyTaskTones[task.status].color,
        1.65,
        task.status === 'TODO',
      );
    }
  }

  // 2. Draw Root Node
  {
    const rx = rootPoint.x;
    const ry = rootPoint.y - 78;
    const rh = 156;
    ctx.save();
    ctx.shadowColor = 'rgba(176, 39, 0, 0.16)';
    ctx.shadowBlur = 18;
    ctx.shadowOffsetY = 6;
    roundRectPath(ctx, rx, ry, rootWidth, rh, 12);
    ctx.fillStyle = '#ffffff';
    ctx.fill();
    ctx.restore();

    roundRectPath(ctx, rx, ry, rootWidth, rh, 12);
    ctx.strokeStyle = '#f2e9e6';
    ctx.lineWidth = 1;
    ctx.stroke();

    // Badge
    roundRectPath(ctx, rx + 16, ry + 16, 114, 20, 10);
    ctx.fillStyle = '#fce9e3';
    ctx.fill();
    ctx.fillStyle = '#b02700';
    ctx.font = `700 10px ${FONT_FAMILY}`;
    ctx.fillText('● GỐC KẾ HOẠCH', rx + 24, ry + 30);

    // Title & Subtitle
    ctx.fillStyle = '#141c24';
    ctx.font = `800 16px ${FONT_FAMILY}`;
    ctx.fillText(truncateText(ctx, title, rootWidth - 32), rx + 16, ry + 62);

    if (subtitle) {
      ctx.fillStyle = '#735951';
      ctx.font = `400 13px ${FONT_FAMILY}`;
      ctx.fillText(truncateText(ctx, subtitle, rootWidth - 32), rx + 16, ry + 84);
    }

    // Divider & Summary
    ctx.strokeStyle = '#f1f5f9';
    ctx.beginPath();
    ctx.moveTo(rx + 16, ry + 100);
    ctx.lineTo(rx + rootWidth - 16, ry + 100);
    ctx.stroke();

    ctx.fillStyle = '#735951';
    ctx.font = `600 11px ${FONT_FAMILY}`;
    ctx.fillText('Tổng quan', rx + 16, ry + 120);

    const summaryText = tasksCount ? `${doneCount}/${tasksCount} đầu việc (${formatStudyPercent(percent)})` : 'Chưa có đầu việc';
    ctx.fillStyle = '#b02700';
    ctx.font = `700 11px ${FONT_FAMILY}`;
    const summaryWidth = ctx.measureText(summaryText).width;
    ctx.fillText(summaryText, rx + rootWidth - 16 - summaryWidth, ry + 120);

    // Progress bar
    roundRectPath(ctx, rx + 16, ry + 130, rootWidth - 32, 6, 3);
    ctx.fillStyle = '#e5edf9';
    ctx.fill();
    if (percent > 0) {
      roundRectPath(ctx, rx + 16, ry + 130, ((rootWidth - 32) * Math.min(100, percent)) / 100, 6, 3);
      ctx.fillStyle = '#b02700';
      ctx.fill();
    }
  }

  // 3. Draw Skill Branches & Task Nodes
  for (const branch of branches) {
    const bx = getNodePoint(positions, `skill:${branch.skillId ?? ''}`, { x: skillX, y: branch.y }).x;
    const byCenter = getNodePoint(positions, `skill:${branch.skillId ?? ''}`, { x: skillX, y: branch.y }).y;
    const bh = 68;
    const by = byCenter - bh / 2;
    const borderColor = branch.tone?.lineColor ?? branch.color;
    const branchTitle = branch.skillId ? skillLabel(branch.skillId) : 'Chưa gắn kỹ năng';
    const branchPercent = (branch.done / branch.nodes.length) * 100;

    ctx.save();
    ctx.shadowColor = 'rgba(20, 28, 36, 0.1)';
    ctx.shadowBlur = 8;
    ctx.shadowOffsetY = 2;
    roundRectPath(ctx, bx, by, skillWidth, bh, 12);
    ctx.fillStyle = '#ffffff';
    ctx.fill();
    ctx.restore();

    // Left accent border
    ctx.save();
    roundRectPath(ctx, bx, by, skillWidth, bh, 12);
    ctx.clip();
    ctx.fillStyle = borderColor;
    ctx.fillRect(bx, by, 4, bh);
    ctx.restore();

    // Connector dot
    ctx.beginPath();
    ctx.arc(bx, byCenter, 5, 0, Math.PI * 2);
    ctx.fillStyle = '#ffffff';
    ctx.fill();
    ctx.strokeStyle = borderColor;
    ctx.lineWidth = 1.5;
    ctx.stroke();

    // Title & Percent
    const pctText = formatStudyPercent(branchPercent);
    ctx.font = `700 12px ${FONT_FAMILY}`;
    const pctWidth = ctx.measureText(pctText).width;
    ctx.fillStyle = branch.color;
    ctx.fillText(pctText, bx + skillWidth - 14 - pctWidth, by + 26);

    ctx.fillStyle = '#141c24';
    ctx.font = `700 13px ${FONT_FAMILY}`;
    ctx.fillText(truncateText(ctx, branchTitle, skillWidth - 36 - pctWidth), bx + 16, by + 26);

    ctx.fillStyle = '#735951';
    ctx.font = `400 11px ${FONT_FAMILY}`;
    ctx.fillText(`${branch.done}/${branch.nodes.length} hoàn thành`, bx + 16, by + 49);

    roundRectPath(ctx, bx + skillWidth - 78, by + 43, 64, 4, 2);
    ctx.fillStyle = '#e5edf9';
    ctx.fill();
    if (branchPercent > 0) {
      roundRectPath(ctx, bx + skillWidth - 78, by + 43, (64 * Math.min(100, branchPercent)) / 100, 4, 2);
      ctx.fillStyle = branch.color;
      ctx.fill();
    }

    // Task Cards
    for (const { task, point: defaultPoint } of branch.nodes) {
      const pt = getNodePoint(positions, `task:${task.id}`, defaultPoint);
      const tx = pt.x;
      const th = 44;
      const ty = pt.y - th / 2;
      const tone = studyTaskTones[task.status];
      const statusLabel = studyTaskStatuses.find((s) => s.value === task.status)?.label ?? '';

      ctx.save();
      ctx.shadowColor = 'rgba(20, 28, 36, 0.08)';
      ctx.shadowBlur = 5;
      ctx.shadowOffsetY = 1;
      roundRectPath(ctx, tx, ty, leafWidth, th, 12);
      ctx.fillStyle = '#ffffff';
      ctx.fill();
      ctx.restore();

      roundRectPath(ctx, tx, ty, leafWidth, th, 12);
      ctx.strokeStyle = '#e2e8f0';
      ctx.lineWidth = 1;
      ctx.stroke();

      // Left status dot
      ctx.beginPath();
      ctx.arc(tx, pt.y, 4, 0, Math.PI * 2);
      ctx.fillStyle = tone.color;
      ctx.fill();

      // Status badge on right
      ctx.font = `600 10px ${FONT_FAMILY}`;
      const badgeTextW = ctx.measureText(statusLabel).width;
      const badgeW = badgeTextW + 12;
      const badgeX = tx + leafWidth - 10 - badgeW;
      roundRectPath(ctx, badgeX, ty + 13, badgeW, 18, 9);
      ctx.fillStyle = task.status === 'DONE' ? '#a9f3ba' : task.status === 'IN_PROGRESS' ? '#dbeafe' : '#e5edf9';
      ctx.fill();
      ctx.fillStyle = tone.color;
      ctx.fillText(statusLabel, badgeX + 6, ty + 25.5);

      // Task title
      ctx.fillStyle = task.status === 'DONE' ? '#526071' : '#141c24';
      ctx.font = `600 12px ${FONT_FAMILY}`;
      const maxTitleW = Math.max(40, badgeX - (tx + 16) - 6);
      const renderedTitle = truncateText(ctx, task.title, maxTitleW);
      ctx.fillText(renderedTitle, tx + 16, ty + 26);

      if (task.status === 'DONE') {
        const lineW = ctx.measureText(renderedTitle).width;
        ctx.strokeStyle = '#526071';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(tx + 16, ty + 22.5);
        ctx.lineTo(tx + 16 + lineW, ty + 22.5);
        ctx.stroke();
      }
    }
  }

  // Trigger PNG download
  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/png'));
  if (!blob) throw new Error('Failed to generate PNG image');
  const url = URL.createObjectURL(blob);
  const safeName = title
    .trim()
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');
  const link = document.createElement('a');
  link.href = url;
  link.download = `${safeName || 'mindmap'}-mindmap.png`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

