import redisClient from '../../config/redis.js';

/**
 * Initializes a new interview session state in Redis.
 */
export const createSession = async (
  sessionId,
  candidateId,
  initialQuestions = null,
  baseQuestionIndex = 0,
  options = {}
) => {
  let cachedQuestions = await redisClient.get(`interview:${sessionId}:questions`);
  let questionsList = cachedQuestions
    ? JSON.parse(cachedQuestions)
    : initialQuestions && initialQuestions.length > 0
    ? initialQuestions
    : [
        'Could you walk me through your experience with microservices architecture?',
        'How do you handle database scaling for high-traffic applications?',
        'Can you describe a challenging bug you fixed recently?'
      ];

  const sessionData = {
    sessionId,
    candidateId,
    status: 'INIT',
    currentTopicId: 'topic-0',
    // Interview domain for AI prompt (e.g. "IT", "Marketing")
    interviewDomain: options.interviewDomain || 'IT',
    targetJobTitle: options.targetJobTitle || 'IT Engineer',
    // Resume and JD full text for Final Synthesis
    resumeText: options.resumeText || '',
    jdText: options.jdText || '',
    questions: JSON.stringify(questionsList),
    questionState: JSON.stringify({
      baseQuestionIndex,
      currentFollowUpDepth: 0,
      maxFollowUpDepth: 3,
      isTransitioning: false
    }),
    // Current topic's conversation thread (resets on NEXT_TOPIC)
    conversationThread: JSON.stringify([]),
    // All scored turns across the full interview (for Final Synthesis)
    turns: JSON.stringify([]),
    metrics: JSON.stringify({
      technicalScoreEstimate: 0,
      communicationScoreEstimate: 0
    }),
    updatedAt: new Date().toISOString()
  };

  await redisClient.hSet(`session:${sessionId}`, sessionData);
  return await getSession(sessionId);
};

/**
 * Retrieves the current session state from Redis.
 */
export const getSession = async (sessionId) => {
  const session = await redisClient.hGetAll(`session:${sessionId}`);
  if (!session || Object.keys(session).length === 0) {
    return null;
  }

  return {
    ...session,
    questions: session.questions ? JSON.parse(session.questions) : [],
    questionState: session.questionState ? JSON.parse(session.questionState) : null,
    conversationThread: session.conversationThread ? JSON.parse(session.conversationThread) : [],
    turns: session.turns ? JSON.parse(session.turns) : [],
    metrics: session.metrics ? JSON.parse(session.metrics) : null
  };
};

/**
 * Updates an existing interview session state.
 */
export const updateSession = async (sessionId, updates) => {
  const existing = await getSession(sessionId);
  if (!existing) {
    throw new Error(`Session ${sessionId} not found`);
  }

  const newSessionData = {
    ...existing,
    ...updates,
    updatedAt: new Date().toISOString()
  };

  const redisPayload = {
    ...newSessionData,
    questions: JSON.stringify(newSessionData.questions),
    questionState: JSON.stringify(newSessionData.questionState),
    conversationThread: JSON.stringify(newSessionData.conversationThread),
    turns: JSON.stringify(newSessionData.turns),
    metrics: JSON.stringify(newSessionData.metrics)
  };

  await redisClient.hSet(`session:${sessionId}`, redisPayload);
  return newSessionData;
};

/**
 * Appends a completed turn record to the session's turns list.
 * Used to build the transcript for GenerateFinalReport.
 *
 * @param {string} sessionId
 * @param {{ question, answer, score, evaluation, wasFollowUp, excludedFromScoring }} turnRecord
 */
export const appendTurn = async (sessionId, turnRecord) => {
  const session = await getSession(sessionId);
  if (!session) throw new Error(`Session ${sessionId} not found`);

  const updatedTurns = [...(session.turns || []), turnRecord];
  await redisClient.hSet(`session:${sessionId}`, {
    turns: JSON.stringify(updatedTurns),
    updatedAt: new Date().toISOString()
  });
};

/**
 * Appends a QA pair to the current topic's conversation thread.
 * Called after each turn, before potentially resetting when moving to a new topic.
 *
 * @param {string} sessionId
 * @param {{ question: string, answer: string, wasFollowUp: boolean }} qaContext
 */
export const appendToConversationThread = async (sessionId, qaContext) => {
  const session = await getSession(sessionId);
  if (!session) throw new Error(`Session ${sessionId} not found`);

  const updatedThread = [
    ...(session.conversationThread || []),
    {
      question: qaContext.question,
      answer: qaContext.answer,
      wasFollowUp: qaContext.wasFollowUp || false
    }
  ];

  await redisClient.hSet(`session:${sessionId}`, {
    conversationThread: JSON.stringify(updatedThread),
    updatedAt: new Date().toISOString()
  });
};

/**
 * Resets the conversation thread for the current topic.
 * Called when transitioning to a new base question (NEXT_TOPIC).
 *
 * @param {string} sessionId
 */
export const resetConversationThread = async (sessionId) => {
  await redisClient.hSet(`session:${sessionId}`, {
    conversationThread: JSON.stringify([]),
    updatedAt: new Date().toISOString()
  });
};
