'use client';

import { Check, Clock3, LoaderCircle, Mic, RotateCcw, UserRound } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { MarkdownContent } from '@/components/common/MarkdownContent';
import type { VoiceInterviewRoom } from '@/hooks/useVoiceInterviewRoom';
import { turnSkillId } from '@/services/evidenceInterview';
import { InterviewClarifyBar } from './InterviewClarifyBar';
import { InterviewCodeEditor } from './InterviewCodeEditor';
import styles from './EvidenceVoiceInterview.module.css';

export function VoiceAvatarPanel({ room }: { room: VoiceInterviewRoom }) {
  const { voice } = room;
  return <section className={styles.stage} aria-label="Người phỏng vấn">
    <div className={styles.stageLabel}><span className={styles.aiMark}>AI</span>{room.session?.conversation?.opening.interviewer_name || 'Người phỏng vấn'}</div>
    <div className={styles.avatar} aria-label="Avatar người phỏng vấn">
      <video ref={room.videoRef} autoPlay playsInline muted className={styles.simliVideo} data-ready={voice.avatarReady} aria-label="Video người phỏng vấn Simli" />
      <audio ref={room.audioRef} autoPlay aria-hidden="true" />
      {!voice.avatarReady && <div className={styles.simliPlaceholder}>
        {voice.starting ? <LoaderCircle size={30} className={styles.spinner} /> : <UserRound size={40} strokeWidth={1.25} />}
        <p>{voice.starting ? 'Đang kết nối…' : 'Người phỏng vấn AI'}</p>
        {!voice.enabled && <Button className={styles.startButton} disabled={voice.starting || room.busy || room.session?.awaiting_question} onClick={() => void voice.enable()}>
          <Mic size={16} />{voice.starting ? 'Đang bật micro…' : 'Bắt đầu trò chuyện'}
        </Button>}
      </div>}
    </div>
  </section>;
}

export function VoiceQuestionPanel({ room }: { room: VoiceInterviewRoom }) {
  const pending = room.session?.pending_turn ?? null;
  const awaiting = Boolean(room.session?.awaiting_question);
  const previousQuestion = awaiting ? room.session?.turns.at(-1)?.question : '';
  const isPractice = room.session?.config.session_purpose === 'PRACTICE';
  const lastFeedback = room.session?.turns.at(-1)?.feedback?.trim() || '';
  const introOrFeedback = room.introduction || (awaiting ? lastFeedback : '');
  const showClarify = Boolean(
    room.phase === 'INTERVIEW' && !awaiting && pending,
  );
  const timeLeft = `${Math.floor(room.interview.secondsLeft / 60)}:${String(room.interview.secondsLeft % 60).padStart(2, '0')}`;
  return <section className={styles.textPanel} aria-label="Câu hỏi của AI">
    <header className={styles.panelHeader}>
      <h2>Câu hỏi của AI</h2>
      {room.phase === 'INTERVIEW' && room.session && (
        <span
          title="Đồng hồ tạm dừng khi AI chấm và chuẩn bị câu tiếp theo"
          className="inline-flex items-center gap-1.5 text-xs font-medium tabular-nums text-muted-foreground"
        >
          <span>{room.session.turns.length}/{room.session.config.max_questions} câu</span>
          <span aria-hidden="true">·</span>
          <Clock3 size={12} aria-hidden="true" />
          <span>{timeLeft}</span>
        </span>
      )}
    </header>
    <div ref={room.questionBox} role="region" aria-label="Nội dung câu hỏi" tabIndex={0} className={styles.question}>
      {introOrFeedback && <div className={styles.introduction}><MarkdownContent content={introOrFeedback} /></div>}
      <MarkdownContent content={room.question || previousQuestion || 'Câu hỏi sẽ xuất hiện tại đây.'} />
      {showClarify && pending && (
        <InterviewClarifyBar
          key={pending.turn_id}
          clarifications={pending.clarifications ?? []}
          mode={pending.mode}
          isPractice={isPractice}
          busy={room.busy}
          compact
          onClarify={(kind, question) => room.interview.clarify(kind, question)}
          onInputActiveChange={room.setClarifyTyping}
        />
      )}
    </div>
  </section>;
}

function VoiceCodeAnswer({ room }: { room: VoiceInterviewRoom }) {
  const pending = room.session?.pending_turn;
  const isPractice = room.session?.config.session_purpose === 'PRACTICE';
  if (!room.session || !pending) return null;
  const starterCode = (pending.coding_spec?.starter_code ?? '').trim();
  const hasCode = Boolean(room.code.trim());
  const hasEditedCode = Boolean(hasCode && (!starterCode || room.code.trim() !== starterCode));
  const canSubmit = pending.requires_code
    ? hasEditedCode
    : Boolean(hasEditedCode || room.interview.answer.trim());
  return (
    <div id="voice-code-wrapper" className="space-y-2.5 border-t p-3">
      <p className="text-xs font-semibold text-muted-foreground uppercase">Mã nguồn</p>
      <InterviewCodeEditor
        sessionId={room.session.session_id}
        turnId={pending.turn_id}
        value={room.code}
        onChange={room.setCode}
        codingSpec={pending.coding_spec}
        questionHint={`${turnSkillId(room.session, pending)} ${pending.question}`}
        disabled={room.busy}
        defaultAutocomplete={isPractice}
        compact
      />
      <div className="flex flex-wrap gap-2">
        <Button
          disabled={!canSubmit || room.cannotSubmit}
          title={!canSubmit && Boolean(starterCode) ? 'Hãy chỉnh sửa mã nguồn trước khi nộp bài' : undefined}
          onClick={() => void room.voice.submit(room.interview.answer, hasCode ? room.code : undefined)}
        >
          Nộp bài
        </Button>
        {pending.requires_code && (
          <Button variant="outline" disabled={room.cannotSubmit} onClick={() => void room.voice.submit('Em chưa biết.')}>
            Chưa làm được
          </Button>
        )}
      </div>
    </div>
  );
}

export function VoiceAnswerPanel({ room }: { room: VoiceInterviewRoom }) {
  const pending = room.session?.pending_turn ?? null;
  const canResetDraft = Boolean(
    !room.sent && room.caption && !room.presenting && !room.busy
    && !room.voice.listening && !room.voice.transcribing && !room.voice.review,
  );
  return <section className={styles.textPanel} aria-label="Câu trả lời của bạn">
    <header className={styles.panelHeader}><h2>Câu trả lời của bạn</h2>
      {room.sent && <span className={styles.sentBadge}><Check size={12} />Đã gửi</span>}
      {canResetDraft && (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-7 px-2 text-xs text-muted-foreground hover:text-foreground"
          title="Xóa bản nhận diện hiện tại để nói lại"
          onClick={() => room.voice.clearDraft()}
        >
          <RotateCcw size={12} aria-hidden="true" />
          Nói lại
        </Button>
      )}
    </header>
    <div ref={room.captionBox} role="log" aria-live="polite" aria-relevant="text additions" aria-label="Nội dung lời nói" tabIndex={0} className={styles.captions}>
      {room.caption ? <p>{room.caption}</p> : <p className={styles.placeholder}>{room.voice.retryAvailable ? 'Chưa nhận diện được đoạn vừa nói.' : 'Lời bạn nói sẽ hiện ở đây.'}</p>}
    </div>
    {room.hasCodeEditor && pending && <VoiceCodeAnswer key={pending.turn_id} room={room} />}
  </section>;
}
