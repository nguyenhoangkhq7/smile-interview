export interface QuestionBankItem {
  id?: string;
  code?: string;
  type?: string;
  question_type?: string;
  questionType?: string;
  difficulty?: string;
  level?: string;
  topic?: string;
  topicTag?: string;
  topic_tag?: string;
  question?: string | { question?: string; topic?: string };
  content?: string;
  answer?: string;
  score?: number | string;
  hints?: string[] | string;
  goodAnswerSignals?: string[];
  good_answer_signals?: string[];
  isDeepDive?: boolean;
  evaluation?: string;
  strengths?: string;
  improvements?: string;
  suggestedAnswer?: string;
  suggested_answer?: string;
  hrRating?: number;
  hrFeedback?: string;
}

export type ExportableQuestionItem = QuestionBankItem;

/**
 * Escapes a single cell value for CSV compliant format.
 * - Wraps string in double quotes
 * - Escapes existing double quotes by doubling them ("")
 * - Handles null/undefined gracefully
 */
function escapeCSVField(value: unknown): string {
  if (value === null || value === undefined) {
    return '""';
  }
  const str = String(value).replace(/"/g, '""');
  return `"${str}"`;
}

/**
 * Exports a question bank array to a downloadable CSV file.
 * UTF-8 BOM (\uFEFF) is added so Microsoft Excel opens Vietnamese characters correctly.
 * 
 * Column mapping:
 * - Column A: Mã câu hỏi (e.g. Q001)
 * - Column B: Loại (e.g. behavioural, technical, coding)
 * - Column C: Độ khó (e.g. easy, medium, hard)
 * - Column D: Chủ đề (topic)
 * - Column E: Nội dung câu hỏi (question)
 * - Column F: Gợi ý / Hints (joined by "; ")
 */
export function exportQuestionBankToCSV(questionBank: ExportableQuestionItem[], sessionId: string): void {
  if (!questionBank || questionBank.length === 0) {
    console.warn('[exportUtils] Question bank is empty. Export cancelled.');
    return;
  }

  const headers = [
    'Mã câu hỏi',
    'Loại',
    'Độ khó',
    'Chủ đề',
    'Nội dung câu hỏi',
    'Câu trả lời của ứng viên',
    'Điểm số',
    'Nhận xét / Phân tích AI',
    'Gợi ý câu trả lời chuẩn',
  ];

  const rows = questionBank.map((q, index) => {
    // Helper to infer topic from question content if topic is empty
    const inferTopic = (text: string): string => {
      const lower = text.toLowerCase();
      if (lower.includes('agile') || lower.includes('scrum') || lower.includes('user story') || lower.includes('sprint')) {
        return 'Quy trình Agile / Scrum';
      }
      if (lower.includes('api') || lower.includes('rest') || lower.includes('postman') || lower.includes('swagger') || lower.includes('openapi')) {
        return 'Kiểm thử API / RESTful';
      }
      if (lower.includes('startup') || lower.includes('nguồn lực') || lower.includes('kế hoạch') || lower.includes('yêu cầu')) {
        return 'Quản lý & Kế hoạch QA';
      }
      if (lower.includes('code') || lower.includes('function') || lower.includes('script') || lower.includes('lập trình')) {
        return 'Lập trình & Automation';
      }
      if (lower.includes('test case') || lower.includes('edge case') || lower.includes('kiểm thử')) {
        return 'Kỹ thuật Kiểm thử';
      }
      return 'Chuyên môn QA / IT';
    };

    // Column A: Code/ID
    const code = q.id || q.code || `Q${String(index + 1).padStart(3, '0')}`;

    // Column E: Question Content (Extracted early for inferencing)
    let questionText = '';
    if (typeof q.question === 'object' && q.question !== null) {
      questionText = (q.question as { question?: string }).question || '';
    } else if (typeof q.question === 'string') {
      questionText = q.question;
    } else if (typeof q.content === 'string') {
      questionText = q.content;
    }

    // Column B: Type
    const rawType = q.type || q.question_type || q.questionType;
    const type = rawType || (q.isDeepDive ? 'Chuyên sâu (Follow-up)' : 'Chuyên môn (Core)');

    // Column C: Difficulty
    const rawDifficulty = q.difficulty || q.level;
    const difficulty = rawDifficulty || (q.isDeepDive ? 'Nâng cao' : 'Trung bình');

    // Column D: Topic
    const rawTopic = q.topic || q.topicTag || q.topic_tag || (typeof q.question === 'object' && q.question !== null ? (q.question as { topic?: string }).topic : '');
    const topic = rawTopic || (questionText ? inferTopic(questionText) : 'Tổng quan');

    // Column F: Candidate Answer
    const candidateAnswer = q.answer !== undefined && q.answer !== null && String(q.answer).trim() !== ''
      ? String(q.answer)
      : '[Chưa có câu trả lời]';

    // Column G: Score
    const score = q.score !== undefined && q.score !== null ? String(q.score) : '';

    // Column H: AI Feedback & Analysis
    const feedbackParts: string[] = [];
    if (q.strengths) feedbackParts.push(`Điểm mạnh: ${q.strengths}`);
    if (q.improvements) feedbackParts.push(`Cần cải thiện: ${q.improvements}`);
    if (q.evaluation) feedbackParts.push(`Đánh giá: ${q.evaluation}`);
    const aiAnalysis = feedbackParts.join(' | ');

    // Column I: Suggested Answer / Hints
    let suggestedAnswerText = '';
    if (q.suggestedAnswer || q.suggested_answer) {
      suggestedAnswerText = String(q.suggestedAnswer || q.suggested_answer);
    } else if (Array.isArray(q.goodAnswerSignals) && q.goodAnswerSignals.length > 0) {
      suggestedAnswerText = q.goodAnswerSignals.join('; ');
    } else if (Array.isArray(q.good_answer_signals) && q.good_answer_signals.length > 0) {
      suggestedAnswerText = q.good_answer_signals.join('; ');
    } else if (Array.isArray(q.hints) && q.hints.length > 0) {
      suggestedAnswerText = q.hints.join('; ');
    } else if (typeof q.hints === 'string') {
      suggestedAnswerText = q.hints;
    }

    return [code, type, difficulty, topic, questionText, candidateAnswer, score, aiAnalysis, suggestedAnswerText]
      .map(escapeCSVField)
      .join(',');
  });

  const csvHeaderLine = headers.map(escapeCSVField).join(',');
  const csvContent = '\uFEFF' + [csvHeaderLine, ...rows].join('\r\n');

  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');

  const cleanSessionId = (sessionId || 'export').trim().replace(/[^a-zA-Z0-9_-]/g, '_');
  const filename = `danh_sach_cau_hoi_${cleanSessionId}.csv`;

  link.href = url;
  link.setAttribute('download', filename);
  document.body.appendChild(link);
  link.click();

  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
