import redisClient from '../../config/redis.js';
import { transcribeAudio } from '../audio/audio.service.js';
import { synthesizeSpeech } from '../tts/tts.service.js';
import {
  createSession,
  getSession,
  updateSession,
  appendTurn,
  appendToConversationThread,
  resetConversationThread,
} from './session.service.js';
import { evaluateCandidateResponse, generateFinalReport } from './engine.client.js';
import { generateAvatarAction } from './mockAvatar.service.js';

/**
 * Saves socket metadata mapping in Redis.
 */
const saveSocketSession = async (socketId, interviewId, userId) => {
  await redisClient.hSet(`socket:${socketId}`, {
    interviewId,
    userId,
    joinedAt: new Date().toISOString(),
  });
};

/**
 * Adds a user to the set of participants in Redis.
 */
const addParticipantToSession = async (interviewId, userId) => {
  await redisClient.sAdd(`interview:${interviewId}:participants`, userId);
};

/**
 * Fetches the active interview session, creating it if it doesn't exist.
 */
const getOrCreateSession = async (interviewId, userId, initialQuestions, baseQuestionIndex, data) => {
  let session = await getSession(interviewId);
  console.log(`[Signaling] Fetched existing session from Redis:`, session ? 'Found' : 'Null');
  if (!session) {
    console.log(`[Signaling] Creating new session in Redis with initialQuestions:`, initialQuestions);
    session = await createSession(interviewId, userId, initialQuestions, baseQuestionIndex, {
      interviewDomain: data.interviewDomain || 'IT',
      targetJobTitle: data.targetJobTitle || 'IT Engineer',
      resumeText: data.resumeText || '',
      jdText: data.jdText || '',
    });
  }
  return session;
};

/**
 * Sends a STATE_UPDATE payload to the client.
 */
const emitStateUpdate = (target, session) => {
  target.emit('orchestration-event', {
    type: 'STATE_UPDATE',
    payload: {
      status: session.status,
      questionState: session.questionState,
    },
  });
  console.log(`[Signaling] Emitted STATE_UPDATE to client`);
};

/**
 * Triggers the start of the interview by broadcasting the first question.
 */
const startFirstQuestion = async (io, interviewId, session) => {
  const firstQuestionObj = session.questions[session.questionState?.baseQuestionIndex || 0];
  const firstQuestion = typeof firstQuestionObj === 'object' && firstQuestionObj !== null
    ? firstQuestionObj.question
    : firstQuestionObj;

  console.log(`[Signaling] Session INIT. Broadcasting first question: "${firstQuestion}"`);
  const avatarAction = await generateAvatarAction(firstQuestion, 'NEUTRAL');

  await updateSession(interviewId, { status: 'IN_PROGRESS' });
  console.log(`[Signaling] Updated Redis session to IN_PROGRESS`);

  io.to(interviewId).emit('orchestration-event', {
    type: 'INTERVIEWER_ACTION',
    payload: {
      actionId: `action-${Date.now()}`,
      actionType: 'TRANSITION',
      text: firstQuestion,
      reasoning: 'Starting the interview.',
      score: null,
      evaluation: '',
      isFallback: false,
      audioUrl: null,
      avatarTriggers: avatarAction,
    },
  });
  console.log(`[Signaling] Emitted INTERVIEWER_ACTION to room ${interviewId}`);
};

/**
 * Joins an interview session room, registers metadata, and initializes state.
 */
export const joinInterview = async (io, socket, data) => {
  const { interviewId, userId, initialQuestions, baseQuestionIndex = 0 } = data;
  if (!interviewId || !userId) {
    socket.emit('error', { message: 'interviewId and userId are required' });
    return;
  }

  console.log(`User ${userId} joined interview ${interviewId} on socket ${socket.id}, baseIndex: ${baseQuestionIndex}`);

  await saveSocketSession(socket.id, interviewId, userId);
  await addParticipantToSession(interviewId, userId);
  
  socket.join(interviewId);
  console.log(`[Signaling] Socket ${socket.id} joined room ${interviewId}`);

  const session = await getOrCreateSession(interviewId, userId, initialQuestions, baseQuestionIndex, data);
  console.log(`[Signaling] Session status: ${session?.status}, questions: ${session?.questions?.length}`);

  socket.to(interviewId).emit('peer-joined', { userId, socketId: socket.id });
  socket.emit('joined-room', { interviewId, userId });

  emitStateUpdate(socket, session);

  if (session.status === 'INIT' && session.questions.length > 0) {
    await startFirstQuestion(io, interviewId, session);
  }
};

/**
 * Handles fast evaluation synchronously.
 */
const runFastEvaluation = async (sessionId, session, currentQuestion, candidateText, qState, cvText, limitReached) => {
  if (limitReached) {
    console.log(`[Signaling] Limit reached. Bypassing synchronous LLM evaluation.`);
    return {
      decision: 'NEXT_TOPIC',
      followUpQuestion: '',
      reasoning: 'Bypassed LLM call: reached maximum follow-up depth.',
      score: null,
      evaluation: '',
      isFallback: false,
      excludedFromScoring: false,
    };
  }

  console.log(`[Signaling] Calling fast evaluation synchronously...`);
  try {
    return await evaluateCandidateResponse({
      sessionId,
      targetJobTitle: session.targetJobTitle || 'IT Engineer',
      interviewDomain: session.interviewDomain || 'IT',
      currentQuestion,
      candidateAnswer: candidateText,
      currentFollowUpCount: qState.currentFollowUpDepth,
      maxFollowUpCount: qState.maxFollowUpDepth || 3,
      conversationThread: session.conversationThread || [],
      fastMode: true,
      cvText,
    });
  } catch (error) {
    console.error('[Signaling] Fast evaluation failed. Using fallback.', error);
    return {
      decision: 'NEXT_TOPIC',
      followUpQuestion: '',
      reasoning: 'Fast evaluation failed, falling back to NEXT_TOPIC.',
      score: null,
      evaluation: '',
      isFallback: true,
      excludedFromScoring: true,
    };
  }
};

/**
 * Updates an existing turn record with background slow evaluation metrics.
 */
const updateTurnWithSlowEvaluation = async (sessionId, currentQuestion, candidateText, slowRes) => {
  const sess = await getSession(sessionId);
  if (!sess) return;

  const turns = sess.turns || [];
  let updated = false;
  for (let i = turns.length - 1; i >= 0; i--) {
    if (turns[i].question === currentQuestion && turns[i].answer === candidateText) {
      turns[i].score = slowRes.score;
      turns[i].evaluation = slowRes.evaluation || '';
      turns[i].excludedFromScoring = slowRes.excludedFromScoring;
      updated = true;
      break;
    }
  }

  if (updated) {
    await redisClient.hSet(`session:${sessionId}`, {
      turns: JSON.stringify(turns),
      updatedAt: new Date().toISOString(),
    });
    console.log(`[Background Eval] Successfully updated Redis turns with score.`);
  }
};

/**
 * Triggers background slow/detailed LLM evaluation asynchronously.
 */
const triggerSlowEvaluation = (sessionId, session, currentQuestion, candidateText, qState, cvText, goodAnswerSignals) => {
  const slowEvalParams = {
    sessionId,
    targetJobTitle: session.targetJobTitle || 'IT Engineer',
    interviewDomain: session.interviewDomain || 'IT',
    currentQuestion,
    candidateAnswer: candidateText,
    currentFollowUpCount: qState.currentFollowUpDepth,
    maxFollowUpCount: qState.maxFollowUpDepth || 3,
    conversationThread: session.conversationThread || [],
    fastMode: false,
    cvText,
    goodAnswerSignals,
  };

  (async () => {
    console.log(`[Background Eval] Starting detailed evaluation in background...`);
    try {
      const slowRes = await evaluateCandidateResponse(slowEvalParams);
      console.log(`[Background Eval] Finished for session ${sessionId}. Score: ${slowRes.score}`);
      await updateTurnWithSlowEvaluation(sessionId, currentQuestion, candidateText, slowRes);
    } catch (e) {
      console.error(`[Background Eval] Detailed evaluation failed in background:`, e);
    }
  })();
};

/**
 * Transitions the session state to the next base topic.
 */
const transitionToNextTopic = async (sessionId, session, qState) => {
  const nextQState = { ...qState };
  nextQState.baseQuestionIndex += 1;
  nextQState.currentFollowUpDepth = 0;
  await resetConversationThread(sessionId);

  let nextQuestionText = '';
  let actionType = '';

  if (nextQState.baseQuestionIndex < session.questions.length) {
    const nextObj = session.questions[nextQState.baseQuestionIndex];
    nextQuestionText = typeof nextObj === 'object' && nextObj !== null ? nextObj.question : nextObj;
    actionType = 'TRANSITION';
  } else {
    nextQuestionText = 'Thank you. That concludes our technical questions.';
    actionType = 'CONCLUDING';
  }

  return { nextQuestionText, actionType, nextQState };
};

/**
 * Decides whether to follow up or transition to the next topic.
 */
const determineNextQuestion = async (sessionId, session, qState, engineResponse) => {
  let nextQuestionText = '';
  let actionType = engineResponse.decision;
  let nextQState = { ...qState };

  if (actionType === 'FOLLOW_UP' && !engineResponse.isFallback) {
    nextQuestionText = engineResponse.followUpQuestion || '';
    nextQState.currentFollowUpDepth += 1;
    console.log(`[Signaling] AI follow-up: "${nextQuestionText}" (depth: ${nextQState.currentFollowUpDepth})`);

    if (!nextQuestionText.trim()) {
      console.warn('[Signaling] AI returned FOLLOW_UP but followUpQuestion is empty. Transitioning.');
      return await transitionToNextTopic(sessionId, session, nextQState);
    }
  } else {
    return await transitionToNextTopic(sessionId, session, nextQState);
  }

  return { nextQuestionText, actionType, nextQState };
};

/**
 * Generates avatar triggers and broadcasts the INTERVIEWER_ACTION event.
 */
const broadcastInterviewerAction = async (io, sessionId, nextQuestionText, actionType, reasoning, isFallback) => {
  const emotionHint = 'CURIOUS';
  const avatarAction = await generateAvatarAction(nextQuestionText, emotionHint);

  io.to(sessionId).emit('orchestration-event', {
    type: 'INTERVIEWER_ACTION',
    payload: {
      actionId: `action-${Date.now()}`,
      actionType,
      text: nextQuestionText,
      reasoning,
      score: null,
      evaluation: '',
      isFallback,
      audioUrl: null,
      avatarTriggers: avatarAction,
    },
  });
};

/**
 * Orchestrates candidate text submission processing.
 */
const handleCandidateTextSubmit = async (io, sessionId, session, candidateText) => {
  const qState = session.questionState;
  const currentQuestionObj = session.questions[qState.baseQuestionIndex];
  const currentQuestion = typeof currentQuestionObj === 'object' && currentQuestionObj !== null
    ? currentQuestionObj.question
    : currentQuestionObj;

  const goodAnswerSignals = currentQuestionObj?.good_answer_signals || [];
  const cvText = session.resumeText || '';
  const limitReached = qState.currentFollowUpDepth >= (qState.maxFollowUpDepth || 3);

  const engineResponse = await runFastEvaluation(sessionId, session, currentQuestion, candidateText, qState, cvText, limitReached);
  console.log(`[Signaling] Fast decision: ${engineResponse.decision}, reasoning: ${engineResponse.reasoning}`);

  await appendToConversationThread(sessionId, {
    question: currentQuestion,
    answer: candidateText,
    wasFollowUp: qState.currentFollowUpDepth > 0,
  });

  await appendTurn(sessionId, {
    question: currentQuestion,
    answer: candidateText,
    score: null,
    evaluation: '',
    wasFollowUp: qState.currentFollowUpDepth > 0,
    excludedFromScoring: engineResponse.excludedFromScoring,
  });

  triggerSlowEvaluation(sessionId, session, currentQuestion, candidateText, qState, cvText, goodAnswerSignals);

  const { nextQuestionText, actionType, nextQState } = await determineNextQuestion(sessionId, session, qState, engineResponse);

  const updatedSession = await updateSession(sessionId, {
    questionState: nextQState,
    status: actionType === 'CONCLUDING' ? 'COMPLETED' : 'IN_PROGRESS',
  });

  emitStateUpdate(io.to(sessionId), updatedSession);
  await broadcastInterviewerAction(io, sessionId, nextQuestionText, actionType, engineResponse.reasoning, engineResponse.isFallback);
};

/**
 * Handles generating final report and updating interview session.
 */
const handleInterviewEnd = async (io, sessionId, session) => {
  console.log(`[Signaling] INTERVIEW_END received for session ${sessionId}`);
  try {
    const scoredTurns = (session.turns || []).filter(t => !t.excludedFromScoring);
    console.log(`[Signaling] Generating final report. Scored turns: ${scoredTurns.length}`);

    const finalReport = await generateFinalReport({
      sessionId,
      targetJobTitle: session.targetJobTitle || 'IT Engineer',
      turns: scoredTurns,
      resumeText: session.resumeText || '',
      jdText: session.jdText || '',
    });

    await updateSession(sessionId, { status: 'REPORT_READY' });

    io.to(sessionId).emit('orchestration-event', {
      type: 'FINAL_REPORT',
      payload: finalReport,
    });

    console.log(`[Signaling] Final report emitted. Hiring recommendation: ${finalReport.hiringRecommendation}`);
  } catch (reportError) {
    console.error('[Signaling] Failed to generate final report:', reportError);
    io.to(sessionId).emit('orchestration-event', {
      type: 'FINAL_REPORT_ERROR',
      payload: { message: 'Failed to generate final report. Please try again.' },
    });
  }
};

/**
 * Entrance handler for all orchestration socket events.
 */
export const handleOrchestrationEvent = async (io, socket, data) => {
  const socketInfo = await redisClient.hGetAll(`socket:${socket.id}`);
  if (!socketInfo || !socketInfo.interviewId) {
    socket.emit('error', { message: 'Not joined in any session' });
    return;
  }

  const sessionId = socketInfo.interviewId;
  const userId = socketInfo.userId;

  const session = await getSession(sessionId);
  if (!session) {
    socket.emit('error', { message: 'Session not found' });
    return;
  }

  // IDOR Protection: Ensure user is authorized to modify/submit data for this session
  if (session.candidateId !== userId) {
    console.warn(`[Security Alert] Socket user ${userId} attempted unauthorized session access for session: ${sessionId}`);
    socket.emit('error', { message: 'Access denied: unauthorized session modification' });
    return;
  }

  if (data.type === 'CANDIDATE_TEXT_SUBMIT') {
    await handleCandidateTextSubmit(io, sessionId, session, data.payload?.text);
  } else if (data.type === 'INTERVIEW_END') {
    await handleInterviewEnd(io, sessionId, session);
  }
};

/**
 * Forwards RTC signaling payload to peer socket or to session room.
 */
export const handleSignal = async (io, socket, data) => {
  const { targetSocketId, signal } = data;
  const senderInfo = await redisClient.hGetAll(`socket:${socket.id}`);
  if (!senderInfo || !senderInfo.userId) return;

  const payload = {
    senderSocketId: socket.id,
    senderUserId: senderInfo.userId,
    signal,
  };

  if (targetSocketId) {
    io.to(targetSocketId).emit('signal', payload);
  } else if (senderInfo.interviewId) {
    socket.to(senderInfo.interviewId).emit('signal', payload);
  }
};

/**
 * Distributes streaming audio chunk from client to all other room members.
 */
export const handleAudioChunk = async (io, socket, data) => {
  const { chunk } = data;
  const socketInfo = await redisClient.hGetAll(`socket:${socket.id}`);
  if (!socketInfo || !socketInfo.interviewId) return;

  socket.to(socketInfo.interviewId).emit('audio-chunk', {
    userId: socketInfo.userId,
    chunk,
    timestamp: Date.now(),
  });
};

/**
 * Triggers speech-to-text translation and emits result back to requester socket.
 */
export const processStt = async (socket, audioBuffer) => {
  const mockFile = { buffer: audioBuffer, originalname: 'stream.webm', mimetype: 'audio/webm' };
  const resultText = await transcribeAudio(mockFile.buffer, mockFile.originalname);
  socket.emit('stt-result', { status: 'success', text: resultText });
};

/**
 * Synthesizes text to speech MP3 stream and emits back to requester socket.
 */
export const processTts = async (socket, text) => {
  const audioArrayBuffer = await synthesizeSpeech(text);
  socket.emit('tts-result', Buffer.from(audioArrayBuffer));
};

/**
 * Cleans up user metadata maps and participants arrays on disconnect.
 */
export const handleDisconnect = async (io, socket) => {
  console.log(`Client disconnected: ${socket.id}`);
  const socketInfo = await redisClient.hGetAll(`socket:${socket.id}`);
  if (socketInfo && socketInfo.interviewId && socketInfo.userId) {
    const { interviewId, userId } = socketInfo;
    await redisClient.sRem(`interview:${interviewId}:participants`, userId);
    socket.to(interviewId).emit('peer-left', { userId, socketId: socket.id });
  }
  await redisClient.del(`socket:${socket.id}`);
};
