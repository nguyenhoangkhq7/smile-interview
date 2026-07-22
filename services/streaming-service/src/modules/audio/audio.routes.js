import { Router } from 'express';
import { transcribe, streamTranscribe } from './audio.controller.js';
import { upload } from './upload.middleware.js';

const router = Router();

// POST /api/v1/audio/transcribe
// Accepts multipart/form-data with a single audio file under field name "audio"
router.post('/transcribe', upload.single('audio'), transcribe);

// GET /api/v1/audio/stream-transcribe
// Accepts query parameter text
// Returns Server-Sent Events stream typing out each word at 80ms intervals
router.get('/stream-transcribe', streamTranscribe);

export default router;
