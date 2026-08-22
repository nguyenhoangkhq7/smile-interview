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
  getHonorific,
  extractCandidateInfoFromResume,
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
  
  // It should broadcast INTERVIEWER_ACTION for the warmup greeting to the room
  const interviewerAction = io.broadcasts.find(
    b => b.room === 'interview-123' && b.event === 'orchestration-event' && b.data?.type === 'INTERVIEWER_ACTION'
  );
  assert.ok(interviewerAction);
  assert.ok(interviewerAction.data.payload.text.includes('break the ice') || interviewerAction.data.payload.text.includes('introduce yourself'));
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

// ─── Honorific & Small Talk Greeting Tests ───────────────────────────────────

test('Honorific: getHonorific correctly computes Vietnamese and English addressing', () => {
  // Young candidate < 27
  const youngVi = getHonorific('Nguyễn Văn An', 22, null, 'vi');
  assert.strictEqual(youngVi.pronoun, 'em');
  assert.strictEqual(youngVi.address, 'em An');

  // Peer/Middle candidate 27-35
  const midVi = getHonorific('Trần Thị Bình', 30, null, 'vi');
  assert.strictEqual(midVi.pronoun, 'bạn');
  assert.strictEqual(midVi.address, 'bạn Bình');

  // Senior candidate > 35
  const seniorVi = getHonorific('Lê Hoàng Cường', 42, null, 'vi');
  assert.strictEqual(seniorVi.pronoun, 'anh/chị');
  assert.strictEqual(seniorVi.address, 'anh/chị Cường');

  // Year of birth calculation
  const currentYear = new Date().getFullYear();
  const yobVi = getHonorific('Phạm Đức', null, currentYear - 24, 'vi');
  assert.strictEqual(yobVi.pronoun, 'em');
  assert.strictEqual(yobVi.address, 'em Đức');

  // English addressing
  const enRes = getHonorific('John Doe', 25, null, 'en');
  assert.strictEqual(enRes.displayName, 'Doe');
});

test('Resume parsing: extractCandidateInfoFromResume extracts name and birth year', () => {
  const sampleCv = `
    Họ và tên: Hoàng Minh Khôi
    Năm sinh: 2002
    Kinh nghiệm: 2 năm làm việc với Node.js và Java
  `;
  const info = extractCandidateInfoFromResume(sampleCv);
  assert.strictEqual(info.name, 'Hoàng Minh Khôi');
  assert.strictEqual(info.yearOfBirth, 2002);
  assert.strictEqual(info.age, new Date().getFullYear() - 2002);
});

test('Socket: joinInterview includes candidate name and warm greeting in first question', async () => {
  const io = createMockIo();
  const socket = createMockSocket('socket-candidate-an');

  const data = {
    interviewId: 'interview-warmup-1',
    userId: 'user-an',
    candidateName: 'Nguyễn Văn An',
    candidateAge: 23,
    initialQuestions: ['Giới thiệu đôi nét về bản thân và dự án gần đây nhất.'],
    interviewDomain: 'IT',
    targetJobTitle: 'Java Backend Developer',
    language: 'vi',
  };

  await joinInterview(io, socket, data);

  const interviewerAction = io.broadcasts.find(
    b => b.room === 'interview-warmup-1' && b.event === 'orchestration-event' && b.data?.type === 'INTERVIEWER_ACTION'
  );
  assert.ok(interviewerAction);
  const text = interviewerAction.data.payload.text;
  assert.ok(text.includes('em An'));
  assert.ok(text.includes('Java Backend Developer'));
  assert.ok(text.includes('thoải mái'));
});

test('Socket: handleOrchestrationEvent RESTART_INTERVIEW resets session and re-broadcasts question 1', async () => {
  const io = createMockIo();
  const socket = createMockSocket('socket-restart-1');

  // Join first to create session and establish socket mapping
  const data = {
    interviewId: 'interview-restart-test',
    userId: 'user-restart',
    initialQuestions: ['Question 1: What is OOP?', 'Question 2: What is Design Pattern?'],
    interviewDomain: 'IT',
    targetJobTitle: 'Software Engineer',
    language: 'en',
  };

  await joinInterview(io, socket, data);

  // Advance state manually: add a turn and increment baseQuestionIndex
  const { updateSession, appendTurn } = await import('../src/modules/interview/session.service.js');
  await appendTurn('interview-restart-test', {
    question: 'Question 1: What is OOP?',
    answer: 'OOP is object oriented programming.',
    score: 8,
    evaluation: 'Good answer',
  });
  await updateSession('interview-restart-test', {
    questionState: {
      baseQuestionIndex: 1,
      currentFollowUpDepth: 2,
      maxFollowUpDepth: 3,
      currentFollowUpQuestion: 'Tell me more about polymorphism',
      isTransitioning: false,
    },
    status: 'IN_PROGRESS',
  });

  // Verify state advanced
  const { getSession } = await import('../src/modules/interview/session.service.js');
  let sessionBefore = await getSession('interview-restart-test');
  assert.strictEqual(sessionBefore.questionState.baseQuestionIndex, 1);
  assert.strictEqual(sessionBefore.turns.length, 1);

  // Send RESTART_INTERVIEW event
  await handleOrchestrationEvent(io, socket, {
    type: 'RESTART_INTERVIEW',
    payload: { interviewId: 'interview-restart-test' },
  });

  // Verify session is reset in Redis
  let sessionAfter = await getSession('interview-restart-test');
  assert.strictEqual(sessionAfter.questionState.baseQuestionIndex, 0);
  assert.strictEqual(sessionAfter.questionState.currentFollowUpDepth, 0);
  assert.strictEqual(sessionAfter.turns.length, 0);
  assert.strictEqual(sessionAfter.conversationThread.length, 0);

  // Verify INTERVIEWER_ACTION was broadcast for warmup greeting
  const actions = io.broadcasts.filter(
    b => b.room === 'interview-restart-test' && b.event === 'orchestration-event' && b.data?.type === 'INTERVIEWER_ACTION'
  );
  assert.ok(actions.length >= 2); // Initial start + restart
  const latestAction = actions[actions.length - 1];
  assert.ok(latestAction.data.payload.text.includes('break the ice') || latestAction.data.payload.text.includes('introduce yourself'));
});

test('Socket: joinInterview with restart: true resets existing session', async () => {
  const io = createMockIo();
  const socket = createMockSocket('socket-force-restart');

  const { appendTurn, updateSession, getSession } = await import('../src/modules/interview/session.service.js');

  // Setup dirty session
  const data = {
    interviewId: 'interview-join-restart',
    userId: 'user-candidate-2',
    initialQuestions: ['First topic question', 'Second topic question'],
    interviewDomain: 'IT',
    targetJobTitle: 'Backend Dev',
    language: 'vi',
  };
  await joinInterview(io, socket, data);
  await appendTurn('interview-join-restart', {
    question: 'First topic question',
    answer: 'Some answer',
    score: 5,
  });
  await updateSession('interview-join-restart', {
    questionState: { baseQuestionIndex: 1, currentFollowUpDepth: 1, maxFollowUpDepth: 3 },
  });

  // Re-join with restart: true
  const restartSocket = createMockSocket('socket-force-restart-2');
  await joinInterview(io, restartSocket, {
    ...data,
    restart: true,
  });

  const session = await getSession('interview-join-restart');
  assert.strictEqual(session.questionState.baseQuestionIndex, 0);
  assert.strictEqual(session.turns.length, 0);
});

test('Socket: joinInterview on IN_PROGRESS session emits current active question to resuming client', async () => {
  const io = createMockIo();
  const socket1 = createMockSocket('socket-resume-orig');

  const { updateSession } = await import('../src/modules/interview/session.service.js');

  const data = {
    interviewId: 'interview-resume-active-q',
    userId: 'user-candidate-resume',
    initialQuestions: ['Question 1: Intro', 'Question 2: Concurrency in Node.js'],
    interviewDomain: 'IT',
    targetJobTitle: 'Node.js Developer',
    language: 'vi',
  };

  // Join to initialize
  await joinInterview(io, socket1, data);

  // Set session to IN_PROGRESS at question index 1 (Question 2)
  await updateSession('interview-resume-active-q', {
    status: 'IN_PROGRESS',
    questionState: {
      isWarmup: false,
      baseQuestionIndex: 1,
      currentFollowUpDepth: 0,
      maxFollowUpDepth: 3,
      currentFollowUpQuestion: '',
    },
  });

  // Reconnecting socket (e.g. page refresh / resume)
  const socket2 = createMockSocket('socket-resume-reconnected');
  await joinInterview(io, socket2, data);

  // Socket 2 should receive INTERVIEWER_ACTION with Question 2
  const resumeAction = socket2.emitted.find(
    e => e.event === 'orchestration-event' && e.data?.type === 'INTERVIEWER_ACTION'
  );
  assert.ok(resumeAction, 'Must emit INTERVIEWER_ACTION on resume');
  assert.ok(resumeAction.data.payload.text.includes('Question 2: Concurrency in Node.js'));
});

test('Socket: Candidate answering warmup turn receives Question 1 transition without scoring penalty', async () => {
  const io = createMockIo();
  const socket = createMockSocket('socket-warmup-candidate');

  const data = {
    interviewId: 'interview-warmup-flow-test',
    userId: 'user-warmup-candidate',
    candidateName: 'Trần Văn Bình',
    candidateAge: 25,
    initialQuestions: ['Explain the difference between SQL and NoSQL databases.'],
    interviewDomain: 'IT',
    targetJobTitle: 'Database Administrator',
    language: 'vi',
  };

  // 1. Join interview (starts at warmup turn)
  await joinInterview(io, socket, data);

  const initialAction = io.broadcasts.find(
    b => b.room === 'interview-warmup-flow-test' && b.event === 'orchestration-event' && b.data?.type === 'INTERVIEWER_ACTION'
  );
  assert.ok(initialAction);
  assert.ok(initialAction.data.payload.text.includes('em Bình'));
  assert.ok(initialAction.data.payload.text.includes('khởi động'));

  // 2. Candidate submits response to warmup
  await handleOrchestrationEvent(io, socket, {
    type: 'CANDIDATE_TEXT_SUBMIT',
    payload: {
      text: 'Chào bạn, mình tên Bình, 25 tuổi, có 3 năm kinh nghiệm quản trị cơ sở dữ liệu PostgreSQL và MongoDB.',
    },
  });

  // 3. Verify AI acknowledges warmup and presents Question 1
  const actions = io.broadcasts.filter(
    b => b.room === 'interview-warmup-flow-test' && b.event === 'orchestration-event' && b.data?.type === 'INTERVIEWER_ACTION'
  );
  assert.strictEqual(actions.length, 2);
  const q1Action = actions[1];
  assert.ok(q1Action.data.payload.text.includes('Cảm ơn phần giới thiệu'));
  assert.ok(q1Action.data.payload.text.includes('Explain the difference between SQL and NoSQL databases.'));

  // 4. Verify turn is recorded as excludedFromScoring: true
  const { getSession } = await import('../src/modules/interview/session.service.js');
  const session = await getSession('interview-warmup-flow-test');
  assert.strictEqual(session.turns.length, 1);
  assert.strictEqual(session.turns[0].excludedFromScoring, true);
  assert.strictEqual(session.questionState.isWarmup, false);
  assert.strictEqual(session.questionState.baseQuestionIndex, 0);
});
