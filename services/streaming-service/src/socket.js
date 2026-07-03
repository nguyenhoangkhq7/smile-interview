import { Server } from 'socket.io';
import { handleConnection } from './modules/interview/signaling.controller.js';
import { corsOptions } from './app.js';

export const initSocket = (httpServer) => {
  const io = new Server(httpServer, {
    cors: corsOptions,
    pingTimeout: 60000,
    pingInterval: 25000,
  });

  io.on('connection', (socket) => {
    handleConnection(io, socket);
  });

  return io;
};
