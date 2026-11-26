import { Award } from 'lucide-react';
import { assessmentLabel, terminationLabel } from './sessionDisplay';
import type { InterviewDetail } from './types';

export default function InterviewEvaluation({ report }: { report: InterviewDetail['report'] }) {
  const objectives = report?.objectives ?? [];
  const achieved = objectives.filter(({ assessment }) => assessment === 'DEMONSTRATED_AT_TARGET'
    || assessment === 'DEMONSTRATED_ABOVE_TARGET').length;
  const reason = terminationLabel(report?.terminationReason);

  return (
    <section className="space-y-4 rounded-xl bg-white p-5 shadow-xs">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 font-semibold"><Award className="size-5 text-[#ad2c00]" /> Kết quả đánh giá năng lực</h2>
        {objectives.length > 0 && <span className="rounded-full bg-green-100 px-2 py-1 text-xs text-green-800">
          {achieved}/{objectives.length} đạt yêu cầu
        </span>}
      </div>
      {reason && <p className="text-sm text-[#5c4039]">{reason}</p>}
      {report?.overallScore != null && <p className="text-sm font-semibold">Điểm tổng hợp {report.overallScore}</p>}
      {report?.feedback && <p className="whitespace-pre-wrap break-words text-sm">{report.feedback}</p>}
      {objectives.map((objective, index) => (
        <div key={index} className="space-y-1.5 rounded-lg bg-[#f1f3ff] p-3 text-sm">
          <h3 className="font-semibold">{objective.skill}</h3>
          {objective.assessment && <p className="text-xs font-medium text-[#186392]">
            {assessmentLabel(objective.assessment)}
          </p>}
          {objective.claim && <p className="break-words">{objective.claim}</p>}
          {[...objective.strengths, ...objective.weaknesses].map((entry, item) =>
            <p key={item} className="break-words text-xs text-[#5c4039]">{entry}</p>)}
        </div>
      ))}
      {!objectives.length && report?.overallScore == null && !report?.feedback
        && <p className="text-sm text-[#5c4039]">Chưa có kết quả đánh giá được lưu.</p>}
    </section>
  );
}
