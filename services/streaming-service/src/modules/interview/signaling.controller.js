import redisClient from '../../config/redis.js';
import { transcribeAudio } from '../audio/audio.service.js';
import { synthesizeSpeech } from '../tts/tts.service.js';
import { createSession, getSession, updateSession } from './session.service.js';
import { evaluateCandidateResponse } from './engine.client.js';
import { generateAvatarAction } from './mockAvatar.service.js';

export const handleConnection = (io, socket) => {
  console.log(`Client connected: ${socket.id}`);

  // Handle joining an interview session
  socket.on('join-interview', async (data) => {
    try {
      const { interviewId, userId, initialQuestions, baseQuestionIndex = 0 } = data;
      if (!interviewId || !userId) {
        socket.emit('error', { message: 'interviewId and userId are required' });
        return;
      }

      console.log(`User ${userId} joined interview ${interviewId} on socket ${socket.id}, baseIndex: ${baseQuestionIndex}`);
      
      // Save socket-to-user/interview mapping in Redis for session management
      await redisClient.hSet(`socket:${socket.id}`, {
        interviewId,
        userId,
        joinedAt: new Date().toISOString()
      });
      
      await redisClient.sAdd(`interview:${interviewId}:participants`, userId);
      socket.join(interviewId);
      console.log(`[Signaling] Socket ${socket.id} joined room ${interviewId}`);
      
      // Initialize or get orchestration session
      let session = await getSession(interviewId);
      console.log(`[Signaling] Fetched existing session from Redis:`, session ? 'Found' : 'Null');
      if (!session) {
        console.log(`[Signaling] Creating new session in Redis with initialQuestions:`, initialQuestions);
        session = await createSession(interviewId, userId, initialQuestions, baseQuestionIndex);
      }
      console.log(`[Signaling] Session state status: ${session?.status}, questions length: ${session?.questions?.length}`);

      socket.to(interviewId).emit('peer-joined', { userId, socketId: socket.id });
      socket.emit('joined-room', { interviewId, userId });
      
      // Emit initial orchestration state to the user who joined
      socket.emit('orchestration-event', {
        type: 'STATE_UPDATE',
        payload: {
          status: session.status,
          questionState: session.questionState
        }
      });
      console.log(`[Signaling] Emitted STATE_UPDATE to client`);

      // Optionally, push the first base question to start the interview if INIT
      if (session.status === 'INIT' && session.questions.length > 0) {
        const firstQuestion = session.questions[session.questionState?.baseQuestionIndex || 0];
        console.log(`[Signaling] Session status is INIT. Broadcasting first question: "${firstQuestion}"`);
        const avatarAction = await generateAvatarAction(firstQuestion, 'NEUTRAL');

        // Update state to IN_PROGRESS
        await updateSession(interviewId, { status: 'IN_PROGRESS' });
        console.log(`[Signaling] Updated Redis session to IN_PROGRESS`);

        io.to(interviewId).emit('orchestration-event', {
          type: 'INTERVIEWER_ACTION',
          payload: {
            actionId: `action-${Date.now()}`,
            actionType: 'TRANSITION',
            text: firstQuestion,
            reasoning: 'Starting the interview.',
            score: 0,
            evaluation: '',
            audioUrl: null,
            avatarTriggers: avatarAction
          }
        });
        console.log(`[Signaling] Emitted INTERVIEWER_ACTION to room ${interviewId}`);
      } else {
        console.log(`[Signaling] Skip INIT questions broadcast. Status: ${session.status}, questions length: ${session.questions.length}`);
      }

    } catch (error) {
      console.error('Error in join-interview:', error);
      socket.emit('error', { message: 'Failed to join interview room' });
    }
  });

  // Handle Orchestration Events from the Frontend
  socket.on('orchestration-event', async (data) => {
    try {
      const socketInfo = await redisClient.hGetAll(`socket:${socket.id}`);
      if (!socketInfo || !socketInfo.interviewId) {
        socket.emit('error', { message: 'Not joined in any session' });
        return;
      }
      
      const sessionId = socketInfo.interviewId;

      if (data.type === 'CANDIDATE_TEXT_SUBMIT') {
        const candidateText = data.payload.text;
        
        // 1. Get Session State
        const session = await getSession(sessionId);
        if (!session) throw new Error('Session not found');

        const qState = session.questionState;
        
        // Determine the current question context for the engine
        // If we are currently following up, we'd ideally pass the previous follow-up. 
        // For simplicity, we pass the base question from the list.
        const currentQuestion = session.questions[qState.baseQuestionIndex];

        // 2. Call Java AI Inference Service via gRPC
        const engineResponse = await evaluateCandidateResponse({
          sessionId: sessionId,
          currentQuestion: currentQuestion,
          candidateAnswer: candidateText,
          currentFollowUpCount: qState.currentFollowUpDepth,
          targetJobTitle: "IT Engineer",
          previousQaContext: [] // Can be populated from a full history list if maintained
        });
        
        let nextQuestionText = "";
        let actionType = engineResponse.decision; // e.g. "FOLLOW_UP" or "NEXT_TOPIC"
        let nextQState = { ...qState };

        if (actionType === 'FOLLOW_UP') {
          nextQuestionText = engineResponse.generatedFollowUpQuestion;
          nextQState.currentFollowUpDepth += 1;
        } else {
          // Transition to Next Topic
          nextQState.baseQuestionIndex += 1;
          nextQState.currentFollowUpDepth = 0;
          
          if (nextQState.baseQuestionIndex < session.questions.length) {
            nextQuestionText = session.questions[nextQState.baseQuestionIndex];
            actionType = 'TRANSITION';
          } else {
            nextQuestionText = "Thank you. That concludes our technical questions.";
            actionType = 'CONCLUDING';
          }
        }

        // 3. Update Session State
        const updatedSession = await updateSession(sessionId, {
          questionState: nextQState,
          status: actionType === 'CONCLUDING' ? 'COMPLETED' : 'IN_PROGRESS'
        });

        // 4. Broadcast State Update
        io.to(sessionId).emit('orchestration-event', {
          type: 'STATE_UPDATE',
          payload: { 
            status: updatedSession.status, 
            questionState: updatedSession.questionState 
          }
        });

        // 5. Generate Mock Avatar Triggers
        const emotionHint = engineResponse.score > 7 ? 'HAPPY' : 'CURIOUS';
        const avatarAction = await generateAvatarAction(nextQuestionText, emotionHint);
        
        // 6. Broadcast INTERVIEWER_ACTION
        io.to(sessionId).emit('orchestration-event', {
          type: 'INTERVIEWER_ACTION',
          payload: {
            actionId: `action-${Date.now()}`,
            actionType: actionType,
            text: nextQuestionText,
            reasoning: engineResponse.reasoning,
            score: engineResponse.score,
            evaluation: engineResponse.evaluation,
            audioUrl: null,
            avatarTriggers: avatarAction
          }
        });
      }
    } catch (error) {
      console.error('Error in orchestration event:', error);
    }
  });

  // Handle RTC Signaling (offer, answer, candidate routing)
  socket.on('signal', async (data) => {
    try {
      const { targetSocketId, signal } = data;
      const senderInfo = await redisClient.hGetAll(`socket:${socket.id}`);
      if (!senderInfo || !senderInfo.userId) return;
      
      if (targetSocketId) {
        io.to(targetSocketId).emit('signal', { senderSocketId: socket.id, senderUserId: senderInfo.userId, signal });
      } else if (senderInfo.interviewId) {
        socket.to(senderInfo.interviewId).emit('signal', { senderSocketId: socket.id, senderUserId: senderInfo.userId, signal });
      }
    } catch (error) {}
  });

  // Handle streaming audio chunk routing
  socket.on('audio-chunk', async (data) => {
    try {
      const { chunk } = data; 
      const socketInfo = await redisClient.hGetAll(`socket:${socket.id}`);
      if (!socketInfo || !socketInfo.interviewId) return;
      socket.to(socketInfo.interviewId).emit('audio-chunk', { userId: socketInfo.userId, chunk, timestamp: Date.now() });
    } catch (error) {}
  });

  // STT / TTS Handlers
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

  // Handle disconnect
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
