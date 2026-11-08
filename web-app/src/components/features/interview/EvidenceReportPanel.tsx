import { Assessment, EvidenceReport, ObjectiveReport } from '@/services/evidenceInterview';
import { MarkdownContent } from '@/components/common/MarkdownContent';

const labels: Record<Assessment, string> = {
  NOT_ASSESSED: 'Chưa được kiểm tra', INSUFFICIENT_EVIDENCE: 'Chưa đủ bằng chứng',
  NOT_DEMONSTRATED: 'Chưa thể hiện được', DEMONSTRATED_BELOW_TARGET: 'Đã thể hiện ở mức dưới yêu cầu',
  DEMONSTRATED_AT_TARGET: 'Đáp ứng yêu cầu đã kiểm tra', DEMONSTRATED_ABOVE_TARGET: 'Vượt yêu cầu đã kiểm tra',
};
const reasons: Record<string, string> = {
  TIME_BUDGET: 'Hết thời gian', QUESTION_BUDGET: 'Hết ngân sách câu hỏi', USER_STOP: 'Bạn đã kết thúc phiên',
  PLAN_COMPLETE: 'Đã xử lý các mục tiêu trong kế hoạch', MODE_FILTER: 'Ngoài dạng phỏng vấn đã chọn',
  PLAN_BUDGET: 'Ngoài ngân sách phiên', LOCAL_BUDGET: 'Hết lượt cho mục tiêu này', SUFFICIENT_EVIDENCE: 'Đã đủ bằng chứng',
  CRITERION_BUDGET: 'Đã hết lượt kiểm chứng tiêu chí; phần chưa rõ vẫn cần thêm bằng chứng',
  NO_PROGRESS: 'Dừng hỏi tiếp vì chưa thu được thêm bằng chứng',
  NO_INDEPENDENT_CRITERIA_IN_MODE: 'Không còn tiêu chí có thể kiểm chứng độc lập trong dạng phỏng vấn này',
};

function Findings({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return <div><h4 className="font-medium">{title}</h4><ul className="list-disc space-y-2 pl-5">{items.map((item, i) => <li key={i}><MarkdownContent content={item} /></li>)}</ul></div>;
}

function ObjectiveResult({ objective }: { objective: ObjectiveReport }) {
  return <article className="space-y-3 rounded border p-4">
    <h3 className="font-semibold">{objective.claim}</h3>
    {objective.inferred && <p className="text-sm text-slate-600">Mục tiêu hoặc mức yêu cầu được suy luận từ JD.</p>}
    <p>{labels[objective.assessment]}</p>
    <p className="text-sm text-slate-600">{reasons[objective.excluded_reason || objective.stop_reason || '']}</p>
    <Findings title="Đã thể hiện tốt" items={objective.strengths} />
    <Findings title="Hạn chế đã quan sát" items={objective.weaknesses} />
    <Findings title="Cần thêm bằng chứng" items={objective.missing_criteria} />
    {!!objective.criteria?.length && <details><summary>Chi tiết từng tiêu chí</summary>
      <ul className="space-y-2 pt-2">{objective.criteria.map(c => <li key={c.criterion_id}>
        <p>{c.description}: {labels[c.assessment]} ({c.turns_spent} lượt)</p>
        {c.stop_reason && <p className="text-sm text-slate-600">{reasons[c.stop_reason] || c.stop_reason}</p>}
      </li>)}</ul>
    </details>}
    <Findings title="Nội dung cần ôn luyện" items={objective.study_recommendations || []} />
    {objective.evidence.length > 0 && <details><summary>Bằng chứng từ câu trả lời</summary>
      {objective.evidence.map(e => <blockquote className="my-2 border-l-2 pl-3" key={`${e.turn_id}:${e.criterion_id}`}>{e.response_excerpt}<p className="text-sm">{e.rationale}</p></blockquote>)}
    </details>}
  </article>;
}

export function EvidenceReportPanel({ report }: { report: EvidenceReport }) {
  const skills = [...new Set(report.objectives.map(o => o.skill_id))];
  const studyItems = report.study_recommendations?.length
    ? report.study_recommendations
    : [...new Set(report.objectives.flatMap(o => o.study_recommendations || []))];
  return <section className="space-y-6">
    <h1 className="text-2xl font-semibold">Kết quả phỏng vấn theo bằng chứng</h1>
    <p>{reasons[report.termination_reason || ''] || 'Phiên đang diễn ra'}</p>
    <p>Độ bao phủ bằng chứng: {Math.round(report.evidence_coverage * 100)}%. Kết luận áp dụng cho phần đã kiểm tra.</p>
    {skills.map(skill => <section className="space-y-3" key={skill}><h2 className="text-xl font-semibold">{skill}</h2>
      {report.objectives.filter(o => o.skill_id === skill).map(o => <ObjectiveResult key={o.objective_id} objective={o} />)}
    </section>)}
    {studyItems.length > 0 && <section className="space-y-2 rounded border p-4">
      <h2 className="text-lg font-semibold">Tổng hợp nội dung cần ôn luyện</h2>
      <ul className="list-disc space-y-2 pl-5">{studyItems.map((item, i) => <li key={i}><MarkdownContent content={item} /></li>)}</ul>
    </section>}
  </section>;
}
