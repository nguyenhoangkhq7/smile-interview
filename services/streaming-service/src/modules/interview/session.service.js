import redisClient from '../../config/redis.js';

/**
 * Initializes a new interview session state in Redis.
 * Assumes the Question Bank has been generated and cached by ai-inference-service.
 */
export const createSession = async (sessionId, candidateId, initialQuestions = null, baseQuestionIndex = 0) => {
  // Try to fetch pre-generated questions from Redis (created by ai-inference-service)
  // If not found, use a fallback list for the IT domain, or the provided initialQuestions
  let cachedQuestions = await redisClient.get(`interview:${sessionId}:questions`);
  let questionsList = cachedQuestions ? JSON.parse(cachedQuestions) : (initialQuestions && initialQuestions.length > 0 ? initialQuestions : [
    "Could you walk me through your experience with microservices architecture?",
    "How do you handle database scaling for high-traffic applications?",
    "Can you describe a challenging bug you fixed recently?"
  ]);

  const sessionData = {
    sessionId,
    candidateId,
    status: 'INIT',
    currentTopicId: 'topic-0',
    questions: JSON.stringify(questionsList),
    questionState: JSON.stringify({
      baseQuestionIndex: baseQuestionIndex,
      currentFollowUpDepth: 0,
      maxFollowUpDepth: 3,
      isTransitioning: false
    }),
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
  
  // Parse JSON fields back to objects
  return {
    ...session,
    questions: session.questions ? JSON.parse(session.questions) : [],
    questionState: session.questionState ? JSON.parse(session.questionState) : null,
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

  // Convert nested objects back to JSON strings for Redis hash storage
  const redisPayload = {
    ...newSessionData,
    questions: JSON.stringify(newSessionData.questions),
    questionState: JSON.stringify(newSessionData.questionState),
    metrics: JSON.stringify(newSessionData.metrics)
  };

  await redisClient.hSet(`session:${sessionId}`, redisPayload);
  return newSessionData;
};
