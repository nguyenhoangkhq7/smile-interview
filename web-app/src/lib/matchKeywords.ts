/**
 * matchKeywords.ts
 *
 * BFF utility for Jobscan-style Visual Keyword Matching.
 *
 * Takes the original raw text of a CV and a Job Description (pre-LLM,
 * as extracted directly from the PDF), then calls the OpenRouter LLM
 * in strict JSON mode to:
 *   1. Identify all skill/keyword requirements in the JD.
 *   2. Determine which are present (matched) or absent (missing) in the CV.
 *   3. Classify each as "hard" (technical) or "soft" skill.
 *
 * Returns a KeywordMatchResult. On any LLM failure or JSON parse error
 * the function falls back gracefully to { matching_skills: [], missing_skills: [] }.
 *
 * LLM latency: ~1–3 seconds (OpenRouter / free-tier model).
 */

export interface SkillEntry {
  /** Unique visual tag ID (e.g. "ms1", "msk2") */
  id: string;
  /** The canonical keyword exactly as it appears in the JD */
  keyword: string;
  /** "hard" for technical skills, "soft" for interpersonal/behavioral skills */
  category: 'hard' | 'soft';
  /** Optional semantically equivalent variants used to scan the CV */
  variants?: string[];
}

export interface KeywordMatchResult {
  /** Keywords present in the JD that were found (or semantically matched) in the CV */
  matching_skills: SkillEntry[];
  /** Keywords present in the JD that are absent from the CV */
  missing_skills: SkillEntry[];
}

const FALLBACK: KeywordMatchResult = { matching_skills: [], missing_skills: [] };

/**
 * Extract and match skill keywords between a JD and a CV using an LLM call.
 *
 * @param rawResumeText  Pre-LLM plain text extracted from the candidate's CV/resume PDF.
 * @param rawJdText      Pre-LLM plain text extracted from the Job Description PDF/text.
 * @returns              A KeywordMatchResult categorising skills as matching or missing.
 */
export async function matchKeywords(
  rawResumeText: string,
  rawJdText: string
): Promise<KeywordMatchResult> {
  const apiKey = process.env.LLM_API_KEY;
  const apiUrl = process.env.LLM_API_URL || 'https://openrouter.ai/api/v1';
  const model = process.env.LLM_MODEL || 'poolside/laguna-xs-2.1:free';

  if (!apiKey) {
    console.error('[matchKeywords] LLM_API_KEY is not set. Returning empty result.');
    return FALLBACK;
  }

  // Truncate inputs to avoid excessive token usage (~4000 chars each is enough)
  const cvSnippet = rawResumeText.slice(0, 4000);
  const jdSnippet = rawJdText.slice(0, 4000);

  const systemPrompt = `You are a technical recruiter assistant specialised in resume screening.
Your task is to compare a Job Description (JD) against a Candidate Resume (CV) and identify skill keywords.

You MUST return a valid JSON object strictly matching this schema (no markdown, no extra keys):
{
  "matching_skills": [
    { "id": "ms1", "keyword": "string", "category": "hard" | "soft", "variants": ["string"] }
  ],
  "missing_skills": [
    { "id": "msk1", "keyword": "string", "category": "hard" | "soft" }
  ]
}

Rules:
- Extract every distinct technical skill, tool, framework, methodology, certification, and soft skill from the JD.
- For each keyword, check if it OR a close semantic variant (e.g. "ReactJS" vs "React") appears in the CV text.
- If found (even as a variant): include it in "matching_skills" with any detected variant forms in the "variants" array.
- If NOT found: include it in "missing_skills".
- Classify "hard" for technical/tool/framework/language/platform skills.
- Classify "soft" for interpersonal, communication, behavioural, or process skills.
- IDs for matching_skills: ms1, ms2, ms3 ... (sequential).
- IDs for missing_skills: msk1, msk2, msk3 ... (sequential).
- Do NOT invent keywords not present in the JD.
- Return ONLY the JSON object. No explanation, no markdown fences.`;

  const userPrompt = `### JOB DESCRIPTION ###
${jdSnippet}

### CANDIDATE RESUME ###
${cvSnippet}`;

  try {
    const response = await fetch(`${apiUrl}/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model,
        messages: [
          { role: 'system', content: systemPrompt },
          { role: 'user', content: userPrompt },
        ],
        // Enforce strict JSON output - avoids markdown fences and free-text responses
        response_format: { type: 'json_object' },
        temperature: 0.0,
        max_tokens: 2048,
      }),
    });

    if (!response.ok) {
      const errText = await response.text();
      console.error(`[matchKeywords] LLM API returned ${response.status}:`, errText);
      return FALLBACK;
    }

    const data = await response.json();
    const rawContent: string | undefined = data?.choices?.[0]?.message?.content;

    if (!rawContent) {
      console.error('[matchKeywords] LLM returned empty content.');
      return FALLBACK;
    }

    // Parse and validate the returned JSON
    let parsed: { matching_skills?: unknown[]; missing_skills?: unknown[] } | null = null;
    try {
      parsed = JSON.parse(rawContent) as { matching_skills?: unknown[]; missing_skills?: unknown[] };
    } catch (parseErr) {
      console.error('[matchKeywords] Failed to parse LLM JSON response:', parseErr, '\nRaw:', rawContent);
      return FALLBACK;
    }

    // Basic structural validation before returning
    const matchingSkills: SkillEntry[] = Array.isArray(parsed?.matching_skills)
      ? (parsed.matching_skills as SkillEntry[]).filter(
          (s) => typeof s?.id === 'string' && typeof s?.keyword === 'string'
        )
      : [];

    const missingSkills: SkillEntry[] = Array.isArray(parsed?.missing_skills)
      ? (parsed.missing_skills as SkillEntry[]).filter(
          (s) => typeof s?.id === 'string' && typeof s?.keyword === 'string'
        )
      : [];

    console.log(
      `[matchKeywords] Done. Matching: ${matchingSkills.length}, Missing: ${missingSkills.length}`
    );

    return { matching_skills: matchingSkills, missing_skills: missingSkills };
  } catch (err) {
    console.error('[matchKeywords] Unexpected error during LLM call:', err);
    return FALLBACK;
  }
}
