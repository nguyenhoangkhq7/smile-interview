import { synthesizeSpeech } from '../services/tts.service.js';

/**
 * POST /api/v1/audio/synthesize
 *
 * Accepts a JSON body `{ "text": "...", "voice": "..." }`, validates the
 * input, delegates to the TTS Service, and streams the resulting MP3 audio
 * bytes directly back to the client.
 *
 * @param {import('express').Request}  req
 * @param {import('express').Response} res
 */
export const synthesizeAudio = async (req, res) => {
  const { text, voice } = req.body ?? {};

  // --- 1. Validate required input ---
  if (!text || typeof text !== 'string' || text.trim().length === 0) {
    return res.status(400).json({
      status: 'error',
      message: '"text" field is required and must be a non-empty string.',
    });
  }

  // --- 2. Delegate to the TTS Service ---
  try {
    const audioArrayBuffer = await synthesizeSpeech(text.trim(), voice);

    // --- 3. Stream raw MP3 bytes back to the client ---
    res.set({
      'Content-Type': 'audio/mpeg',
      'Content-Length': audioArrayBuffer.byteLength,
      // Allow browsers to display a filename when the user downloads the result
      'Content-Disposition': 'inline; filename="speech.mp3"',
    });

    return res.send(Buffer.from(audioArrayBuffer));
  } catch (error) {
    console.error('[TtsController] Speech synthesis failed:', error.message);

    const isNetworkError = error.message.startsWith('Network error');
    return res.status(isNetworkError ? 503 : 502).json({
      status: 'error',
      message: error.message,
    });
  }
};
