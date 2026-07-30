/**
 * Utility functions for exporting data to various formats (CSV, etc.)
 */

export interface QuestionBankItem {
  id?: string;
  code?: string;
  type?: string;
  question_type?: string;
  questionType?: string;
  difficulty?: string;
  topic?: string;
  topicTag?: string;
  topic_tag?: string;
  question?: string | { question?: string; topic?: string };
  content?: string;
  hints?: string[] | string;
  goodAnswerSignals?: string[];
  [key: string]: unknown;
}

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
export function exportQuestionBankToCSV(questionBank: any[], sessionId: string): void {
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
    'Gợi ý / Hints',
  ];

  const rows = questionBank.map((q, index) => {
    // Column A: Code/ID
    const code = q.id || q.code || `Q${String(index + 1).padStart(3, '0')}`;

    // Column B: Type
    const type = q.type || q.question_type || q.questionType || '';

    // Column C: Difficulty
    const difficulty = q.difficulty || '';

    // Column D: Topic
    const topic = q.topic || q.topicTag || q.topic_tag || (typeof q.question === 'object' && q.question !== null ? q.question.topic : '') || '';

    // Column E: Question Content
    let questionText = '';
    if (typeof q.question === 'object' && q.question !== null) {
      questionText = q.question.question || '';
    } else if (typeof q.question === 'string') {
      questionText = q.question;
    } else if (typeof q.content === 'string') {
      questionText = q.content;
    }

    // Column F: Hints / Suggestions
    let hintsText = '';
    if (Array.isArray(q.hints)) {
      hintsText = q.hints.join('; ');
    } else if (typeof q.hints === 'string') {
      hintsText = q.hints;
    } else if (Array.isArray(q.goodAnswerSignals)) {
      hintsText = q.goodAnswerSignals.join('; ');
    }

    return [code, type, difficulty, topic, questionText, hintsText]
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
