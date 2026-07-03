import express from 'express';
import cors from 'cors';
import audioRoutes from './modules/audio/audio.routes.js';
import ttsRoutes from './modules/tts/tts.routes.js';
import { handleMulterError } from './modules/audio/upload.middleware.js';

const app = express();

const corsOptions = {
  origin: process.env.CORS_ORIGIN || '*',
  methods: ['GET', 'POST'],
  credentials: true,
};

app.use(cors(corsOptions));
app.use(express.json());

// Health Check
app.get('/health', (_req, res) => {
  res.status(200).json({ status: 'UP', service: 'streaming-service' });
});

// Routes
app.use('/api/v1/audio', audioRoutes);
app.use('/api/v1/audio', ttsRoutes);

// Error Handlers
app.use(handleMulterError);

// Global Error Handler
app.use((err, _req, res, _next) => {
  console.error('[App] Unhandled error:', err);
  return res.status(500).json({ status: 'error', message: err.message || 'Internal server error' });
});

export default app;
export { corsOptions };
