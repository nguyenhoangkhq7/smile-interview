import express from 'express';
import { createServer } from 'http';
import { Server } from 'socket.io';
import cors from 'cors';
import multer from 'multer';
import dotenv from 'dotenv';
import { connectRedis } from './config/redis.js';
import { handleConnection } from './controllers/signaling.controller.js';
import { transcribe } from './controllers/audio.controller.js';
import { synthesizeAudio } from './controllers/tts.controller.js';

dotenv.config();

const app = express();
const PORT = process.env.PORT || 8001;

// ─── CORS Configuration ────────────────────────────────────────────────────────
const corsOptions = {
  origin: process.env.CORS_ORIGIN || '*',
  methods: ['GET', 'POST'],
  credentials: true,
};

app.use(cors(corsOptions));
app.use(express.json());

// ─── Multer — Memory Storage ───────────────────────────────────────────────────
// Audio clips are short-lived, so we hold them in RAM rather than writing to
// disk. The buffer is passed directly to the Whisper API and then discarded.
const upload = multer({
  storage: multer.memoryStorage(),
  limits: {
    fileSize: 25 * 1024 * 1024, // 25 MB — Whisper API hard limit
  },
  fileFilter: (_req, file, cb) => {
    // Accept common audio MIME types
    const allowedMimes = [
      'audio/mpeg',
      'audio/mp4',
      'audio/ogg',
      'audio/wav',
      'audio/webm',
      'audio/flac',
      'audio/x-m4a',
    ];
    if (allowedMimes.includes(file.mimetype)) {
      cb(null, true);
    } else {
      cb(new Error(`Unsupported audio format: ${file.mimetype}`), false);
    }
  },
});

// ─── REST Routes ───────────────────────────────────────────────────────────────

// Health Check
app.get('/health', (_req, res) => {
  res.status(200).json({ status: 'UP', service: 'streaming-service' });
});

// POST /api/v1/audio/transcribe
// Accepts multipart/form-data with a single audio file under field name "audio"
app.post(
  '/api/v1/audio/transcribe',
  upload.single('audio'),
  transcribe
);

// POST /api/v1/audio/synthesize
// Accepts JSON body: { "text": "...", "voice": "af_bella" }
// Returns raw MP3 bytes with Content-Type: audio/mpeg
app.post('/api/v1/audio/synthesize', synthesizeAudio);

// GET /api/v1/audio/stream-transcribe
// Accepts query parameter text
// Returns Server-Sent Events stream typing out each word at 80ms intervals
app.get('/api/v1/audio/stream-transcribe', (req, res) => {
  const text = req.query.text || '';
  
  res.writeHead(200, {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'Access-Control-Allow-Origin': '*'
  });
  
  res.write('data: [START]\n\n');
  
  if (!text) {
    res.write('data: [END]\n\n');
    res.end();
    return;
  }
  
  const words = text.split(' ');
  let index = 0;
  
  const interval = setInterval(() => {
    if (index < words.length) {
      res.write(`data: ${words[index]}\n\n`);
      index++;
    } else {
      clearInterval(interval);
      res.write('data: [END]\n\n');
      res.end();
    }
  }, 80);
  
  req.on('close', () => {
    clearInterval(interval);
  });
});

// ─── Multer Error Handler ──────────────────────────────────────────────────────
// Must be defined AFTER routes to intercept multer-specific errors cleanly
// eslint-disable-next-line no-unused-vars
app.use((err, _req, res, _next) => {
  if (err instanceof multer.MulterError || err.message?.startsWith('Unsupported audio format')) {
    return res.status(400).json({ status: 'error', message: err.message });
  }
  console.error('[Server] Unhandled error:', err);
  return res.status(500).json({ status: 'error', message: 'Internal server error' });
});

// ─── HTTP + Socket.io Server ───────────────────────────────────────────────────

// Wrap Express app with Node's native HTTP server
const httpServer = createServer(app);

// Initialize Socket.io with matching CORS config
const io = new Server(httpServer, {
  cors: corsOptions,
  pingTimeout: 60000,
  pingInterval: 25000,
});

// Register Socket.io connection handler
io.on('connection', (socket) => {
  handleConnection(io, socket);
});

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
