/**
 * Audio Service — Handles communication with the Whisper STT API.
 *
 * Uses Node 24's native `fetch` and `FormData` APIs exclusively.
 * No external HTTP client or form-data libraries required.
 */

const WHISPER_API_URL =
  process.env.WHISPER_API_URL ||
  'https://api.openai.com/v1/audio/transcriptions';
const WHISPER_API_KEY = process.env.WHISPER_API_KEY;

/**
 * Transcribes an audio file buffer by forwarding it to the Whisper API.
 *
 * @param {Buffer} fileBuffer   - The raw audio file buffer from multer memory storage.
 * @param {string} originalName - The original filename (used to infer MIME type).
 * @returns {Promise<string>}   - The transcribed text string.
 * @throws {Error}              - Throws a descriptive error on API failure.
 */
export const transcribeAudio = async (fileBuffer, originalName) => {
  if (!WHISPER_API_KEY) {
    throw new Error(
      'WHISPER_API_KEY environment variable is not configured.'
    );
  }

  // Derive MIME type from the file extension; default to webm for browser recordings
  const extension = originalName.split('.').pop().toLowerCase();
  const mimeTypeMap = {
    mp3: 'audio/mpeg',
    mp4: 'audio/mp4',
    mpeg: 'audio/mpeg',
    mpga: 'audio/mpeg',
    m4a: 'audio/mp4',
    ogg: 'audio/ogg',
    wav: 'audio/wav',
    webm: 'audio/webm',
    flac: 'audio/flac',
  };
  const mimeType = mimeTypeMap[extension] ?? 'audio/webm';

  // Speaches (local) uses HuggingFace model IDs; OpenAI cloud uses 'whisper-1'.
  // WHISPER_MODEL defaults to the 'base' variant — fast enough for CPU, good accuracy.
  // Override with e.g. WHISPER_MODEL=Systran/faster-whisper-small for higher accuracy.
  const whisperModel = process.env.WHISPER_MODEL || 'Systran/faster-whisper-base';

  // Build a native Blob from the buffer, then append it to a native FormData
  const audioBlob = new Blob([fileBuffer], { type: mimeType });

  const formData = new FormData();
  formData.append('file', audioBlob, originalName);
  formData.append('model', whisperModel);
  formData.append('prompt', 'Cao Thanh Đông, Backend, Java, Spring Boot, RESTful API, MySQL, Git, Docker, IT, Công nghệ thông tin');

  let response;
  try {
    response = await fetch(WHISPER_API_URL, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${WHISPER_API_KEY}`,
        // NOTE: Do NOT set 'Content-Type' manually — fetch sets it automatically
        // with the correct multipart boundary when a FormData body is used.
      },
      body: formData,
    });
  } catch (networkError) {
    throw new Error(
      `Network error while reaching Whisper API: ${networkError.message}`
    );
  }

  if (!response.ok) {
    let errorBody = '';
    try {
      const errorJson = await response.json();
      errorBody = errorJson?.error?.message ?? JSON.stringify(errorJson);
    } catch {
      errorBody = await response.text();
    }
    throw new Error(
      `Whisper API responded with status ${response.status}: ${errorBody}`
    );
  }

  const data = await response.json();

  if (!data?.text) {
    throw new Error(
      'Whisper API returned an unexpected response format (missing "text" field).'
    );
  }

  return data.text;
};
