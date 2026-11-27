'use client';

import { useState } from 'react';
import { Check, LoaderCircle, Mic, UserRound } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { MarkdownContent } from '@/components/common/MarkdownContent';
import type { VoiceInterviewRoom } from '@/hooks/useVoiceInterviewRoom';
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
  return <section className={styles.textPanel} aria-label="Câu hỏi của AI">
    <header className={styles.panelHeader}><h2>Câu hỏi của AI</h2></header>
    <div ref={room.questionBox} role="region" aria-label="Nội dung câu hỏi" tabIndex={0} className={styles.question}>
      {room.introduction && <div className={styles.introduction}><MarkdownContent content={room.introduction} /></div>}
      <MarkdownContent content={room.question || 'Câu hỏi sẽ xuất hiện tại đây.'} />
    </div>
  </section>;
}

function VoiceCodeAnswer({ room }: { room: VoiceInterviewRoom }) {
  const pending = room.session?.pending_turn;
  const [code, setCode] = useState(() => pending?.coding_spec?.starter_code ?? '');
  if (!room.session || !pending) return null;
  return (
    <div id="voice-code-wrapper" className="space-y-2.5 border-t p-3">
      <p className="text-xs font-semibold text-muted-foreground uppercase">Mã nguồn</p>
      <InterviewCodeEditor
        sessionId={room.session.session_id}
        turnId={pending.turn_id}
        value={code}
        onChange={setCode}
        codingSpec={pending.coding_spec}
        questionHint={pending.question}
        disabled={room.busy}
        compact
      />
      <div className="flex flex-wrap gap-2">
        <Button disabled={!code.trim() || room.cannotSubmit} onClick={() => void room.voice.submit(room.interview.answer, code)}>
          Nộp bài
        </Button>
        <Button variant="outline" disabled={room.cannotSubmit} onClick={() => void room.voice.submit('Em chưa biết.')}>
          Chưa làm được
        </Button>
      </div>
    </div>
  );
}

export function VoiceAnswerPanel({ room }: { room: VoiceInterviewRoom }) {
  return <section className={styles.textPanel} aria-label="Câu trả lời của bạn">
    <header className={styles.panelHeader}><h2>Câu trả lời của bạn</h2>
      {room.sent && <span className={styles.sentBadge}><Check size={12} />Đã gửi</span>}
    </header>
    <div ref={room.captionBox} role="log" aria-live="polite" aria-relevant="text additions" aria-label="Nội dung lời nói" tabIndex={0} className={styles.captions}>
      {room.caption ? <p>{room.caption}</p> : <p className={styles.placeholder}>{room.voice.retryAvailable ? 'Chưa nhận diện được đoạn vừa nói.' : 'Lời bạn nói sẽ hiện ở đây.'}</p>}
    </div>
    {room.session?.pending_turn?.requires_code && <VoiceCodeAnswer key={room.session.pending_turn.turn_id} room={room} />}
  </section>;
}
