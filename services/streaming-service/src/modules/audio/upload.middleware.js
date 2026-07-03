import multer from 'multer';

// Audio clips are short-lived, so we hold them in RAM rather than writing to
// disk. The buffer is passed directly to the Whisper API and then discarded.
export const upload = multer({
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

// Middleware to handle Multer errors cleanly
export const handleMulterError = (err, _req, res, next) => {
  if (err instanceof multer.MulterError || err.message?.startsWith('Unsupported audio format')) {
    return res.status(400).json({ status: 'error', message: err.message });
  }
  next(err);
};
