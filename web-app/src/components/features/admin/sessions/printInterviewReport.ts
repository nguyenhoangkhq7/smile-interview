import { percent } from '@/components/features/interview/result/resultData';
import { assessmentLabel, dateLabel, durationLabel, modeLabel, statusLabels, terminationLabel } from './sessionDisplay';
import type { InterviewDetail } from './types';

export function printInterviewReport(detail: InterviewDetail) {
  if (!detail.finalized) return false;
  const popup = window.open('', '_blank');
  if (!popup) return false;
  popup.opener = null;
  const doc = popup.document;
  doc.documentElement.lang = 'vi';
  doc.title = 'Báo cáo phiên phỏng vấn ' + detail.session.id;
  const style = doc.createElement('style');
  style.textContent = '@page{size:A4;margin:18mm}body{font:11pt/1.45 Arial,sans-serif;color:#182032}' +
    'h1{font-size:22pt}h2{font-size:15pt;border-bottom:1px solid #dbe2f5;padding-bottom:5pt}' +
    'h2,h3{break-after:avoid}p{white-space:pre-wrap;overflow-wrap:anywhere;orphans:2;widows:2}';
  doc.head.append(style);

  function add(tag: 'h1' | 'h2' | 'h3' | 'p', content: string | number | null | undefined) {
    if (content == null || content === '') return;
    const node = doc.createElement(tag);
    node.textContent = String(content);
    doc.body.append(node);
  }

  const { session, inputs, transcript, report, matching } = detail;
  const score = percent(matching.score);
  add('h1', 'Báo cáo phiên phỏng vấn');
  add('p', [
    session.candidateName, session.roleTitle, inputs.company, session.id,
    statusLabels[session.status], modeLabel(session.mode), dateLabel(session.endedAt), durationLabel(session),
  ].filter(Boolean).join(' · '));
  if (score !== null) add('p', 'Độ khớp CV–JD ' + score + '%');
  if (report) {
    add('h2', 'Kết quả đánh giá');
    add('p', terminationLabel(report.terminationReason));
    if (report.overallScore !== null) add('p', 'Điểm tổng hợp ' + report.overallScore);
    add('p', report.feedback);
    for (const objective of report.objectives) {
      add('h3', objective.skill + (objective.assessment ? ' · ' + assessmentLabel(objective.assessment) : ''));
      add('p', objective.claim);
      add('p', objective.strengths.join('\n'));
      add('p', objective.weaknesses.join('\n'));
    }
  }
  if (transcript) {
    add('h2', 'Nội dung hỏi đáp');
    add('p', transcript.opening);
    if (transcript.introduction) {
      add('h3', 'Giới thiệu của ứng viên');
      add('p', transcript.introduction);
    }
    transcript.turns.forEach((turn, index) => {
      add('h3', 'Lượt ' + (index + 1) + (turn.skill ? ' · ' + turn.skill : ''));
      if (turn.question) add('p', 'Câu hỏi\n' + turn.question);
      if (turn.answer) add('p', 'Câu trả lời\n' + turn.answer);
      add('p', turn.feedback);
      if (turn.score !== null) add('p', 'Điểm ' + turn.score);
      add('p', turn.strengths);
      add('p', turn.improvements);
      add('p', turn.suggestedAnswer);
      for (const evidence of turn.evidence) {
        if (evidence.excerpt) add('p', 'Bằng chứng\n' + evidence.excerpt);
        add('p', evidence.rationale);
      }
    });
    if (transcript.closing) {
      add('h3', 'Kết thúc');
      add('p', transcript.closing);
    }
  }
  popup.requestAnimationFrame(() => {
    popup.focus();
    popup.print();
  });
  return true;
}
