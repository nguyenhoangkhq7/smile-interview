import {
  handleDisconnect,
  handleAudioChunk,
  handleSignal,
  handleOrchestrationEvent,
  joinInterview,
  processStt,
  processTts,
} from './signaling.service.js';

export const handleConnection = (io, socket) => {
  console.log(`Client connected: ${socket.id}`);

  // Join interview session
  socket.on('join-interview', async (data) => {
    try {
      await joinInterview(io, socket, data);
    } catch (error) {
      console.error('Error in join-interview:', error);
      socket.emit('error', { message: 'Failed to join interview room' });
    }
  });

  // Orchestration events
  socket.on('orchestration-event', async (data) => {
    try {
      await handleOrchestrationEvent(io, socket, data);
    } catch (error) {
      console.error('Error in orchestration event:', error);
    }
  });

  // RTC Signaling
  socket.on('signal', async (data) => {
    try {
      await handleSignal(io, socket, data);
    } catch (error) {
      console.error('Error in signal event:', error);
    }
  });

  // Streaming audio chunk routing
  socket.on('audio-chunk', async (data) => {
    try {
      await handleAudioChunk(io, socket, data);
    } catch (error) {
      console.error('Error in audio-chunk event:', error);
    }
  });

  // STT / TTS
  socket.on('process-stt', async (audioBuffer) => {
    try {
      await processStt(socket, audioBuffer);
    } catch (error) {
      socket.emit('stt-error', { status: 'error', message: error.message });
    }
  });

  socket.on('process-tts', async (text) => {
    try {
      await processTts(socket, text);
    } catch (error) {
      socket.emit('tts-error', { status: 'error', message: error.message });
    }
  });

  // Disconnect
  socket.on('disconnect', async () => {
    try {
      await handleDisconnect(io, socket);
    } catch (error) {
      console.error('Error in disconnect event:', error);
    }
  });
};
