import { NextRequest, NextResponse } from 'next/server';
import { query } from '@/lib/db';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

// Global Set of active SSE client controllers
type SSEController = ReadableStreamDefaultController<Uint8Array>;
const clients = new Set<SSEController>();

function sendSSE(controller: SSEController, eventName: string, data: unknown) {
  try {
    const encoder = new TextEncoder();
    const formattedData = `event: ${eventName}\ndata: ${JSON.stringify(data)}\n\n`;
    controller.enqueue(encoder.encode(formattedData));
  } catch (err) {
    console.warn('[HR Realtime SSE] Error enqueuing message to client:', err);
    clients.delete(controller);
  }
}

function broadcastSSE(eventName: string, data: unknown) {
  for (const client of Array.from(clients)) {
    sendSSE(client, eventName, data);
  }
}

/**
 * GET /api/hr-realtime
 * Establishes an SSE stream for HR Dashboard clients
 */
export async function GET(_req: NextRequest) {
  let controllerRef: SSEController | null = null;

  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      controllerRef = controller;
      clients.add(controller);

      // Send initial connection event
      sendSSE(controller, 'connected', {
        message: 'Connected to HR Realtime Event Stream',
        timestamp: new Date().toISOString(),
      });
    },
    cancel() {
      if (controllerRef) {
        clients.delete(controllerRef);
      }
    },
  });

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream; charset=utf-8',
      'Cache-Control': 'no-cache, no-transform',
      'Connection': 'keep-alive',
      'X-Accel-Buffering': 'no',
    },
  });
}

/**
 * POST /api/hr-realtime
 * Trigger stage transition or new candidate session event
 */
export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { sessionId, stage, payload } = body;

    if (!stage) {
      return NextResponse.json({ error: 'Missing stage parameter' }, { status: 400 });
    }

    // Optional DB update if sessionId is passed
    if (sessionId) {
      try {
        await query(
          `UPDATE sessions SET current_stage = $1, updated_at = CURRENT_TIMESTAMP WHERE id = $2`,
          [stage, sessionId]
        );
      } catch (dbErr) {
        console.warn('[HR Realtime] Error updating current_stage in DB:', dbErr);
      }
    }

    const eventData = {
      sessionId,
      stage,
      payload,
      timestamp: new Date().toISOString(),
    };

    // Broadcast event to all HR clients
    broadcastSSE('SESSION_STAGE_UPDATED', eventData);

    return NextResponse.json({ success: true, broadcastedTo: clients.size, eventData });
  } catch (err) {
    const error = err as Error;
    return NextResponse.json({ error: error.message || 'Failed to dispatch realtime event' }, { status: 500 });
  }
}
