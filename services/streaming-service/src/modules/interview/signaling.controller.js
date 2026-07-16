import redisClient from '../../config/redis.js';
import { transcribeAudio } from '../audio/audio.service.js';
import { synthesizeSpeech } from '../tts/tts.service.js';
import {
  createSession,
  getSession,
  updateSession,
  appendTurn,
  appendToConversationThread,
  resetConversationThread
} from './session.service.js';
import { evaluateCandidateResponse, generateFinalReport } from './engine.client.js';
import { generateAvatarAction } from './mockAvatar.service.js';

export const handleConnection = (io, socket) => {
  console.log(`Client connected: ${socket.id}`);

  // ─── Join interview session ───────────────────────────────────────────────

  socket.on('join-interview', async (data) => {
    try {
      const { interviewId, userId, initialQuestions, baseQuestionIndex = 0 } = data;
      if (!interviewId || !userId) {
        socket.emit('error', { message: 'interviewId and userId are required' });
        return;
      }

      console.log(`User ${userId} joined interview ${interviewId} on socket ${socket.id}, baseIndex: ${baseQuestionIndex}`);

      await redisClient.hSet(`socket:${socket.id}`, {
        interviewId,
        userId,
        joinedAt: new Date().toISOString()
      });

      await redisClient.sAdd(`interview:${interviewId}:participants`, userId);
      socket.join(interviewId);
      console.log(`[Signaling] Socket ${socket.id} joined room ${interviewId}`);

      let session = await getSession(interviewId);
      console.log(`[Signaling] Fetched existing session from Redis:`, session ? 'Found' : 'Null');
      if (!session) {
        console.log(`[Signaling] Creating new session in Redis with initialQuestions:`, initialQuestions);
        session = await createSession(interviewId, userId, initialQuestions, baseQuestionIndex, {
          interviewDomain: data.interviewDomain || 'IT',
          targetJobTitle: data.targetJobTitle || 'IT Engineer',
          resumeText: data.resumeText || '',
          jdText: data.jdText || ''
        });
      }
      console.log(`[Signaling] Session status: ${session?.status}, questions: ${session?.questions?.length}`);

      socket.to(interviewId).emit('peer-joined', { userId, socketId: socket.id });
      socket.emit('joined-room', { interviewId, userId });

      socket.emit('orchestration-event', {
        type: 'STATE_UPDATE',
        payload: {
          status: session.status,
          questionState: session.questionState
        }
      });
      console.log(`[Signaling] Emitted STATE_UPDATE to client`);

      if (session.status === 'INIT' && session.questions.length > 0) {
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
            avatarTriggers: avatarAction
          }
        });
        console.log(`[Signaling] Emitted INTERVIEWER_ACTION to room ${interviewId}`);
      }
    } catch (error) {
      console.error('Error in join-interview:', error);
      socket.emit('error', { message: 'Failed to join interview room' });
    }
  });

  // ─── Orchestration events ─────────────────────────────────────────────────

  socket.on('orchestration-event', async (data) => {
    try {
      const socketInfo = await redisClient.hGetAll(`socket:${socket.id}`);
      if (!socketInfo || !socketInfo.interviewId) {
        socket.emit('error', { message: 'Not joined in any session' });
        return;
      }

      const sessionId = socketInfo.interviewId;

       // ── CANDIDATE_TEXT_SUBMIT ───────────────────────────────────────────
      if (data.type === 'CANDIDATE_TEXT_SUBMIT') {
        const candidateText = data.payload.text;

        // 1. Get session state
        const session = await getSession(sessionId);
        if (!session) throw new Error('Session not found');

        const qState = session.questionState;
        const currentQuestionObj = session.questions[qState.baseQuestionIndex];
        const currentQuestion = typeof currentQuestionObj === 'object' && currentQuestionObj !== null
          ? currentQuestionObj.question
          : currentQuestionObj;

        const goodAnswerSignals = currentQuestionObj && currentQuestionObj.good_answer_signals
          ? currentQuestionObj.good_answer_signals
          : [];

        const cvText = session.resumeText || '';
        const limitReached = qState.currentFollowUpDepth >= (qState.maxFollowUpDepth || 3);

        let engineResponse;

        if (limitReached) {
          console.log(`[Signaling] Limit reached. Bypassing synchronous LLM evaluation.`);
          engineResponse = {
            decision: 'NEXT_TOPIC',
            followUpQuestion: '',
            reasoning: 'Bypassed LLM call: reached maximum follow-up depth.',
            score: null,
            evaluation: '',
            isFallback: false,
            excludedFromScoring: false
          };
        } else {
          // Fast mode evaluation synchronously
          console.log(`[Signaling] Calling fast evaluation synchronously...`);
          try {
            engineResponse = await evaluateCandidateResponse({
              sessionId,
              targetJobTitle: session.targetJobTitle || 'IT Engineer',
              interviewDomain: session.interviewDomain || 'IT',
              currentQuestion,
              candidateAnswer: candidateText,
              currentFollowUpCount: qState.currentFollowUpDepth,
              maxFollowUpCount: qState.maxFollowUpDepth || 3,
              conversationThread: session.conversationThread || [],
              fastMode: true,
              cvText
            });
          } catch (error) {
            console.error('[Signaling] Fast evaluation failed. Using fallback.', error);
            engineResponse = {
              decision: 'NEXT_TOPIC',
              followUpQuestion: '',
              reasoning: 'Fast evaluation failed, falling back to NEXT_TOPIC.',
              score: null,
              evaluation: '',
              isFallback: true,
              excludedFromScoring: true
            };
          }
        }

        console.log(`[Signaling] Fast decision: ${engineResponse.decision}, reasoning: ${engineResponse.reasoning}`);

        // 3. Append current QA to conversation thread (before potentially resetting it)
        await appendToConversationThread(sessionId, {
          question: currentQuestion,
          answer: candidateText,
          wasFollowUp: qState.currentFollowUpDepth > 0
        });

        // 4. Append turn record for final synthesis (initially empty score/eval)
        await appendTurn(sessionId, {
          question: currentQuestion,
          answer: candidateText,
          score: null,
          evaluation: '',
          wasFollowUp: qState.currentFollowUpDepth > 0,
          excludedFromScoring: engineResponse.excludedFromScoring
        });

        // 5. Fire asynchronous slow evaluation in the background
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
          goodAnswerSignals
        };

        // Asynchronous IIFE for background evaluation
        (async () => {
          console.log(`[Background Eval] Starting detailed evaluation in background...`);
          try {
            const slowRes = await evaluateCandidateResponse(slowEvalParams);
            console.log(`[Background Eval] Finished for session ${sessionId}. Score: ${slowRes.score}`);
            
            // Update Redis turns
            const sess = await getSession(sessionId);
            if (sess) {
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
                  updatedAt: new Date().toISOString()
                });
                console.log(`[Background Eval] Successfully updated Redis turns with score.`);
              }
            }
          } catch (e) {
            console.error(`[Background Eval] Detailed evaluation failed in background:`, e);
          }
        })();

        // 6. Determine next question and update state
        let nextQuestionText = '';
        let actionType = engineResponse.decision;
        let nextQState = { ...qState };

        if (actionType === 'FOLLOW_UP' && !engineResponse.isFallback) {
          nextQuestionText = engineResponse.followUpQuestion || '';
          nextQState.currentFollowUpDepth += 1;
          console.log(`[Signaling] AI follow-up: "${nextQuestionText}" (depth: ${nextQState.currentFollowUpDepth})`);

          if (!nextQuestionText.trim()) {
            console.warn('[Signaling] AI returned FOLLOW_UP but followUpQuestion is empty. Transitioning.');
            actionType = 'TRANSITION';
            nextQState.baseQuestionIndex += 1;
            nextQState.currentFollowUpDepth = 0;
            await resetConversationThread(sessionId);

            if (nextQState.baseQuestionIndex < session.questions.length) {
              const nextObj = session.questions[nextQState.baseQuestionIndex];
              nextQuestionText = typeof nextObj === 'object' && nextObj !== null ? nextObj.question : nextObj;
            } else {
              nextQuestionText = 'Thank you. That concludes our technical questions.';
              actionType = 'CONCLUDING';
            }
          }
        } else {
          nextQState.baseQuestionIndex += 1;
          nextQState.currentFollowUpDepth = 0;
          await resetConversationThread(sessionId);

          if (nextQState.baseQuestionIndex < session.questions.length) {
            const nextObj = session.questions[nextQState.baseQuestionIndex];
            nextQuestionText = typeof nextObj === 'object' && nextObj !== null ? nextObj.question : nextObj;
            actionType = 'TRANSITION';
          } else {
            nextQuestionText = 'Thank you. That concludes our technical questions.';
            actionType = 'CONCLUDING';
          }
        }

        // 7. Update session state
        const updatedSession = await updateSession(sessionId, {
          questionState: nextQState,
          status: actionType === 'CONCLUDING' ? 'COMPLETED' : 'IN_PROGRESS'
        });

        // 8. Broadcast state update
        io.to(sessionId).emit('orchestration-event', {
          type: 'STATE_UPDATE',
          payload: {
            status: updatedSession.status,
            questionState: updatedSession.questionState
          }
        });

        // 9. Generate avatar triggers
        const emotionHint = 'CURIOUS'; // Baseline since score is calculated asynchronously
        const avatarAction = await generateAvatarAction(nextQuestionText, emotionHint);

        // 10. Broadcast INTERVIEWER_ACTION
        io.to(sessionId).emit('orchestration-event', {
          type: 'INTERVIEWER_ACTION',
          payload: {
            actionId: `action-${Date.now()}`,
            actionType,
            text: nextQuestionText,
            reasoning: engineResponse.reasoning,
            score: null,
            evaluation: '',
            isFallback: engineResponse.isFallback,
            audioUrl: null,
            avatarTriggers: avatarAction
          }
        });
      }

      // ── INTERVIEW_END ───────────────────────────────────────────────────
      if (data.type === 'INTERVIEW_END') {
        console.log(`[Signaling] INTERVIEW_END received for session ${sessionId}`);
        try {
          const session = await getSession(sessionId);
          if (!session) throw new Error('Session not found');

          // Filter out turns excluded from scoring (fallback turns)
          const scoredTurns = (session.turns || []).filter(t => !t.excludedFromScoring);

          console.log(`[Signaling] Generating final report. Scored turns: ${scoredTurns.length}`);

          const finalReport = await generateFinalReport({
            sessionId,
            targetJobTitle: session.targetJobTitle || 'IT Engineer',
            turns: scoredTurns,
            resumeText: session.resumeText || '',
            jdText: session.jdText || ''
          });

          // Mark session as fully completed
          await updateSession(sessionId, { status: 'REPORT_READY' });

          // Emit final report to the room
          io.to(sessionId).emit('orchestration-event', {
            type: 'FINAL_REPORT',
            payload: finalReport
          });

          console.log(`[Signaling] Final report emitted. Hiring recommendation: ${finalReport.hiringRecommendation}`);
        } catch (reportError) {
          console.error('[Signaling] Failed to generate final report:', reportError);
          io.to(sessionId).emit('orchestration-event', {
            type: 'FINAL_REPORT_ERROR',
            payload: { message: 'Failed to generate final report. Please try again.' }
          });
        }
      }
    } catch (error) {
      console.error('Error in orchestration event:', error);
    }
  });

  // ─── RTC Signaling ────────────────────────────────────────────────────────

  socket.on('signal', async (data) => {
    try {
      const { targetSocketId, signal } = data;
      const senderInfo = await redisClient.hGetAll(`socket:${socket.id}`);
      if (!senderInfo || !senderInfo.userId) return;

      if (targetSocketId) {
        io.to(targetSocketId).emit('signal', {
          senderSocketId: socket.id,
          senderUserId: senderInfo.userId,
          signal
        });
      } else if (senderInfo.interviewId) {
        socket.to(senderInfo.interviewId).emit('signal', {
          senderSocketId: socket.id,
          senderUserId: senderInfo.userId,
          signal
        });
      }
    } catch (error) {}
  });

  // ─── Streaming audio chunk routing ───────────────────────────────────────

  socket.on('audio-chunk', async (data) => {
    try {
      const { chunk } = data;
      const socketInfo = await redisClient.hGetAll(`socket:${socket.id}`);
      if (!socketInfo || !socketInfo.interviewId) return;
      socket.to(socketInfo.interviewId).emit('audio-chunk', {
        userId: socketInfo.userId,
        chunk,
        timestamp: Date.now()
      });
    } catch (error) {}
  });

  // ─── STT / TTS ────────────────────────────────────────────────────────────

  socket.on('process-stt', async (audioBuffer) => {
    try {
      const mockFile = { buffer: audioBuffer, originalname: 'stream.webm', mimetype: 'audio/webm' };
      const resultText = await transcribeAudio(mockFile.buffer, mockFile.originalname);
      socket.emit('stt-result', { status: 'success', text: resultText });
    } catch (error) {
      socket.emit('stt-error', { status: 'error', message: error.message });
    }
  });

  socket.on('process-tts', async (text) => {
    try {
      const audioArrayBuffer = await synthesizeSpeech(text);
      socket.emit('tts-result', Buffer.from(audioArrayBuffer));
    } catch (error) {
      socket.emit('tts-error', { status: 'error', message: error.message });
    }
  });

  // ─── Disconnect ───────────────────────────────────────────────────────────

  socket.on('disconnect', async () => {
    console.log(`Client disconnected: ${socket.id}`);
    try {
      const socketInfo = await redisClient.hGetAll(`socket:${socket.id}`);
      if (socketInfo && socketInfo.interviewId && socketInfo.userId) {
        const { interviewId, userId } = socketInfo;
        await redisClient.sRem(`interview:${interviewId}:participants`, userId);
        socket.to(interviewId).emit('peer-left', { userId, socketId: socket.id });
      }
      await redisClient.del(`socket:${socket.id}`);
    } catch (error) {}
  });
};
