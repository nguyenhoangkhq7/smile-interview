import redisClient from '../config/redis.js';

export const handleConnection = (io, socket) => {
  console.log(`Client connected: ${socket.id}`);

  // Handle joining an interview session
  socket.on('join-interview', async (data) => {
    try {
      const { interviewId, userId } = data;
      if (!interviewId || !userId) {
        socket.emit('error', { message: 'interviewId and userId are required' });
        return;
      }

      console.log(`User ${userId} joined interview ${interviewId} on socket ${socket.id}`);
      
      // Save socket-to-user/interview mapping in Redis for session management
      await redisClient.hSet(`socket:${socket.id}`, {
        interviewId,
        userId,
        joinedAt: new Date().toISOString()
      });
      
      // Also add user to the interview session set in Redis
      await redisClient.sAdd(`interview:${interviewId}:participants`, userId);
      
      // Join the Socket.io room matching the interview ID
      socket.join(interviewId);
      
      // Notify other participants in the room
      socket.to(interviewId).emit('peer-joined', { userId, socketId: socket.id });
      
      // Acknowledge successful join
      socket.emit('joined-room', { interviewId, userId });
    } catch (error) {
      console.error('Error in join-interview:', error);
      socket.emit('error', { message: 'Failed to join interview room' });
    }
  });

  // Handle RTC Signaling (offer, answer, candidate routing)
  socket.on('signal', async (data) => {
    try {
      const { targetSocketId, signal } = data;
      
      // Retrieve sender info from Redis
      const senderInfo = await redisClient.hGetAll(`socket:${socket.id}`);
      if (!senderInfo || !senderInfo.userId) {
        socket.emit('error', { message: 'Not joined in any session' });
        return;
      }
      
      if (targetSocketId) {
        // Route signal to a specific socket ID
        io.to(targetSocketId).emit('signal', {
          senderSocketId: socket.id,
          senderUserId: senderInfo.userId,
          signal
        });
      } else if (senderInfo.interviewId) {
        // Broadcast signal to everyone else in the interview room
        socket.to(senderInfo.interviewId).emit('signal', {
          senderSocketId: socket.id,
          senderUserId: senderInfo.userId,
          signal
        });
      }
    } catch (error) {
      console.error('Error in signaling routing:', error);
    }
  });

  // Handle streaming audio chunk routing
  socket.on('audio-chunk', async (data) => {
    try {
      const { chunk } = data; // audio data chunk (buffer or base64 string)
      
      // Retrieve session info from Redis
      const socketInfo = await redisClient.hGetAll(`socket:${socket.id}`);
      if (!socketInfo || !socketInfo.interviewId) {
        return;
      }

      const { interviewId, userId } = socketInfo;

      // Broadcast the audio chunk to other participants in the interview room
      socket.to(interviewId).emit('audio-chunk', {
        userId,
        chunk,
        timestamp: Date.now()
      });
    } catch (error) {
      console.error('Error handling audio chunk:', error);
    }
  });

  // Handle client disconnection
  socket.on('disconnect', async () => {
    console.log(`Client disconnected: ${socket.id}`);
    try {
      // Fetch user and interview info before deleting
      const socketInfo = await redisClient.hGetAll(`socket:${socket.id}`);
      if (socketInfo && socketInfo.interviewId && socketInfo.userId) {
        const { interviewId, userId } = socketInfo;
        
        // Remove user from the interview participants set
        await redisClient.sRem(`interview:${interviewId}:participants`, userId);
        
        // Notify others in the room
        socket.to(interviewId).emit('peer-left', { userId, socketId: socket.id });
      }
      
      // Clean up socket mapping in Redis
      await redisClient.del(`socket:${socket.id}`);
    } catch (error) {
      console.error('Error during client disconnect cleanup:', error);
    }
  });
};
