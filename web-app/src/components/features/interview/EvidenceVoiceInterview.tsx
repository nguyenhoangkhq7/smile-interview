'use client';

import { voiceTurn } from '@/services/evidenceInterview';
import { useVoiceInterviewRoom } from '@/hooks/useVoiceInterviewRoom';
import type { InterviewController } from './EvidenceTextInterview';
import { VoiceAvatarPanel, VoiceQuestionPanel, VoiceAnswerPanel } from './VoiceInterviewPanels';
import { VoiceToolbar, VoiceSettings, VoiceRecovery, VoiceRecognitionReview } from './VoiceInterviewControls';
import styles from './EvidenceVoiceInterview.module.css';

export function EvidenceVoiceInterview({ interview, suspended, onStop }: {
  interview: InterviewController; suspended: boolean; onStop: () => void;
}) {
  const room = useVoiceInterviewRoom(interview, suspended);
  if (!room.session || (!voiceTurn(room.session) && !room.session.awaiting_question && !room.session.submission)) return null;
  const gradingFailed = room.session.submission?.status === 'FAILED' && !room.session.is_finished;
  return <section hidden={gradingFailed} style={gradingFailed ? { display: 'none' } : undefined}
    data-interview-mode="VOICE" data-conversation-phase={room.phase} data-answered-count={room.session.turns.length} aria-label="Không gian phỏng vấn giọng nói" className={styles.room}>
    <h1 className="sr-only">Phỏng vấn giọng nói</h1>
    <div className={styles.workspace}>
      <VoiceAvatarPanel room={room} />
      <VoiceQuestionPanel room={room} />
      <VoiceAnswerPanel room={room} />
    </div>
    <VoiceToolbar room={room} />
    <VoiceRecovery room={room} />
    <VoiceSettings room={room} onStop={onStop} />
    <VoiceRecognitionReview room={room} />
  </section>;
}
