'use client';
import Link from 'next/link';
import dynamic from 'next/dynamic';
import { useState } from 'react';
import { useParams } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { useEvidenceInterview } from '@/hooks/useEvidenceInterview';
import { EvidenceTextInterview } from './EvidenceTextInterview';
import { InterviewSubmissionStatus } from './InterviewSubmissionStatus';
import { EvidenceSession, EvidenceTurn, conversationPhase, turnSkillId } from '@/services/evidenceInterview';
import { IntroductionHistory } from './InterviewConversation';
import { EvidenceSetup, modeLabels } from './EvidenceSetup';
import { InterviewOutcome } from './InterviewOutcome';
import { InterviewResultDashboard } from './result/InterviewResultDashboard';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { skillLabel } from '@/components/features/applications/applicationUi';
import { MarkdownContent } from '@/components/common/MarkdownContent';
import { BrandLoading } from '@/components/common/BrandLoading';

const VoiceInterview = dynamic(() => import('./EvidenceVoiceInterview').then(module => module.EvidenceVoiceInterview),
  { ssr: false, loading: () => <p className="p-6 text-sm">Đang chuẩn bị phòng phỏng vấn giọng nói…</p> });

function Transcript({ session, turns }: { session: EvidenceSession; turns: EvidenceTurn[] }) {
  return <div className="space-y-3">{[...turns].reverse().map((turn, index) => <details className="rounded-xl border bg-card p-4" key={turn.turn_id} open={index === 0}>
    <summary className="cursor-pointer text-sm font-semibold">Câu {turns.length - index} · {skillLabel(turnSkillId(session, turn))} · {modeLabels[turn.mode]}</summary>
    <div className="mt-4 space-y-4">
      <MarkdownContent content={turn.question} />
      <div className="rounded-lg bg-muted/40 p-4"><p className="mb-2 text-xs font-semibold text-muted-foreground">CÂU TRẢ LỜI CỦA BẠN</p>
        {turn.mode === 'CODING' ? <pre className="max-w-full overflow-x-auto whitespace-pre font-mono text-sm">{turn.answer}</pre> : <MarkdownContent content={turn.answer || ''} />}
      </div>
      {turn.feedback && <div className="rounded-lg border border-brand-green/20 bg-brand-green/5 p-4"><p className="mb-2 text-xs font-semibold text-brand-green">NHẬN XÉT</p><MarkdownContent content={turn.feedback} /></div>}
    </div>
  </details>)}</div>;
}

export function EvidenceInterview() {
  const { id } = useParams<{ id: string }>();
  const interview = useEvidenceInterview(id);
  const [confirmStop, setConfirmStop] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const { session, busy, error } = interview;
  const phase = conversationPhase(session);
  const conversationVisible = ['OPENING', 'SELF_INTRODUCTION', 'CLOSING'].includes(phase);
  const grading = session?.submission?.status === 'QUEUED' && !session.is_finished;
  const awaitingQuestion = Boolean(session?.awaiting_question && !session.is_finished && (busy || !error));
  const processingLabel = grading ? 'Đang chấm câu trả lời…'
    : awaitingQuestion ? (session?.turns.length ? 'Đang chuẩn bị câu hỏi tiếp theo…' : 'Đang chuẩn bị câu hỏi đầu tiên…')
      : null;
  if (interview.loading) return <main className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6">
    <BrandLoading label="Đang tải phiên phỏng vấn…" description="Đang chuẩn bị không gian luyện tập của bạn." className="min-h-[60vh]" />
  </main>;
  if (interview.legacy) return <main className="mx-auto max-w-3xl space-y-4 p-8">
    <h1 className="text-xl font-semibold">Phiên phỏng vấn cũ</h1>
    <p>Phiên này chỉ hỗ trợ xem lại. Hãy tạo lượt phỏng vấn mới để tiếp tục luyện tập.</p>
    <div className="flex gap-4"><Link className="text-brand-orange" href={`/interview/session/${id}/result`}>Xem kết quả đã lưu</Link>
      <Link className="text-brand-orange" href="/interview/new">Tạo lượt phỏng vấn mới</Link></div>
  </main>;
  if (session?.is_finished && !conversationVisible && session.turns.length > 0) {
    return <InterviewResultDashboard session={session} metadata={interview.metadata} />;
  }
  return <main className="mx-auto w-full max-w-6xl space-y-4 px-4 py-5 sm:px-6">
    {interview.metadata?.applicationProfileId && session?.config.interaction_mode !== 'VOICE' && <header className="space-y-2 border-b pb-5"><Link className="text-sm text-brand-orange" href={`/applications/${interview.metadata.applicationProfileId}`}>← Về hồ sơ ứng tuyển</Link><h2 className="text-xl font-semibold">{interview.metadata.applicationProfileTitle} · Lượt {interview.metadata.attemptNumber}</h2></header>}
    {session?.awaiting_question && session.config.interaction_mode === 'VOICE' && !awaitingQuestion && <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-card p-4">
      <p role="status">{session.turns.length > 0 ? 'Đã lưu câu trả lời. ' : session.conversation?.introduction ? 'Đã lưu phần giới thiệu. ' : ''}
        {session.turns.length ? 'Câu tiếp theo đang chờ tải.' : 'Câu hỏi đầu tiên đang chờ tải.'}</p>
      <Button variant="outline" onClick={() => void interview.loadNextQuestion()}>Thử tải lại câu hỏi</Button>
    </div>}
    {error && !session?.awaiting_question && <div role="alert" className="rounded border border-red-300 p-4"><p>{error}</p><Button variant="outline" onClick={() => void interview.reload()}>Tải lại phiên</Button></div>}
    {!session && <EvidenceSetup busy={busy} profileId={interview.metadata?.applicationProfileId} onStart={config => void interview.start(config)} />}
    {session?.submission && !grading && (!session.is_finished || conversationVisible) && <InterviewSubmissionStatus submission={session.submission} busy={busy}
      retry={() => void interview.submit(session.submission!.candidate_response, session.submission!.submitted_code)}
      stop={() => setConfirmStop(true)} />}
    {session && <>
      {session.is_finished && !conversationVisible ? <InterviewOutcome session={session} metadata={interview.metadata} />
        : session.config.interaction_mode === 'VOICE'
          ? <VoiceInterview interview={interview} suspended={confirmStop || Boolean(error) || Boolean(session.submission && !session.is_finished)} onStop={() => setConfirmStop(true)} />
          : (!session.submission || grading || conversationVisible) && <EvidenceTextInterview interview={interview} onHistory={() => setHistoryOpen(true)} onStop={() => setConfirmStop(true)} />}
    </>}
    {processingLabel && (
      <Dialog open disablePointerDismissal onOpenChange={(open, event) => { if (!open) event.cancel(); }}>
        <DialogContent
          aria-label={processingLabel}
          showCloseButton={false}
          overlayClassName="bg-black/35 supports-backdrop-filter:backdrop-blur-sm motion-reduce:animate-none"
          className="rounded-2xl p-5 sm:max-w-xs motion-reduce:animate-none"
        >
          <BrandLoading embedded label={processingLabel} description={grading ? 'Thời gian làm bài đã tạm dừng.' : undefined} />
        </DialogContent>
      </Dialog>
    )}
    <Dialog open={historyOpen} onOpenChange={setHistoryOpen}><DialogContent className="sm:max-w-3xl"><DialogHeader><DialogTitle>Lịch sử phỏng vấn</DialogTitle><DialogDescription>Câu mới nhất hiển thị trước. Mở từng câu để xem lại câu trả lời và nhận xét.</DialogDescription></DialogHeader><div role="region" aria-label="Nội dung lịch sử" tabIndex={0} className="max-h-[65dvh] min-w-0 space-y-3 overflow-y-auto overscroll-contain pr-1"><IntroductionHistory interview={interview} />{session?.turns.length ? <Transcript session={session} turns={session.turns} /> : <p className="py-8 text-center text-muted-foreground">Chưa có câu trả lời nào được gửi.</p>}</div><DialogFooter><Button variant="outline" onClick={() => setHistoryOpen(false)}>Đóng lịch sử</Button></DialogFooter></DialogContent></Dialog>
    <Dialog open={confirmStop} onOpenChange={open => !busy && setConfirmStop(open)}><DialogContent><DialogHeader><DialogTitle>Kết thúc lượt phỏng vấn?</DialogTitle><DialogDescription>{session?.submission?.status === 'FAILED' ? 'Bài vừa nộp sẽ được giữ lại ở trạng thái chưa chấm. Các lượt đã chấm vẫn có trong kết quả.' : session?.turns.length ? 'Các câu trả lời đã gửi sẽ được giữ lại và dùng để tạo kết quả. Lượt này sẽ được ghi nhận là kết thúc sớm.' : 'Bạn chưa gửi câu trả lời nào. Lượt này sẽ được ghi nhận là đã hủy và chưa có dữ liệu đánh giá.'} Nội dung chưa nộp sẽ không được tính.</DialogDescription></DialogHeader><DialogFooter><Button variant="outline" disabled={busy} onClick={() => setConfirmStop(false)}>Tiếp tục phỏng vấn</Button><Button disabled={busy} onClick={() => { setConfirmStop(false); void interview.stop(); }}>Kết thúc lượt</Button></DialogFooter></DialogContent></Dialog>
  </main>;
}
