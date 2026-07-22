import { transcribeAudio } from './audio.service.js';

/**
 * POST /api/v1/audio/transcribe
 *
 * Accepts a single audio file via multipart/form-data (field name: "audio"),
 * validates the upload, delegates to the Audio Service for Whisper STT
 * transcription, and returns the resulting text as a standard JSON response.
 *
 * @param {import('express').Request}  req
 * @param {import('express').Response} res
 */
export const transcribe = async (req, res) => {
  // --- 1. Validate the uploaded file ---
  if (!req.file) {
    return res.status(400).json({
      status: 'error',
      message: 'No audio file provided. Upload a file using the "audio" field.',
    });
  }

  if (req.file.size === 0) {
    return res.status(400).json({
      status: 'error',
      message: 'Uploaded audio file is empty.',
    });
  }

  // --- 2. Delegate to the Audio Service ---
  try {
    const transcribedText = await transcribeAudio(
      req.file.buffer,
      req.file.originalname
    );

    // --- 3. Return standard success response ---
    return res.status(200).json({
      status: 'success',
      text: transcribedText,
    });
  } catch (error) {
    console.error('[AudioController] Transcription failed:', error.message);

    // Distinguish between client-facing bad requests and internal errors
    const isClientError = error.message.includes('not configured');
    return res.status(isClientError ? 503 : 502).json({
      status: 'error',
      message: error.message,
    });
  }
};

/**
 * GET /api/v1/audio/stream-transcribe
 *
 * Accepts query parameter `text` and returns a Server-Sent Events (SSE) stream
 * that types out each word of the text at 80ms intervals.
 *
 * @param {import('express').Request}  req
 * @param {import('express').Response} res
 */
export const streamTranscribe = (req, res) => {
  const text = req.query.text || '';

  res.writeHead(200, {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'Access-Control-Allow-Origin': '*',
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
};
