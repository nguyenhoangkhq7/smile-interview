import { createServer } from 'http';
import dotenv from 'dotenv';
import app from './app.js';
import { initSocket } from './socket.js';
import { connectRedis } from './config/redis.js';
import path from 'path';

// Load root .env first, then local .env overrides
dotenv.config({ path: path.resolve(process.cwd(), '../../.env') });
dotenv.config();

const PORT = process.env.PORT || 8001;

// Wrap Express app with Node's native HTTP server
const httpServer = createServer(app);

// Attach Socket.io
initSocket(httpServer);

// ─── Bootstrap ────────────────────────────────────────────────────────────────
const startServer = async () => {
  try {
    await connectRedis();
    httpServer.listen(PORT, () => {
      console.log(`Streaming Service listening on port ${PORT}`);
      console.log(`  → Health:      http://localhost:${PORT}/health`);
      console.log(`  → Transcribe:  POST http://localhost:${PORT}/api/v1/audio/transcribe`);
      console.log(`  → Synthesize:  POST http://localhost:${PORT}/api/v1/audio/synthesize`);
    });
  } catch (error) {
    console.error('Failed to start Streaming Service:', error);
    process.exit(1);
  }
};

startServer();
