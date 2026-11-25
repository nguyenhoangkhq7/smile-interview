'use client';

import { useState } from 'react';
import { FileDown, RefreshCw } from 'lucide-react';
import { percent } from '@/components/features/interview/result/resultData';
import InterviewEvaluation from './InterviewEvaluation';
import InterviewTranscript from './InterviewTranscript';
import { printInterviewReport } from './printInterviewReport';
import { dateLabel, durationLabel, modeLabel, statusLabels, statusStyle } from './sessionDisplay';
import type { InterviewDetail } from './types';

const stages = [
  ['inputs', 'CV & JD đầu vào'],
  ['matching', 'Đối sánh & Skill Gap'],
  ['blueprint', 'Cấu hình phiên'],
  ['transcript', 'Transcript & Bằng chứng'],
  ['evaluation', 'Đánh giá cuối'],
] as const;
type Stage = typeof stages[number][0];

function Fields({ title, items }: { title: string; items: readonly (readonly [string, string | number | null])[] }) {
  const known = items.filter(([, value]) => value !== null);
  return (
    <section className="space-y-3 rounded-xl bg-white p-5 shadow-xs">
      <h2 className="font-semibold">{title}</h2>
      {known.length ? <dl className="grid gap-4 sm:grid-cols-2">
        {known.map(([label, value]) => <div key={label}>
          <dt className="text-xs text-[#5c4039]">{label}</dt>
          <dd className="break-words text-sm font-medium">{value}</dd>
        </div>)}
      </dl> : <p className="text-sm text-[#5c4039]">Chưa có dữ liệu đã lưu cho mục này.</p>}
    </section>
  );
}

export default function AdminInterviewDetail({ detail, onRefresh }: { detail: InterviewDetail; onRefresh: () => void }) {
  const [stage, setStage] = useState<Stage>(
    detail.finalized || detail.session.status === 'IN_PROGRESS' ? 'transcript' : 'inputs'
  );
  const [printError, setPrintError] = useState(false);
  const { session, inputs, matching, blueprint } = detail;
  const score = percent(matching.score);
  const policy = blueprint?.policy;
  const locked = !detail.finalized && stage === 'evaluation';
  const panels = {
    inputs: <Fields title="Hồ sơ đầu vào" items={[
      ['Tên tệp CV', inputs.cvName], ['Tiêu đề mô tả công việc', inputs.jdTitle], ['Công ty', inputs.company],
    ]} />,
    matching: <Fields title="Kết quả đối sánh" items={[
      ['Độ khớp CV–JD', score === null ? null : score + '%'],
      ['Skill Gap', matching.available ? 'Đã có kết quả phân tích' : 'Chưa có kết quả phân tích'],
    ]} />,
    blueprint: <div className="space-y-4">
      <Fields title="Cấu hình đã lưu của phiên" items={[
        ['Tối đa số câu hỏi', blueprint?.maxQuestions ?? null],
        ['Thời lượng tối đa (giây)', blueprint?.durationSeconds ?? null],
        ['Tối đa câu hỏi mỗi kỹ năng', blueprint?.maxQuestionsPerObjective ?? null],
        ['Dạng câu hỏi', blueprint ? blueprint.questionMode ?? 'Tổng hợp' : null],
        ['Mục tiêu đánh giá', blueprint?.objectiveCount ?? null],
      ]} />
      {policy && <Fields title="Chính sách thích ứng của phiên" items={[
        ['Trọng số kỹ năng cốt lõi', policy.coreImportance],
        ['Tỷ lệ câu hỏi đào sâu dự phòng', policy.reserveFollowupFraction],
        ['Độ sâu dự phòng', policy.fallbackDepth],
        ['Số ngữ cảnh thất bại tối thiểu', policy.minFailureContexts],
        ['Câu hỏi mở rộng', policy.allowExtensionProbes === null ? null : policy.allowExtensionProbes ? 'Bật' : 'Tắt'],
      ]} />}
    </div>,
    transcript: <InterviewTranscript transcript={detail.transcript} />,
    evaluation: <InterviewEvaluation report={detail.report} />,
  };

  return (
    <>
      <section className="flex flex-wrap items-center justify-between gap-4 rounded-xl bg-white p-5 shadow-xs">
        <div className="min-w-0 space-y-2">
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="text-xl font-semibold">{session.candidateName ?? 'Ứng viên không còn hồ sơ'}</h2>
            <span className={statusStyle(session.status) + ' rounded-full px-2 py-1 text-xs font-medium'}>
              {statusLabels[session.status]}
            </span>
          </div>
          <p className="break-all font-mono text-xs text-[#5c4039]">{session.id}</p>
          <p className="flex flex-wrap gap-x-3 text-sm">
            {session.roleTitle && <span>{session.roleTitle}</span>}
            {session.mode && <span>{modeLabel(session.mode)}</span>}
            {session.startedAt && <span>Bắt đầu {dateLabel(session.startedAt)}</span>}
            {session.endedAt && <span>Kết thúc {dateLabel(session.endedAt)}</span>}
            {session.startedAt && session.endedAt && <span>{durationLabel(session)}</span>}
            {session.userRating != null && <span>Ứng viên đánh giá {session.userRating}/5</span>}
          </p>
        </div>
        {detail.finalized
          ? <button type="button" onClick={() => setPrintError(!printInterviewReport(detail))}
              className="flex items-center gap-2 rounded-lg bg-[#186392] px-4 py-2 text-sm font-semibold text-white">
              <FileDown className="size-4" /> Xuất báo cáo PDF
            </button>
          : <button type="button" onClick={onRefresh}
              className="flex items-center gap-2 rounded-lg bg-[#edf0ff] px-4 py-2 text-sm">
              <RefreshCw className="size-4" /> Làm mới phiên
            </button>}
      </section>
      {printError && <p role="alert" className="text-sm text-red-700">Trình duyệt đã chặn cửa sổ báo cáo. Hãy cho phép cửa sổ bật lên và thử lại.</p>}
      <div role="group" aria-label="Các phần chi tiết phiên" className="grid gap-2 sm:grid-cols-2 xl:grid-cols-5">
        {stages.map(([id, label]) => (
          <button type="button" key={id} aria-pressed={stage === id} onClick={() => setStage(id)}
            className={stage === id
              ? 'rounded-xl bg-[#ad2c00] px-4 py-3 text-left text-sm font-semibold text-white'
              : 'rounded-xl bg-white px-4 py-3 text-left text-sm font-semibold text-[#186392] shadow-xs hover:bg-[#edf0ff]'}>
            {label}
          </button>
        ))}
      </div>
      {locked
        ? <p className="rounded-xl bg-white p-5 text-sm text-[#5c4039]">Đánh giá cuối sẽ hiển thị sau khi phiên kết thúc.</p>
        : stage === 'transcript' && detail.finalized
          ? <div className="grid items-start gap-5 xl:grid-cols-[2fr_1fr]">
              {panels.transcript}
              <InterviewEvaluation report={detail.report} />
            </div>
          : panels[stage]}
    </>
  );
}
