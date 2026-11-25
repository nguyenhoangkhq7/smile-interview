export type SessionFilterTabKey = 'all' | 'completed' | 'in_progress' | 'anomaly';

export interface InspectionPipelineStage {
  id: number;
  stepCode: string;
  title: string;
  description: string;
  leftMeta: string;
  rightMeta: string;
  isErrorMeta?: boolean;
  isLockedMeta?: boolean;
  isVerifiedStep?: boolean;
}

export interface SessionTurnDetail {
  id: string;
  pillLabel: string;
  dotVariant: 'emerald' | 'amber' | 'rose';
  isDeepProbe?: boolean;
  turnBadge: string;
  topicTitle: string;
  timeRange: string;
  depthLabel: string;
  aiStrategyTag: string;
  aiStrategyDescription: string;
  aiTimestamp: string;
  aiTtsQuality: string;
  aiPromptText: string;
  candidateInitials: string;
  candidateName: string;
  candidateTimestamp: string;
  candidateConfidencePct: number;
  audioDuration: string;
  transcriptBeforeMark: string;
  transcriptHighlightedMark: string;
  transcriptAfterMark: string;
  transcriptSecondParagraph: string;
  pitchLabel: string;
  evidenceCode: string;
  rubricLevel:
    | 'DEMONSTRATED_ABOVE_TARGET'
    | 'DEMONSTRATED_AT_TARGET'
    | 'DEMONSTRATED_BELOW_TARGET';
  linkedSkill: string;
  taxonomyCode: string;
  confidenceScoreLabel: string;
  sourceTag: string;
  sourceNote: string;
  exactQuote: string;
}

export interface InspectedSessionData {
  sessionId: string;
  traceToken: string;
  candidateName: string;
  candidateId: string;
  candidateEmail: string;
  candidateAvatarUrl: string;
  workspaceImageUrl: string;
  roleTitle: string;
  shortRoleBadge: string;
  matchingScorePct: number;
  statusLabel: string;
  durationLabel: string;
  fullDurationText: string;
  modeLabel: string;
  overallRatingLabel: string;
  endingReasonLabel: string;
  fallbackUsedLabel: string;
  pipelineStages: InspectionPipelineStage[];
  turns: SessionTurnDetail[];
  metadata: {
    engineCore: string;
    audioPipeline: string;
    evidenceHash: string;
    evaluationSeed: string;
  };
}
