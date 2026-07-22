import test from 'node:test';
import assert from 'node:assert';
import http from 'node:http';
import app from '../src/app.js';
import redisClient from '../src/config/redis.js';
import {
  joinInterview,
  handleOrchestrationEvent,
  handleSignal,
  handleAudioChunk,
  processStt,
  processTts,
  handleDisconnect,
} from '../src/modules/interview/signaling.service.js';

// Setup environment variable to trigger Redis mock
process.env.NODE_ENV = 'test';

// ─── Socket Mock Factories ──────────────────────────────────────────────────

function createMockSocket(id) {
  const emitted = [];
  const joinedRooms = [];
  return {
    id,
    emitted,
    joinedRooms,
    emit(event, data) {
      emitted.push({ event, data });
    },
    to(room) {
      return {
        emit(event, data) {
          emitted.push({ room, event, data });
        },
      };
    },
    join(room) {
      joinedRooms.push(room);
    },
  };
}

function createMockIo() {
  const broadcasts = [];
  return {
    broadcasts,
    to(room) {
      return {
        emit(event, data) {
          broadcasts.push({ room, event, data });
        },
      };
    },
  };
}

// ─── HTTP Endpoint Tests ─────────────────────────────────────────────────────

test('HTTP GET /health returns UP status', async () => {
  const server = http.createServer(app);
  await new Promise((resolve) => server.listen(0, resolve));
  const port = server.address().port;

  try {
    const res = await fetch(`http://localhost:${port}/health`);
    assert.strictEqual(res.status, 200);
    const body = await res.json();
    assert.strictEqual(body.status, 'UP');
    assert.strictEqual(body.service, 'streaming-service');
  } finally {
    server.close();
  }
});

test('HTTP GET /api/v1/audio/stream-transcribe splits text and sends SSE', async () => {
  const server = http.createServer(app);
  await new Promise((resolve) => server.listen(0, resolve));
  const port = server.address().port;

  try {
    const res = await fetch(`http://localhost:${port}/api/v1/audio/stream-transcribe?text=hello+world`);
    assert.strictEqual(res.status, 200);
    assert.strictEqual(res.headers.get('content-type'), 'text/event-stream');
    
    const body = await res.text();
    assert.ok(body.includes('data: [START]'));
    assert.ok(body.includes('data: hello'));
    assert.ok(body.includes('data: world'));
    assert.ok(body.includes('data: [END]'));
  } finally {
    server.close();
  }
});

test('HTTP POST /api/v1/audio/synthesize calls TTS API and returns MP3 buffer', async () => {
  const originalFetch = globalThis.fetch;
  
  // Mock fetch to simulate Speaches TTS service
  globalThis.fetch = async (url, options) => {
    const urlStr = url.toString();
    if (urlStr.includes('/api/v1/audio/synthesize')) {
      return originalFetch(url, options);
    }
    assert.ok(urlStr.includes('/v1/audio/speech'));
    return {
      ok: true,
      arrayBuffer: async () => new ArrayBuffer(16),
    };
  };

  const server = http.createServer(app);
  await new Promise((resolve) => server.listen(0, resolve));
  const port = server.address().port;

  try {
    const res = await fetch(`http://localhost:${port}/api/v1/audio/synthesize`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: 'Hello Developer', voice: 'af_bella' }),
    });
    
    assert.strictEqual(res.status, 200);
    assert.strictEqual(res.headers.get('content-type'), 'audio/mpeg');
    const buffer = await res.arrayBuffer();
    assert.strictEqual(buffer.byteLength, 16);
  } finally {
    globalThis.fetch = originalFetch;
    server.close();
  }
});

// ─── Socket Event Tests ──────────────────────────────────────────────────────

test('Socket: joinInterview creates session and starts first question', async () => {
  const io = createMockIo();
  const socket = createMockSocket('socket-1');

  const data = {
    interviewId: 'interview-123',
    userId: 'user-candidate',
    initialQuestions: ['What is Clean Code?', 'Explain SRP'],
    interviewDomain: 'IT',
    targetJobTitle: 'Software Architect',
  };

  await joinInterview(io, socket, data);

  // Check redis storage
  const socketInfo = await redisClient.hGetAll('socket:socket-1');
  assert.strictEqual(socketInfo.interviewId, 'interview-123');
  assert.strictEqual(socketInfo.userId, 'user-candidate');

  const isParticipant = await redisClient.sRem('interview:interview-123:participants', 'user-candidate');
  assert.strictEqual(isParticipant, 1);

  // Check socket room join
  assert.ok(socket.joinedRooms.includes('interview-123'));

  // Check emitted events
  const joinedRoomEvent = socket.emitted.find(e => e.event === 'joined-room');
  assert.ok(joinedRoomEvent);
  assert.strictEqual(joinedRoomEvent.data.interviewId, 'interview-123');

  const stateUpdateEvent = socket.emitted.find(e => e.event === 'orchestration-event' && e.data?.type === 'STATE_UPDATE');
  assert.ok(stateUpdateEvent);
  
  // It should broadcast INTERVIEWER_ACTION for the first question to the room
  const interviewerAction = io.broadcasts.find(
    b => b.room === 'interview-123' && b.event === 'orchestration-event' && b.data?.type === 'INTERVIEWER_ACTION'
  );
  assert.ok(interviewerAction);
  assert.strictEqual(interviewerAction.data.payload.text, 'What is Clean Code?');
  assert.strictEqual(interviewerAction.data.payload.actionType, 'TRANSITION');
});

test('Socket: handleOrchestrationEvent blocks unauthorized user (IDOR Protection)', async () => {
  const io = createMockIo();
  const socket = createMockSocket('socket-malicious');

  // Setup Redis socket mapping for socket-malicious pointing to interview-123, but with user-malicious ID
  await redisClient.hSet('socket:socket-malicious', {
    interviewId: 'interview-123',
    userId: 'user-malicious',
  });

  // Attempt to submit candidate text on behalf of candidate
  const candidateSubmitEvent = {
    type: 'CANDIDATE_TEXT_SUBMIT',
    payload: { text: 'I am doing bad things' },
  };

  await handleOrchestrationEvent(io, socket, candidateSubmitEvent);

  // It should emit error and block
  const errorEvent = socket.emitted.find(e => e.event === 'error');
  assert.ok(errorEvent);
  assert.ok(errorEvent.data.message.includes('Access denied'));
});

test('Socket: handleSignal routes signaling messages correctly', async () => {
  const io = createMockIo();
  const socket = createMockSocket('socket-sender');

  await redisClient.hSet('socket:socket-sender', {
    interviewId: 'interview-123',
    userId: 'user-sender',
  });

  // Target socket signal routing
  await handleSignal(io, socket, {
    targetSocketId: 'socket-receiver',
    signal: 'offer-sdp',
  });

  const signalToReceiver = io.broadcasts.find(b => b.room === 'socket-receiver' && b.event === 'signal');
  assert.ok(signalToReceiver);
  assert.strictEqual(signalToReceiver.data.senderSocketId, 'socket-sender');
  assert.strictEqual(signalToReceiver.data.senderUserId, 'user-sender');
  assert.strictEqual(signalToReceiver.data.signal, 'offer-sdp');
});

test('Socket: handleAudioChunk forwards chunk to room members', async () => {
  const io = createMockIo();
  const socket = createMockSocket('socket-sender');

  await redisClient.hSet('socket:socket-sender', {
    interviewId: 'interview-123',
    userId: 'user-sender',
  });

  await handleAudioChunk(io, socket, { chunk: 'audio-bytes' });

  const chunkForward = socket.emitted.find(e => e.room === 'interview-123' && e.event === 'audio-chunk');
  assert.ok(chunkForward);
  assert.strictEqual(chunkForward.data.userId, 'user-sender');
  assert.strictEqual(chunkForward.data.chunk, 'audio-bytes');
});

test('Socket: processTts synthesizes text and returns audio buffer', async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => ({
    ok: true,
    arrayBuffer: async () => new ArrayBuffer(32),
  });

  const socket = createMockSocket('socket-client');
  try {
    await processTts(socket, 'Vietnamese text to speech');
    
    const ttsResultEvent = socket.emitted.find(e => e.event === 'tts-result');
    assert.ok(ttsResultEvent);
    assert.ok(Buffer.isBuffer(ttsResultEvent.data));
    assert.strictEqual(ttsResultEvent.data.byteLength, 32);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('Socket: handleDisconnect cleans up socket mapping and sets', async () => {
  const io = createMockIo();
  const socket = createMockSocket('socket-disconnecting');

  // Insert mock states
  await redisClient.hSet('socket:socket-disconnecting', {
    interviewId: 'interview-123',
    userId: 'user-leaver',
  });
  await redisClient.sAdd('interview:interview-123:participants', 'user-leaver');

  await handleDisconnect(io, socket);

  // Assert Redis entries are cleaned up
  const socketInfo = await redisClient.hGetAll('socket:socket-disconnecting');
  assert.deepStrictEqual(socketInfo, {});

  const isParticipant = await redisClient.sRem('interview:interview-123:participants', 'user-leaver');
  assert.strictEqual(isParticipant, 0); // Already removed by handleDisconnect

  // Peer-left notification emitted to the room
  const peerLeftEvent = socket.emitted.find(e => e.room === 'interview-123' && e.event === 'peer-left');
  assert.ok(peerLeftEvent);
  assert.strictEqual(peerLeftEvent.data.userId, 'user-leaver');
  assert.strictEqual(peerLeftEvent.data.socketId, 'socket-disconnecting');
});
