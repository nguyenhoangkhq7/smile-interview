import { Router } from 'express';
import { transcribe } from './audio.controller.js';
import { upload } from './upload.middleware.js';

const router = Router();

// POST /api/v1/audio/transcribe
// Accepts multipart/form-data with a single audio file under field name "audio"
router.post('/transcribe', upload.single('audio'), transcribe);

// GET /api/v1/audio/stream-transcribe
// Accepts query parameter text
// Returns Server-Sent Events stream typing out each word at 80ms intervals
router.get('/stream-transcribe', (req, res) => {
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

export default router;
