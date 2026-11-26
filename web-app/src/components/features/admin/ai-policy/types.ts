export interface AdaptivePolicyConfig {
  coreImportance: number;
  fallbackDepth: number;
  reserveFollowupFraction: number;
  minFailureContexts: number;
  allowExtensionProbes: boolean;
  maxQuestions: number;
  durationSeconds: number;
  maxQuestionsPerObjective: number;
  voiceEnabled: boolean;
  simliAvatarEnabled: boolean;
  dailyQuota: number;
}
