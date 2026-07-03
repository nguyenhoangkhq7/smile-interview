import { Router } from 'express';
import { synthesizeAudio } from './tts.controller.js';

const router = Router();

// POST /api/v1/audio/synthesize
// Accepts JSON body: { "text": "...", "voice": "af_bella" }
// Returns raw MP3 bytes with Content-Type: audio/mpeg
router.post('/synthesize', synthesizeAudio);

export default router;
