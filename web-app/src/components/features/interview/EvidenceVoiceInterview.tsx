'use client';

import { useEffect, useRef, useState } from 'react';
import { AlertCircle, Check, Clock3, Headphones, LoaderCircle, Mic, MicOff, PhoneOff, Play, RotateCcw, SlidersHorizontal, UserRound, Volume2, VolumeX } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { useEvidenceVoice } from '@/hooks/useEvidenceVoice';
import type { InterviewController } from './EvidenceTextInterview';
import styles from './EvidenceVoiceInterview.module.css';

export function EvidenceVoiceInterview({ interview, suspended, onStop }: {
  interview: InterviewController; suspended: boolean; onStop: () => void;
}) {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const { session, busy } = interview;
  const turn = session?.pending_turn;
  const videoRef = useRef<HTMLVideoElement>(null);
  const audioRef = useRef<HTMLAudioElement>(null);
  const voice = useEvidenceVoice({ id: session?.session_id || '', session, busy, answer: interview.answer,
    setAnswer: interview.setAnswer, submit: interview.submit, suspended, videoRef, audioRef });
  const previousAnswer = session?.turns.at(-1)?.answer || '';
  const caption = voice.captions || interview.answer || (!voice.listening && !voice.transcribing && !voice.retryAvailable ? previousAnswer : '');
  const sent = !voice.captions && !interview.answer && Boolean(caption);
  const captionBox = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const box = captionBox.current;
    if (box) box.scrollTop = box.scrollHeight;
  }, [caption]);
  if (!session || !turn) return null;

  const state = voice.starting ? 'connecting' : !voice.enabled ? 'ready' : voice.paused ? 'paused' : busy ? 'thinking'
    : voice.listening ? 'listening' : voice.transcribing ? 'transcribing' : voice.retryAvailable ? 'retry'
    : voice.speaking ? 'speaking' : voice.loadingSpeech ? 'loading' : 'waiting';
  const status = {
    connecting: 'Đang kết nối avatar…',
    ready: 'Sẵn sàng trò chuyện', paused: 'Micro đang tạm dừng', thinking: 'Đang chuẩn bị câu hỏi tiếp theo…',
    listening: 'Đang nghe bạn…', transcribing: 'Đang nhận diện lời nói…', speaking: 'Người phỏng vấn đang nói',
    loading: 'Đang chuẩn bị giọng đọc…', waiting: 'Đến lượt bạn trả lời',
    retry: 'Chưa nhận diện được lời nói',
  }[state];
  const hint = {
    connecting: 'Đang chuẩn bị hình ảnh và âm thanh cho cuộc trò chuyện.',
    ready: 'Bắt đầu khi bạn cảm thấy sẵn sàng.', paused: 'Chọn Tiếp tục nghe khi bạn muốn nói tiếp.',
    thinking: 'Câu trả lời của bạn đã được ghi nhận.', listening: 'Cứ nói tự nhiên, AI đang lắng nghe bạn.',
    transcribing: 'Bạn vẫn có thể nói tiếp để bổ sung.', speaking: 'Bạn có thể nói để ngắt lời AI.',
    loading: 'Câu hỏi sẽ được đọc trong giây lát.', waiting: 'Bạn có thể dành một chút thời gian suy nghĩ.',
    retry: 'Bản ghi vẫn được giữ để bạn thử lại.',
  }[state];
  const processing = ['connecting', 'thinking', 'transcribing', 'loading'].includes(state);
  const StatusIcon = processing ? LoaderCircle : state === 'paused' ? MicOff : state === 'retry' ? AlertCircle : state === 'speaking' ? Volume2 : Mic;
  const cannotSubmit = busy || voice.transcribing || voice.listening || voice.retryAvailable || Boolean(voice.review);
  const time = `${Math.floor(interview.secondsLeft / 60)}:${String(interview.secondsLeft % 60).padStart(2, '0')}`;

  return <section data-interview-mode="VOICE" aria-label="Không gian phỏng vấn giọng nói" className={styles.room}>
    <header className={styles.header}>
      <div className={styles.heading}>
        <h1>Phỏng vấn giọng nói</h1>
        <div className={styles.progressRow}>
          <span>Đã trả lời {session.turns.length}/{session.config.max_questions} câu</span>
          <span role="progressbar" aria-label="Số câu đã trả lời" aria-valuemin={0} aria-valuemax={session.config.max_questions} aria-valuenow={session.turns.length} className={styles.progress}>
            <span style={{ width: `${Math.min(100, session.turns.length / session.config.max_questions * 100)}%` }} />
          </span>
        </div>
      </div>
      <div className={styles.headerActions}>
        <span className={styles.timer} data-urgent={interview.secondsLeft <= 60} aria-label={`Thời gian còn lại ${time}`}><Clock3 size={16} /><span><span className={styles.timerLabel}>Còn </span>{time}</span></span>
        <Button variant="outline" className={styles.settingsButton} aria-label="Tùy chỉnh cuộc trò chuyện" title="Tùy chỉnh cuộc trò chuyện" onClick={() => setSettingsOpen(true)}><SlidersHorizontal size={18} /></Button>
      </div>
    </header>

    <div className={styles.surface}>
      <div className={styles.conversation}>
        <section className={styles.stage} aria-label="Người phỏng vấn">
          <div className={styles.stageLabel}><span className={styles.aiMark}>AI</span><span>Người phỏng vấn</span></div>
          <div className={styles.avatar} aria-label="Avatar người phỏng vấn">
            <video ref={videoRef} autoPlay playsInline muted className={styles.simliVideo} data-ready={voice.avatarReady} aria-label="Video người phỏng vấn Simli" />
            <audio ref={audioRef} autoPlay aria-hidden="true" />
            {!voice.avatarReady && <div className={styles.simliPlaceholder}>
              {voice.starting ? <LoaderCircle size={30} className={styles.spinner} /> : <UserRound size={40} strokeWidth={1.25} />}
              <p>{voice.starting ? 'Đang kết nối người phỏng vấn…' : 'Người phỏng vấn AI'}</p>
              <span>{voice.starting ? 'Vui lòng chờ trong giây lát' : 'Avatar sẽ xuất hiện khi bạn bắt đầu trò chuyện'}</span>
            </div>}
          </div>
          <div className={styles.stageStatus} data-state={state}>
            <span className={styles.statusIcon} aria-hidden="true"><StatusIcon size={19} className={processing ? styles.spinner : undefined} /></span>
            <div className={styles.statusCopy}><p role="status" aria-live="polite">{status}</p><p>{hint}</p></div>
            {(voice.speaking || voice.loadingSpeech) && <Button variant="ghost" className={styles.stopSpeech} onClick={voice.interrupt} aria-label="Dừng giọng đọc" title="Dừng giọng đọc"><VolumeX size={17} /><span>Dừng</span></Button>}
          </div>
        </section>

        <section aria-label="Lời nói của bạn" className={styles.transcriptPanel}>
          {!voice.enabled ? <div className={styles.welcome}>
            <span className={styles.welcomeIcon} aria-hidden="true"><Headphones size={25} strokeWidth={1.5} /></span>
            <p className={styles.eyebrow}>Trước khi bắt đầu</p>
            <h2>Bắt đầu cuộc trò chuyện</h2>
            <p>Nghe câu hỏi từ AI và trả lời tự nhiên. Lời bạn nói sẽ hiện tại đây để bạn dễ theo dõi.</p>
            <Button className={styles.startButton} disabled={voice.starting || busy} onClick={() => void voice.enable()}>{voice.starting ? <LoaderCircle className={styles.spinner} size={18} /> : <Mic size={18} />}{voice.starting ? 'Đang bật micro…' : 'Bắt đầu trò chuyện'}</Button>
            <span className={styles.permissionHint}>Micro chỉ bật khi bạn cho phép.</span>
          </div> : <>
            <div className={styles.transcriptHeader}>
              <div><p className={styles.eyebrow}>Lời nói của bạn</p><h2>{sent ? 'Câu trả lời vừa gửi' : 'Câu trả lời hiện tại'}</h2></div>
              {sent && <span className={styles.sentBadge}><Check size={13} />Đã gửi</span>}
              {voice.listening && <span className={styles.liveBadge}><span aria-hidden="true" />Đang nghe<span className="sr-only"> bạn nói</span></span>}
            </div>
            <div ref={captionBox} role="log" aria-live="polite" aria-relevant="text additions" aria-label="Nội dung lời nói" tabIndex={0} className={styles.captions} data-empty={!caption}>
              {caption ? <p>{caption}</p> : <div className={styles.captionPlaceholder}>
                <span className={styles.placeholderIcon} aria-hidden="true">{voice.retryAvailable ? <AlertCircle size={23} strokeWidth={1.5} /> : <Mic size={23} strokeWidth={1.5} />}</span>
                <p>{voice.listening ? 'Đang lắng nghe bạn' : voice.transcribing ? 'Đang nhận diện đoạn vừa nói…' : voice.retryAvailable ? 'Chưa nhận diện được đoạn vừa nói' : 'Lời bạn nói sẽ hiện ở đây'}</p>
                <span>{voice.listening || voice.transcribing ? 'Văn bản sẽ xuất hiện khi đoạn nói được nhận diện.' : voice.retryAvailable ? 'Thử nhận diện lại bản ghi bên dưới.' : 'Bạn chỉ cần nói. Không cần nhập văn bản.'}</span>
              </div>}
            </div>
            <div className={styles.transcriptFoot}>
              {voice.countdown ? <div role="status" className={styles.countdown}><span>Sắp gửi câu trả lời…</span><button onClick={voice.cancelAuto}>Chờ thêm</button></div>
                : <p>{voice.transcribing ? <><LoaderCircle size={14} className={styles.spinner} />Đang nhận diện và kiểm tra lại lời nói…</> : voice.listening ? 'Phụ đề tạm; nội dung được kiểm tra lại khi bạn ngừng nói.' : voice.review ? 'Cần xác nhận đoạn chưa rõ trước khi gửi.' : 'Chỉ bản nhận diện đã chốt được dùng để đánh giá.'}</p>}
              {(turn.mode === 'CODING' || turn.mode === 'DEBUGGING') && <p className={styles.codingHint}>Câu này chỉ cần giải thích cách làm bằng lời.</p>}
            </div>
          </>}
          {voice.review && <div role="region" aria-label="Xác nhận lời nói" tabIndex={0} className={styles.recognitionReview}>
            <h3>{voice.review.unavailable ? 'Chưa đối chiếu được đoạn ghi này' : 'Hai lần nhận diện có nội dung khác nhau'}</h3>
            <p>Nghe lại và chọn bản đúng với lời bạn nói. Câu trả lời chưa được gửi đánh giá.</p>
            <audio key={voice.review.segment} controls preload="none" aria-label="Nghe lại đoạn cần xác nhận" src={`data:audio/wav;base64,${voice.review.audio}`} />
            <blockquote>{voice.review.text}</blockquote>
            <Button size="sm" variant="outline" onClick={() => voice.confirmReview(voice.review!.segment, false)}>Dùng bản nhận diện này</Button>
            {voice.review.alternative && <>
              <blockquote>{voice.review.alternative}</blockquote>
              <Button size="sm" variant="outline" onClick={() => voice.confirmReview(voice.review!.segment, true)}>Dùng bản đối chiếu</Button>
            </>}
            <Button size="sm" variant="ghost" onClick={() => voice.rejectReview(voice.review!.segment)}>Bỏ đoạn này và nói lại</Button>
          </div>}
          {voice.error && <div role="alert" className={styles.error}>
            <AlertCircle size={17} aria-hidden="true" /><div><p>{voice.error}</p>
              {voice.retryAvailable && <div className={styles.retryActions}><Button size="sm" variant="outline" onClick={voice.retry}>Nhận diện lại bản ghi</Button><Button size="sm" variant="ghost" onClick={voice.discard}>Bỏ đoạn ghi lỗi</Button></div>}
            </div>
          </div>}
        </section>
      </div>

      {voice.enabled && <div className={styles.controls} aria-label="Điều khiển cuộc trò chuyện">
        <div className={styles.audioControls}>
          <Button variant="outline" className={styles.controlButton} aria-pressed={voice.paused} onClick={voice.pause}>{voice.paused ? <Play size={17} /> : <MicOff size={17} />}{voice.paused ? 'Tiếp tục nghe' : 'Tạm dừng micro'}</Button>
          <Button variant="ghost" className={styles.controlButton} disabled={busy || voice.paused} onClick={() => void voice.replay()}><RotateCcw size={17} />Nghe lại câu hỏi</Button>
        </div>
        {interview.answer.trim() ? <Button className={styles.submitButton} disabled={cannotSubmit} onClick={() => void voice.submit()}><Check size={17} />Tôi đã trả lời xong</Button>
          : <p className={styles.controlsHint}>{voice.automatic ? 'Tự gửi sau khi bạn nói xong' : 'Bạn đang chọn gửi câu trả lời thủ công'}</p>}
      </div>}
    </div>

    <footer className={styles.footer}>
      <p><Headphones size={15} aria-hidden="true" /><span>Dùng tai nghe để hạn chế vọng tiếng.</span></p>
      <Button variant="ghost" className={styles.endButton} disabled={busy} onClick={onStop}><PhoneOff size={15} />Kết thúc phiên</Button>
    </footer>

    <Dialog open={settingsOpen} onOpenChange={setSettingsOpen}>
      <DialogContent className={styles.settingsDialog}>
        <DialogHeader><DialogTitle>Tùy chỉnh cuộc trò chuyện</DialogTitle><DialogDescription>Chọn cách chuyển lượt phù hợp với nhịp trả lời của bạn.</DialogDescription></DialogHeader>
        <label className={styles.automaticSetting}>
          <span><span className={styles.settingTitle}>Tự gửi khi nói xong</span><span className={styles.settingDescription}>Tắt để tự bấm “Tôi đã trả lời xong” sau mỗi câu.</span></span>
          <input type="checkbox" checked={voice.automatic} onChange={e => voice.setAutomatic(e.target.checked)} />
        </label>
        <label className={styles.silenceSetting}>
          <span className={styles.settingTitle}>Khoảng nghỉ để suy nghĩ</span>
          <span className={styles.settingDescription}>AI chờ bao lâu khi bạn ngừng nói trước khi nhận diện đoạn vừa nói.</span>
          <select aria-label="Thời gian chờ hết câu" value={voice.silenceMs} onChange={e => voice.setSilenceMs(Number(e.target.value))}>
            <option value={900}>Nhanh · 0,9 giây</option><option value={1200}>Cân bằng · 1,2 giây</option><option value={2200}>Chờ suy nghĩ · 2,2 giây</option>
          </select>
        </label>
        <DialogFooter><Button className={styles.settingsDone} onClick={() => setSettingsOpen(false)}>Xong</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  </section>;
}
