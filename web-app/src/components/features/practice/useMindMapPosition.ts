import { useRef, useState, type KeyboardEvent, type PointerEvent } from 'react';

export type MindMapPoint = { x: number; y: number };
export type MindMapNodeId = 'root' | `skill:${string}` | `task:${number}`;
export type MindMapPositions = Partial<Record<MindMapNodeId, MindMapPoint>>;

export function useMindMapPosition(
  constrain: (id: MindMapNodeId, point: MindMapPoint) => MindMapPoint,
  toCanvas: (x: number, y: number) => MindMapPoint,
  onPosition: (id: MindMapNodeId, point: MindMapPoint) => void,
) {
  const gesture = useRef<{ id: MindMapNodeId; pointerId: number; offset: MindMapPoint; start: MindMapPoint } | null>(null);
  const [draft, setDraft] = useState<{ id: MindMapNodeId; point: MindMapPoint } | null>(null);

  function start(event: PointerEvent<HTMLButtonElement>, id: MindMapNodeId, point: MindMapPoint) {
    if (event.button !== 0 || gesture.current) return;
    const pointer = toCanvas(event.clientX, event.clientY);
    gesture.current = {
      id, pointerId: event.pointerId, start: point,
      offset: { x: pointer.x - point.x, y: pointer.y - point.y },
    };
    event.currentTarget.setPointerCapture(event.pointerId);
    setDraft({ id, point });
  }

  function readPointer(event: PointerEvent<HTMLButtonElement>) {
    const active = gesture.current;
    if (!active || active.pointerId !== event.pointerId) return;
    const pointer = toCanvas(event.clientX, event.clientY);
    return { active, point: constrain(active.id, { x: pointer.x - active.offset.x, y: pointer.y - active.offset.y }) };
  }

  function move(event: PointerEvent<HTMLButtonElement>) {
    const update = readPointer(event);
    if (update) setDraft({ id: update.active.id, point: update.point });
  }

  function cancel(event: PointerEvent<HTMLButtonElement>) {
    if (gesture.current?.pointerId !== event.pointerId) return;
    gesture.current = null;
    setDraft(null);
  }

  function finish(event: PointerEvent<HTMLButtonElement>) {
    const update = readPointer(event);
    if (update && (update.point.x !== update.active.start.x || update.point.y !== update.active.start.y)) {
      onPosition(update.active.id, update.point);
    }
    cancel(event);
  }

  function nudge(event: KeyboardEvent<HTMLButtonElement>, id: MindMapNodeId, point: MindMapPoint) {
    const step = event.shiftKey ? 40 : 10;
    const offsets: Record<string, MindMapPoint> = {
      ArrowLeft: { x: -step, y: 0 }, ArrowRight: { x: step, y: 0 },
      ArrowUp: { x: 0, y: -step }, ArrowDown: { x: 0, y: step },
    };
    const offset = offsets[event.key];
    if (!offset) return;
    event.preventDefault();
    onPosition(id, constrain(id, { x: point.x + offset.x, y: point.y + offset.y }));
  }

  return { draft, start, move, cancel, finish, nudge };
}
