/**
 * TTS Service — Handles communication with the Speaches TTS API.
 *
 * Uses Node 24's native `fetch` API exclusively.
 * The Speaches server exposes an OpenAI-compatible `/v1/audio/speech` endpoint,
 * so no client SDK or external library is required.
 */

const TTS_API_URL =
  process.env.TTS_API_URL ||
  'http://ai-inference-service:8000/v1/audio/speech';

// The Speaches TTS model — defaults to the Vietnamese Piper model
const TTS_MODEL = process.env.TTS_MODEL || 'speaches-ai/piper-vi_VN-vais1000-medium';

// Dictionary mapping common English IT terms to their Vietnamese phonetic pronunciation equivalents.
const IT_TERMS_MAP = {
  'Backend': 'Bách-en',
  'Frontend': 'Phờ-rôn-en',
  'Java': 'Gia-va',
  'Spring Boot': 'Xờ-pờ-ring Bút',
  'RESTful API': 'Rét-phun Ê-pi-ai',
  'MySQL': 'Mai ét-kiu-eo',
  'Git': 'Gít',
  'Docker': 'Đốc-cơ',
  'IT': 'Ai-ti',
  'React': 'Ri-ách',
  'Node.js': 'Nốt-giây-ét',
};

/**
 * Normalizes English IT terms into Vietnamese phonetic equivalents.
 *
 * It uses case-insensitive word boundaries (\b) to replace exact word matches
 * (e.g. matching "Git" but not part of "Github"). Longer keys are matched
 * first to avoid premature replacements (e.g. "Spring Boot" before "Spring").
 *
 * @param {string} text - The raw input text.
 * @returns {string} - The normalized text.
 */
export const normalizeText = (text) => {
  if (!text) return text;

  let normalized = text;

  // Sort keys by length descending to match multi-word phrases before single words
  const sortedKeys = Object.keys(IT_TERMS_MAP).sort((a, b) => b.length - a.length);

  for (const key of sortedKeys) {
    const replacement = IT_TERMS_MAP[key];
    // Escape special regex characters in the dictionary key (e.g. the dot in Node.js)
    const escapedKey = key.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&');
    const regex = new RegExp(`\\b${escapedKey}\\b`, 'gi');
    normalized = normalized.replace(regex, replacement);
  }

  return normalized;
};

/**
 * Synthesizes text into speech by forwarding the request to the TTS API.
 *
 * @param {string} text    - The plain text to synthesize.
 * @param {string} voiceId - The voice identifier (ignored by Piper, but kept for compatibility).
 * @returns {Promise<ArrayBuffer>} - Raw MP3 audio bytes as an ArrayBuffer.
 * @throws {Error} - Throws a descriptive error on network failure or API error.
 */
export const synthesizeSpeech = async (text, voiceId = 'af_bella') => {
  // Pre-process text to convert English IT terms into Vietnamese phonetics
  const normalizedInput = normalizeText(text);
  console.log(`[TTS Service] Original text: "${text}" -> Normalized: "${normalizedInput}"`);

  // Build the OpenAI-compatible JSON payload
  const payload = {
    model: TTS_MODEL,
    input: normalizedInput,
    voice: voiceId,
    response_format: 'mp3',
  };

  let response;
  try {
    response = await fetch(TTS_API_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: 'Bearer dummy_key_for_local',
      },
      body: JSON.stringify(payload),
    });
  } catch (networkError) {
    throw new Error(
      `Network error while reaching TTS API: ${networkError.message}`
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
      `TTS API responded with status ${response.status}: ${errorBody}`
    );
  }

  // Return the raw binary audio data as an ArrayBuffer
  return response.arrayBuffer();
};
