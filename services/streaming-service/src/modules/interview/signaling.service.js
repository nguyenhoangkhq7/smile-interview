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
  restartSession,
} from './session.service.js';
import { evaluateCandidateResponse, generateFinalReport } from './engine.client.js';
import { generateAvatarAction } from './mockAvatar.service.js';

/**
 * Detects whether the text is predominantly Vietnamese or English.
 */
export const detectLanguage = (text, defaultLang = 'vi') => {
  if (!text || typeof text !== 'string') return defaultLang;
  // Vietnamese diacritics regex
  const viPattern = /[àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ]/i;
  if (viPattern.test(text)) return 'vi';
  
  // Common Vietnamese words without diacritics
  const viWords = /\b(ban|cua|cho|voi|trong|hay|nhu|the nao|kinh nghiem|phong van|chuc mung)\b/i;
  if (viWords.test(text)) return 'vi';

  return 'en';
};

/**
 * Determines natural pronouns & addressing forms based on candidate's name and age/year of birth.
 * AI Interviewer acts as Senior Interviewer / Tech Lead (~30-35 years old).
 */
export const getHonorific = (name, age, yearOfBirth, lang = 'vi') => {
  const cleanName = (name || '').trim();
  const displayName = cleanName ? (cleanName.includes(' ') ? cleanName.split(' ').pop() : cleanName) : '';

  if (lang === 'en') {
    return {
      pronoun: cleanName || 'you',
      address: cleanName ? `${cleanName}` : 'there',
      fullName: cleanName,
      displayName: displayName || cleanName || 'there',
    };
  }

  let calculatedAge = Number(age) || 0;
  if (!calculatedAge && yearOfBirth) {
    const currentYear = new Date().getFullYear();
    calculatedAge = currentYear - Number(yearOfBirth);
  }

  let pronoun = 'bạn';
  if (calculatedAge > 0) {
    if (calculatedAge < 27) {
      pronoun = 'em';
    } else if (calculatedAge > 35) {
      pronoun = 'anh/chị';
    }
  }

  const address = displayName ? `${pronoun} ${displayName}` : pronoun;

  return {
    pronoun,
    address,
    fullName: cleanName,
    displayName: displayName || pronoun,
  };
};

/**
 * Heuristically extracts candidate name and birth year from CV / Resume text if not provided directly.
 */
export const extractCandidateInfoFromResume = (resumeText) => {
  if (!resumeText || typeof resumeText !== 'string') return {};
  const info = {};

  const nameMatch = resumeText.match(/(?:Họ\s*(?:và|&)?\s*tên|Full\s*Name|Candidate\s*Name)\s*[:：]\s*([^\r\n,]+)/i);
  if (nameMatch && nameMatch[1]) {
    info.name = nameMatch[1].trim();
  }

  const yobMatch = resumeText.match(/(?:Năm\s*sinh|DOB|Date\s*of\s*birth|Sinh\s*năm|Year\s*of\s*birth)\s*[:：]\s*(\d{4})/i)
                || resumeText.match(/\b(19\d{2}|200\d)\b/);
  if (yobMatch && yobMatch[1]) {
    const yob = parseInt(yobMatch[1], 10);
    const currentYear = new Date().getFullYear();
    if (yob >= 1960 && yob <= currentYear - 16) {
      info.yearOfBirth = yob;
      info.age = currentYear - yob;
    }
  }
  return info;
};

const DIALOGUE_TEMPLATES = {
  vi: {
    greeting: (jobTitle, _firstQuestion, candidateInfo = {}) => {
      const { address, pronoun } = getHonorific(
        candidateInfo.candidateName, candidateInfo.candidateAge, candidateInfo.candidateYearOfBirth, 'vi'
      );
      const nameGreeting = candidateInfo.candidateName ? ` ${address}` : ' bạn';
      return `Xin chào${nameGreeting}! Rất vui được gặp ${address} trong buổi phỏng vấn vị trí **${jobTitle}** hôm nay. Mình là người phỏng vấn AI đồng hành cùng ${pronoun}.\n\nTrước khi bắt đầu các câu hỏi chuyên sâu, ${address} hãy giữ tâm lý thật thoải mái và tự tin nhé! Để cùng làm quen và khởi động buổi trao đổi, ${address} có thể giới thiệu đôi nét về bản thân cũng như chia sẻ về một dự án hoặc công nghệ gần đây mà ${pronoun} tâm đắc nhất được không?`;
    },
    warmupAcknowledgement: (jobTitle, firstQuestion, candidateInfo = {}) => {
      const { address, pronoun } = getHonorific(
        candidateInfo.candidateName, candidateInfo.candidateAge, candidateInfo.candidateYearOfBirth, 'vi'
      );
      return `Cảm ơn phần giới thiệu rất tự tin và cởi mở của ${address}! Rất vui được hiểu thêm về định hướng và kinh nghiệm của ${pronoun}.\n\nBây giờ, chúng ta sẽ chính thức bước vào câu hỏi chuyên môn đầu tiên nhé:\n\n👉 ${firstQuestion}`;
    },
    transitions: (candidateInfo = {}, lang = 'vi') => {
      const { address, pronoun } = getHonorific(
        candidateInfo.candidateName, candidateInfo.candidateAge, candidateInfo.candidateYearOfBirth, 'vi'
      );
      return [
        `Cảm ơn phần chia sẻ của ${address} về chủ đề vừa rồi. Tiếp theo, chúng ta cùng trao đổi về một khía cạnh khác nhé:`,
        `Mình đã ghi nhận câu trả lời của ${address}. Bây giờ ${pronoun} hãy cùng thảo luận về tình huống tiếp theo:`,
        `Rất tốt! Chúng ta sẽ chuyển sang một nội dung chuyên môn tiếp theo:`,
        `Cảm ơn ${address}. Tiếp theo, mình muốn lắng nghe thêm góc nhìn của ${pronoun} về câu hỏi sau:`,
      ];
    },
    concluding: (candidateInfo = {}, lang = 'vi') => {
      const { address } = getHonorific(
        candidateInfo.candidateName, candidateInfo.candidateAge, candidateInfo.candidateYearOfBirth, 'vi'
      );
      const capAddress = address.charAt(0).toUpperCase() + address.slice(1);
      return `Cảm ơn ${address} rất nhiều! Đó là tất cả các câu hỏi cho buổi phỏng vấn hôm nay. ${capAddress} đã chia sẻ rất nhiệt tình và chi tiết về kinh nghiệm của mình. Hệ thống đang tiến hành tổng hợp báo cáo đánh giá. Chúc ${address} một ngày làm việc thật vui vẻ và thành công!`;
    },
  },
  en: {
    greeting: (jobTitle, _firstQuestion, candidateInfo = {}) => {
      const { displayName } = getHonorific(
        candidateInfo.candidateName, candidateInfo.candidateAge, candidateInfo.candidateYearOfBirth, 'en'
      );
      const nameGreeting = displayName && displayName !== 'there' ? ` ${displayName}` : '';
      return `Hello${nameGreeting}! Welcome to the interview session for the **${jobTitle}** position today. I am your AI interviewer.\n\nBefore we dive into technical topics, please take a deep breath and feel completely at ease. To kick things off and break the ice, could you briefly introduce yourself and share a bit about a recent project or technology you've enjoyed working with?`;
    },
    warmupAcknowledgement: (jobTitle, firstQuestion, candidateInfo = {}) => {
      const { displayName } = getHonorific(
        candidateInfo.candidateName, candidateInfo.candidateAge, candidateInfo.candidateYearOfBirth, 'en'
      );
      const nameSuffix = displayName && displayName !== 'there' ? `, ${displayName}` : '';
      return `Thank you for the wonderful introduction${nameSuffix}! It is great learning about your background and experience.\n\nNow, let's officially dive into our first technical topic:\n\n👉 ${firstQuestion}`;
    },
    transitions: (candidateInfo = {}, lang = 'en') => {
      const { displayName } = getHonorific(
        candidateInfo.candidateName, candidateInfo.candidateAge, candidateInfo.candidateYearOfBirth, 'en'
      );
      const nameSuffix = displayName && displayName !== 'there' ? `, ${displayName}` : '';
      return [
        `Thank you for sharing your thoughts${nameSuffix}. Let's move on to our next topic:`,
        `Got it, thank you. Now let's explore another interesting scenario:`,
        `Great perspective! Let's proceed to the next technical area:`,
        `Thanks for your explanation. Next, I'd love to hear your insights on this:`,
      ];
    },
    concluding: (candidateInfo = {}, lang = 'en') => {
      const { displayName } = getHonorific(
        candidateInfo.candidateName, candidateInfo.candidateAge, candidateInfo.candidateYearOfBirth, 'en'
      );
      const nameSuffix = displayName && displayName !== 'there' ? ` ${displayName}` : '';
      return `Thank you very much${nameSuffix}! That concludes our interview session for today. You did a great job sharing your experience and insights. We are compiling your performance evaluation now. Wishing you a wonderful day ahead!`;
    },
  }
};

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
    const firstQText = (initialQuestions && initialQuestions.length > 0)
      ? (typeof initialQuestions[0] === 'object' && initialQuestions[0] !== null ? initialQuestions[0].question : initialQuestions[0])
      : '';
    const detectedLang = data.language || detectLanguage(firstQText || data.jdText || data.targetJobTitle, 'vi');

    const resumeInfo = extractCandidateInfoFromResume(data.resumeText);
    const candidateName = data.candidateName || data.fullName || data.name || resumeInfo.name || '';
    const candidateAge = data.candidateAge || data.age || resumeInfo.age || '';
    const candidateYearOfBirth = data.candidateYearOfBirth || data.yearOfBirth || resumeInfo.yearOfBirth || '';
    const candidateGender = data.candidateGender || data.gender || '';

    session = await createSession(interviewId, userId, initialQuestions, baseQuestionIndex, {
      interviewDomain: data.interviewDomain || 'IT',
      targetJobTitle: data.targetJobTitle || (detectedLang === 'en' ? 'Software Engineer' : 'Kỹ sư Phần mềm'),
      resumeText: data.resumeText || '',
      jdText: data.jdText || '',
      language: detectedLang,
      candidateName,
      candidateAge,
      candidateYearOfBirth,
      candidateGender,
      // Chat mode flag — bypasses avatar generation and TTS on the server side
      chatMode: data.chatMode === true || data.chatMode === 'true',
    });
  } else {
    // If client explicitly requested a restart upon joining
    if (data.restart === true || data.forceRestart === true) {
      console.log(`[Signaling] Forced restart requested on join for session: ${interviewId}`);
      session = await restartSession(interviewId);
    } else {
      const updates = {};
      if ((data.chatMode === true || data.chatMode === 'true') && session.chatMode !== 'true') {
        updates.chatMode = 'true';
        session.chatMode = 'true';
      }
      // Update candidate profile fields if they were missing or updated
      const resumeInfo = extractCandidateInfoFromResume(data.resumeText || session.resumeText);
      const candidateName = data.candidateName || data.fullName || data.name || resumeInfo.name;
      const candidateAge = data.candidateAge || data.age || resumeInfo.age;
      const candidateYearOfBirth = data.candidateYearOfBirth || data.yearOfBirth || resumeInfo.yearOfBirth;

      if (!session.candidateName && candidateName) {
        updates.candidateName = candidateName;
        session.candidateName = candidateName;
      }
      if (!session.candidateAge && candidateAge) {
        updates.candidateAge = String(candidateAge);
        session.candidateAge = String(candidateAge);
      }
      if (!session.candidateYearOfBirth && candidateYearOfBirth) {
        updates.candidateYearOfBirth = String(candidateYearOfBirth);
        session.candidateYearOfBirth = String(candidateYearOfBirth);
      }
      if (data.resumeText && !session.resumeText) {
        updates.resumeText = data.resumeText;
        session.resumeText = data.resumeText;
      }
      if (data.jdText && !session.jdText) {
        updates.jdText = data.jdText;
        session.jdText = data.jdText;
      }
      if (Object.keys(updates).length > 0) {
        await updateSession(interviewId, updates);
      }
    }
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
 * Triggers the start of the interview by broadcasting the greeting and first question.
 */
const startFirstQuestion = async (io, interviewId, session) => {
  const firstQuestionObj = session.questions[session.questionState?.baseQuestionIndex || 0];
  const firstQuestion = typeof firstQuestionObj === 'object' && firstQuestionObj !== null
    ? firstQuestionObj.question
    : firstQuestionObj;

  const lang = session.language ? session.language : (detectLanguage(firstQuestion) === 'en' ? 'en' : 'vi');
  const templates = DIALOGUE_TEMPLATES[lang] || DIALOGUE_TEMPLATES.vi;
  const jobTitle = session.targetJobTitle || (lang === 'en' ? 'Software Engineer' : 'Kỹ sư Phần mềm');
  const greetingMessage = templates.greeting(jobTitle, firstQuestion, session);

  const isChatMode = session.chatMode === true || session.chatMode === 'true';
  console.log(`[Signaling] Session INIT. Broadcasting warmup icebreaker greeting (lang=${lang}, chatMode=${isChatMode})`);

  // In chat mode, skip avatar generation entirely — it is an unnecessary async I/O hop
  const avatarAction = isChatMode ? null : await generateAvatarAction(greetingMessage, 'NEUTRAL');

  await updateSession(interviewId, { status: 'IN_PROGRESS' });
  console.log(`[Signaling] Updated Redis session to IN_PROGRESS`);

  io.to(interviewId).emit('orchestration-event', {
    type: 'INTERVIEWER_ACTION',
    payload: {
      actionId: `action-${Date.now()}`,
      actionType: 'TRANSITION',
      text: greetingMessage,
      reasoning: 'Warmup greeting and icebreaker introduction.',
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
  } else if (session.status === 'IN_PROGRESS' && session.questions && session.questions.length > 0) {
    // When a client resumes or reconnects to an ongoing interview session,
    // broadcast the current active question so the candidate can answer immediately.
    const qState = session.questionState || { baseQuestionIndex: 0, currentFollowUpDepth: 0 };
    let activeQuestionText = '';
    if (qState.isWarmup) {
      const sampleQuestion = session.questions[0];
      const sampleText = typeof sampleQuestion === 'object' && sampleQuestion !== null ? sampleQuestion.question : sampleQuestion;
      const lang = session.language === 'en' || detectLanguage(sampleText) === 'en' ? 'en' : 'vi';
      const templates = DIALOGUE_TEMPLATES[lang] || DIALOGUE_TEMPLATES.vi;
      const jobTitle = session.targetJobTitle || (lang === 'en' ? 'Software Engineer' : 'Kỹ sư Phần mềm');
      activeQuestionText = templates.greeting(jobTitle, '', session);
    } else {
      const currentQuestionObj = session.questions[qState.baseQuestionIndex];
      const baseQuestionText = typeof currentQuestionObj === 'object' && currentQuestionObj !== null
        ? currentQuestionObj.question
        : currentQuestionObj;
      activeQuestionText = (qState.currentFollowUpDepth > 0 && qState.currentFollowUpQuestion)
        ? qState.currentFollowUpQuestion
        : baseQuestionText;
    }

    if (activeQuestionText) {
      console.log(`[Signaling] Resuming session ${interviewId}. Emitting current question to socket ${socket.id}`);
      socket.emit('orchestration-event', {
        type: 'INTERVIEWER_ACTION',
        payload: {
          actionId: `action-resume-${Date.now()}`,
          actionType: qState.currentFollowUpDepth > 0 ? 'FOLLOW_UP' : 'TRANSITION',
          text: activeQuestionText,
          reasoning: 'Resumed ongoing session question.',
          score: null,
          evaluation: '',
          isFallback: false,
          audioUrl: null,
          avatarTriggers: null,
        },
      });
    }
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
      candidateName: session.candidateName || '',
      candidateAge: session.candidateAge || '',
      candidateGender: session.candidateGender || '',
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
    candidateName: session.candidateName || '',
    candidateAge: session.candidateAge || '',
    candidateGender: session.candidateGender || '',
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
  nextQState.currentFollowUpQuestion = ''; // clear tracked follow-up on topic transition
  await resetConversationThread(sessionId);

  let nextQuestionText = '';
  let actionType = '';

  const sampleQuestion = session.questions[0];
  const sampleText = typeof sampleQuestion === 'object' && sampleQuestion !== null ? sampleQuestion.question : sampleQuestion;
  const lang = session.language === 'en' || detectLanguage(sampleText) === 'en' ? 'en' : 'vi';
  const templates = DIALOGUE_TEMPLATES[lang] || DIALOGUE_TEMPLATES.vi;

  if (nextQState.baseQuestionIndex < session.questions.length) {
    const nextObj = session.questions[nextQState.baseQuestionIndex];
    const rawQuestion = typeof nextObj === 'object' && nextObj !== null ? nextObj.question : nextObj;
    const transitionList = typeof templates.transitions === 'function'
      ? templates.transitions(session, lang)
      : templates.transitions;
    const prefix = transitionList[Math.floor(Math.random() * transitionList.length)];
    nextQuestionText = `${prefix}\n\n👉 ${rawQuestion}`;
    actionType = 'TRANSITION';
  } else {
    nextQuestionText = typeof templates.concluding === 'function'
      ? templates.concluding(session, lang)
      : templates.concluding;
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
    // Track the follow-up question text so handleCandidateTextSubmit can use it
    // when the candidate responds (instead of incorrectly using the base question).
    nextQState.currentFollowUpQuestion = nextQuestionText;
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
 * In chat mode, avatar generation is skipped to minimise latency.
 *
 * @param {object} io         - Socket.IO server instance
 * @param {string} sessionId  - Interview session ID (also the room name)
 * @param {string} nextQuestionText - The AI's next question / follow-up
 * @param {string} actionType - 'FOLLOW_UP' | 'TRANSITION' | 'CONCLUDING'
 * @param {string} reasoning  - AI reasoning string (for logging / debug)
 * @param {boolean} isFallback - Whether this is a fallback response
 * @param {boolean} [isChatMode=false] - Skips avatar & TTS when true
 */
const broadcastInterviewerAction = async (
  io, sessionId, nextQuestionText, actionType, reasoning, isFallback, isChatMode = false
) => {
  // Skip expensive avatar generation in text-only chat mode
  const avatarAction = isChatMode ? null : await generateAvatarAction(nextQuestionText, 'CURIOUS');

  if (isChatMode) {
    console.log(`[Signaling][ChatMode] Bypassing TTS/Avatar. Emitting text directly to room ${sessionId}`);
  }

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
      audioUrl: null,          // Always null — TTS is handled client-side when needed
      avatarTriggers: avatarAction,
    },
  });
};

/**
 * Orchestrates candidate text submission processing.
 *
 * Flow:
 *   1. Fast gRPC evaluation  → decision (FOLLOW_UP | NEXT_TOPIC) in < timeout
 *   2. Background slow eval  → detailed score written to Redis asynchronously
 *   3. Broadcast next question via socket (text only in chat mode, avatar+TTS otherwise)
 *
 * Chat mode detection uses session.chatMode stored in Redis by joinInterview.
 */
const handleCandidateTextSubmit = async (io, sessionId, session, candidateText) => {
  const isChatMode = session.chatMode === true || session.chatMode === 'true';

  if (isChatMode) {
    console.log(`[Signaling][ChatMode] Text submit received for session ${sessionId}: "${candidateText?.slice(0, 80)}..."`);
  }

  const qState = session.questionState || { baseQuestionIndex: 0, currentFollowUpDepth: 0 };

  // ── Case 0: Warm-up / Small talk turn ─────────────────────────────────────
  if (qState.isWarmup) {
    console.log(`[Signaling] Candidate submitted answer for Warm-up / Small talk turn.`);
    const sampleQuestion = session.questions[0];
    const sampleText = typeof sampleQuestion === 'object' && sampleQuestion !== null ? sampleQuestion.question : sampleQuestion;
    const lang = session.language ? session.language : (detectLanguage(sampleText) === 'en' ? 'en' : 'vi');
    const templates = DIALOGUE_TEMPLATES[lang] || DIALOGUE_TEMPLATES.vi;
    const jobTitle = session.targetJobTitle || (lang === 'en' ? 'Software Engineer' : 'Kỹ sư Phần mềm');

    const firstQuestionObj = session.questions[0];
    const firstQuestionText = typeof firstQuestionObj === 'object' && firstQuestionObj !== null
      ? firstQuestionObj.question
      : (firstQuestionObj || '');

    const greetingQuestion = templates.greeting(jobTitle, '', session);
    const nextQuestionText = templates.warmupAcknowledgement(jobTitle, firstQuestionText, session);

    // Save warmup turn (excluded from scoring)
    await appendToConversationThread(sessionId, {
      question: greetingQuestion,
      answer: candidateText,
      wasFollowUp: false,
    });

    await appendTurn(sessionId, {
      question: greetingQuestion,
      answer: candidateText,
      score: null,
      evaluation: 'Khởi động / Giới thiệu làm quen (Icebreaker)',
      wasFollowUp: false,
      excludedFromScoring: true,
    });

    const nextQState = {
      ...qState,
      isWarmup: false,
      baseQuestionIndex: 0,
      currentFollowUpDepth: 0,
      currentFollowUpQuestion: '',
    };

    const updatedSession = await updateSession(sessionId, {
      questionState: nextQState,
      status: 'IN_PROGRESS',
    });

    emitStateUpdate(io.to(sessionId), updatedSession);

    await broadcastInterviewerAction(
      io, sessionId, nextQuestionText, 'TRANSITION',
      'Completed warm-up small talk, moving to Question 1.', false, isChatMode
    );
    return;
  }

  const currentQuestionObj = session.questions[qState.baseQuestionIndex];
  const baseQuestionText = typeof currentQuestionObj === 'object' && currentQuestionObj !== null
    ? currentQuestionObj.question
    : currentQuestionObj;

  // If we're responding to a follow-up, use the tracked follow-up question text.
  // This ensures the turn is recorded with the correct follow-up question, not the base question.
  const currentQuestion = (qState.currentFollowUpDepth > 0 && qState.currentFollowUpQuestion)
    ? qState.currentFollowUpQuestion
    : baseQuestionText;

  const goodAnswerSignals = currentQuestionObj?.good_answer_signals || [];
  const cvText = session.resumeText || '';
  const limitReached = qState.currentFollowUpDepth >= (qState.maxFollowUpDepth || 3);

  // ── Tier 1: Fast evaluation (synchronous, determines conversation flow) ──────
  const engineResponse = await runFastEvaluation(
    sessionId, session, currentQuestion, candidateText, qState, cvText, limitReached
  );
  console.log(`[Signaling] Fast decision: ${engineResponse.decision}, reasoning: ${engineResponse.reasoning}`);

  // ── Persist conversation context ─────────────────────────────────────────────
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

  // ── Tier 2: Slow / detailed evaluation (fire-and-forget background task) ─────
  triggerSlowEvaluation(
    sessionId, session, currentQuestion, candidateText, qState, cvText, goodAnswerSignals
  );

  // ── Determine next question ───────────────────────────────────────────────────
  const { nextQuestionText, actionType, nextQState } = await determineNextQuestion(
    sessionId, session, qState, engineResponse
  );

  const updatedSession = await updateSession(sessionId, {
    questionState: nextQState,
    status: actionType === 'CONCLUDING' ? 'COMPLETED' : 'IN_PROGRESS',
  });

  // Emit state update so frontend can reflect session status change
  emitStateUpdate(io.to(sessionId), updatedSession);

  // ── Broadcast AI's next action (bypasses avatar/TTS in chat mode) ─────────────
  await broadcastInterviewerAction(
    io, sessionId, nextQuestionText, actionType,
    engineResponse.reasoning, engineResponse.isFallback,
    isChatMode  // ← chat mode flag passed through
  );
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

  // IDOR Protection: Ensure user is authorized to modify/submit data for this session.
  // If candidateId is absent (e.g. session was created before this field existed, or
  // the session was resumed from a different client), we allow access but log a warning.
  if (session.candidateId && session.candidateId !== userId) {
    console.warn(
      `[Security Alert] Socket user ${userId} attempted unauthorized access for session: ${sessionId} ` +
      `(stored candidateId: ${session.candidateId})`
    );
    socket.emit('error', { message: 'Access denied: unauthorized session modification' });
    return;
  }

  if (data.type === 'RESTART_INTERVIEW' || data.type === 'RESET_INTERVIEW') {
    console.log(`[Signaling] RESTART_INTERVIEW requested for session ${sessionId}`);
    const restartedSession = await restartSession(sessionId);
    emitStateUpdate(io.to(sessionId), restartedSession);
    if (restartedSession.questions && restartedSession.questions.length > 0) {
      await startFirstQuestion(io, sessionId, restartedSession);
    }
  } else if (data.type === 'CANDIDATE_TEXT_SUBMIT') {
    const candidateText = data.payload?.text;
    if (!candidateText || typeof candidateText !== 'string' || !candidateText.trim()) {
      console.warn(`[Signaling] CANDIDATE_TEXT_SUBMIT received with empty/invalid text for session ${sessionId}`);
      socket.emit('error', { message: 'CANDIDATE_TEXT_SUBMIT requires a non-empty text payload' });
      return;
    }
    await handleCandidateTextSubmit(io, sessionId, session, candidateText.trim());
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
