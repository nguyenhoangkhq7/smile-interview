'use client';

import { useState } from 'react';
import { MessagesSquare } from 'lucide-react';
import type { InterviewDetail, InterviewTurn } from './types';

export const performanceLabels: Record<string, string> = {
  BELOW: 'Dưới yêu cầu', AT_TARGET: 'Đạt yêu cầu', ABOVE: 'Vượt yêu cầu', UNDETERMINED: 'Chưa xác định',
};

function TurnCard({ turn, index }: { turn: InterviewTurn; index: number }) {
  const answer = turn.answer ?? '';
  const match = turn.evidence.find((evidence) => evidence.excerpt && answer.includes(evidence.excerpt))?.excerpt;
  const offset = match ? answer.indexOf(match) : -1;

  return <article className="space-y-4 rounded-xl border border-[#edf0ff] p-4">
    <h3 className="font-semibold">Lượt {index + 1}{turn.skill ? ' · ' + turn.skill : ''}</h3>
    {turn.question && <div className="rounded-xl bg-[#f1f3ff] p-4">
      <h4 className="mb-1 text-xs font-semibold text-[#186392]">Câu hỏi</h4>
      <p className="whitespace-pre-wrap break-words">{turn.question}</p>
    </div>}
    <div className="rounded-xl border border-[#edf0ff] p-4">
      <h4 className="mb-1 text-xs font-semibold text-[#ad2c00]">Câu trả lời</h4>
      <p className="whitespace-pre-wrap break-words">{match && offset >= 0
        ? <>{answer.slice(0, offset)}<mark className="rounded bg-[#ffdfd1] text-[#722600]">{match}</mark>{answer.slice(offset + match.length)}</>
        : answer || 'Chưa có câu trả lời được lưu.'}</p>
    </div>
    {([
      ['Phản hồi', turn.feedback], ['Điểm', turn.score],
      ['Điểm mạnh', turn.strengths], ['Cần cải thiện', turn.improvements], ['Gợi ý trả lời', turn.suggestedAnswer],
    ] as const).map(([label, value]) => value != null && <div key={label}>
      <h4 className="text-xs font-semibold text-[#5c4039]">{label}</h4>
      <p className="whitespace-pre-wrap break-words text-sm">{value}</p>
    </div>)}
    {turn.evidence.length > 0 && <section className="space-y-2">
      <h4 className="font-medium">Bằng chứng đánh giá</h4>
      {turn.evidence.map((item, index) => (
        <div key={index} className="space-y-1 rounded-lg bg-[#f1f3ff] px-3 py-2 text-sm">
          <p className="text-xs font-semibold">{[item.criterionId, item.performance && performanceLabels[item.performance]]
            .filter(Boolean).join(' · ')}</p>
          {item.excerpt && <blockquote className="whitespace-pre-wrap break-words text-[#722600]">{item.excerpt}</blockquote>}
          {item.rationale && <p className="break-words">{item.rationale}</p>}
        </div>
      ))}
    </section>}
  </article>;
}

export default function InterviewTranscript({ transcript }: { transcript: InterviewDetail['transcript'] }) {
  const [selected, setSelected] = useState('all');
  if (!transcript || (!transcript.turns.length && !transcript.opening && !transcript.introduction && !transcript.closing)) {
    return <p className="rounded-xl bg-white p-5 text-sm text-[#5c4039]">Phiên chưa có nội dung hỏi đáp đã lưu.</p>;
  }

  return (
    <section className="space-y-4 rounded-xl bg-white p-5 shadow-xs">
      <h2 className="flex items-center gap-2 text-lg font-semibold">
        <MessagesSquare className="size-5 text-[#ad2c00]" /> Nội dung hỏi đáp và bằng chứng
      </h2>
      {transcript.turns.length > 0 && <div role="group" aria-label="Chọn lượt hỏi đáp" className="flex gap-2 overflow-x-auto pb-2">
        {[{ id: 'all', label: 'Tất cả (' + transcript.turns.length + ')' }, ...transcript.turns.map((turn, index) =>
          ({ id: turn.id, label: 'Lượt ' + (index + 1) + (turn.skill ? ' · ' + turn.skill : '') }))].map((item) => (
          <button type="button" key={item.id} aria-pressed={selected === item.id} onClick={() => setSelected(item.id)}
            className={selected === item.id
              ? 'max-w-56 shrink-0 truncate rounded-lg bg-[#186392] px-3 py-2 text-xs text-white'
              : 'max-w-56 shrink-0 truncate rounded-lg bg-[#f1f3ff] px-3 py-2 text-xs'}>
            {item.label}
          </button>
        ))}
      </div>}
      {selected === 'all' && (transcript.opening || transcript.introduction) && (
        <article className="space-y-3 rounded-xl border border-[#edf0ff] p-4">
          <h3 className="font-semibold">Mở đầu</h3>
          {transcript.opening && <p className="whitespace-pre-wrap break-words">{transcript.opening}</p>}
          {transcript.introduction && <div>
            <h4 className="mb-1 text-xs font-semibold text-[#ad2c00]">Ứng viên tự giới thiệu</h4>
            <p className="whitespace-pre-wrap break-words">{transcript.introduction}</p>
          </div>}
        </article>
      )}
      {transcript.turns.map((turn, index) => (selected === 'all' || selected === turn.id)
        && <TurnCard turn={turn} index={index} key={turn.id} />)}
      {selected === 'all' && transcript.closing && <article className="space-y-2 rounded-xl border border-[#edf0ff] p-4">
        <h3 className="font-semibold">Kết thúc</h3>
        <p className="whitespace-pre-wrap break-words">{transcript.closing}</p>
      </article>}
    </section>
  );
}
