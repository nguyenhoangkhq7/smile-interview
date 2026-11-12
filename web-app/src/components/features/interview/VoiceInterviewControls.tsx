'use client';

import { AlertCircle, Check, MicOff, PhoneOff, Play, RotateCcw, SlidersHorizontal, VolumeX } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import type { VoiceInterviewRoom } from '@/hooks/useVoiceInterviewRoom';
import styles from './EvidenceVoiceInterview.module.css';

export function VoiceToolbar({ room }: { room: VoiceInterviewRoom }) {
  const { voice } = room;
  return <div className={styles.toolbar} aria-label="Điều khiển cuộc trò chuyện">
    <p role="status" aria-live="polite" className={styles.status}><span data-active={voice.listening || voice.speaking} />{room.status}</p>
    <div className={styles.actions}>
      {voice.enabled && <>
        <Button variant="ghost" size="icon" disabled={room.presenting} aria-pressed={voice.paused} aria-label={voice.paused ? 'Tiếp tục nghe' : 'Tạm dừng micro'} title={voice.paused ? 'Tiếp tục nghe' : 'Tạm dừng micro'} onClick={voice.pause}>{voice.paused ? <Play size={18} /> : <MicOff size={18} />}</Button>
        <Button variant="ghost" size="icon" disabled={room.busy || voice.paused} aria-label="Nghe lại câu hỏi" title="Nghe lại câu hỏi" onClick={() => void voice.replay()}><RotateCcw size={18} /></Button>
        {(voice.speaking || voice.loadingSpeech) && <Button variant="ghost" size="icon" onClick={room.interrupt} aria-label="Dừng giọng đọc" title="Dừng giọng đọc"><VolumeX size={18} /></Button>}
        {!room.presenting && room.interview.answer.trim() && <Button disabled={room.cannotSubmit} onClick={() => void voice.submit()}><Check size={16} />Tôi đã trả lời xong</Button>}
      </>}
      {room.phase === 'CLOSING' && !voice.enabled && <Button variant="ghost" disabled={room.busy} onClick={room.continueConversation}>Xem kết quả</Button>}
      <Button variant="ghost" size="icon" aria-label="Tùy chỉnh cuộc trò chuyện" title="Tùy chỉnh cuộc trò chuyện" onClick={() => room.setSettingsOpen(true)}><SlidersHorizontal size={18} /></Button>
    </div>
    {voice.countdown && <div className={styles.countdown}><span>Sắp gửi câu trả lời…</span><button onClick={voice.cancelAuto}>Chờ thêm</button></div>}
  </div>;
}

export function VoiceSettings({ room, onStop }: { room: VoiceInterviewRoom; onStop: () => void }) {
  const { voice, session } = room;
  const time = `${Math.floor(room.interview.secondsLeft / 60)}:${String(room.interview.secondsLeft % 60).padStart(2, '0')}`;
  return <Dialog open={room.settingsOpen} onOpenChange={room.setSettingsOpen}><DialogContent className={styles.settingsDialog}>
    <DialogHeader><DialogTitle>Tùy chỉnh cuộc trò chuyện</DialogTitle><DialogDescription>Điều khiển micro, chuyển lượt và kết thúc phiên.</DialogDescription></DialogHeader>
    <p className={styles.sessionInfo}>{room.interview.metadata?.applicationProfileTitle || session?.conversation?.opening.company || 'Phiên phỏng vấn'}{room.phase === 'INTERVIEW' && <> · Đã trả lời {session?.turns.length}/{session?.config.max_questions} câu · Còn {time}</>}</p>
    <label className={styles.setting}><span>Tự gửi khi nói xong</span><input type="checkbox" checked={voice.automatic} onChange={event => voice.setAutomatic(event.target.checked)} /></label>
    <label className={styles.setting}>Khoảng nghỉ để suy nghĩ<select aria-label="Thời gian chờ hết câu" value={voice.silenceMs} onChange={event => voice.setSilenceMs(Number(event.target.value))}>
      <option value={900}>Nhanh · 0,9 giây</option><option value={1200}>Cân bằng · 1,2 giây</option><option value={2200}>Chờ suy nghĩ · 2,2 giây</option>
    </select></label>
    <p className={styles.sessionInfo}>Dùng tai nghe để hạn chế vọng tiếng. Tắt tự gửi nếu bạn muốn chủ động bấm “Tôi đã trả lời xong”.</p>
    {room.phase === 'SELF_INTRODUCTION' && <Button variant="ghost" disabled={room.busy} onClick={room.skipIntroduction}>Bỏ qua giới thiệu</Button>}
    <DialogFooter>
      {room.phase !== 'CLOSING' && <Button variant="ghost" className={styles.endButton} disabled={room.busy} onClick={() => { room.setSettingsOpen(false); onStop(); }}><PhoneOff size={16} />Kết thúc phiên</Button>}
      <Button onClick={() => room.setSettingsOpen(false)}>Xong</Button>
    </DialogFooter>
  </DialogContent></Dialog>;
}

export function VoiceRecovery({ room }: { room: VoiceInterviewRoom }) {
  const { voice } = room;
  if (!voice.error) return null;
  return <div role="alert" className={styles.error}><AlertCircle size={17} /><div><p>{voice.error}</p><div className={styles.retryActions}>
    {voice.retryAvailable && <><Button size="sm" variant="outline" onClick={voice.retry}>Nhận diện lại bản ghi</Button><Button size="sm" variant="ghost" onClick={voice.discard}>Bỏ đoạn ghi lỗi</Button></>}
    {room.presenting && <><Button size="sm" variant="outline" disabled={room.busy} onClick={() => void (voice.enabled ? voice.replay() : voice.enable())}>Thử lại giọng đọc</Button><Button size="sm" variant="ghost" disabled={room.busy} onClick={room.continueConversation}>{room.phase === 'CLOSING' ? 'Xem kết quả' : 'Tiếp tục trò chuyện'}</Button></>}
  </div></div></div>;
}

export function VoiceRecognitionReview({ room }: { room: VoiceInterviewRoom }) {
  const { voice } = room, review = voice.review;
  return <Dialog open={Boolean(review)}><DialogContent showCloseButton={false} className={styles.settingsDialog}>
    <DialogHeader><DialogTitle>Xác nhận lời nói</DialogTitle><DialogDescription>Chọn nội dung đúng với lời bạn nói trước khi gửi.</DialogDescription></DialogHeader>
    {review && <div role="region" aria-label="Xác nhận lời nói" tabIndex={0} className={styles.review}>
      <audio controls preload="none" aria-label="Nghe lại đoạn cần xác nhận" src={`data:audio/wav;base64,${review.audio}`} />
      <blockquote>{review.text}</blockquote><Button variant="outline" onClick={() => voice.confirmReview(review.segment, false)}>Dùng bản nhận diện này</Button>
      {review.alternative && <><blockquote>{review.alternative}</blockquote><Button variant="outline" onClick={() => voice.confirmReview(review.segment, true)}>Dùng bản đối chiếu</Button></>}
      <Button variant="ghost" onClick={() => voice.rejectReview(review.segment)}>Bỏ đoạn này và nói lại</Button>
    </div>}
  </DialogContent></Dialog>;
}
