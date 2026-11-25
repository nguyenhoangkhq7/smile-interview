export type ServiceIconKey =
  | 'database'
  | 'bolt'
  | 'cloud'
  | 'bell'
  | 'brain'
  | 'tree'
  | 'mic'
  | 'avatar';

export interface ServiceHealthCardItem {
  id: string;
  name: string;
  subtitle: string;
  iconKey: ServiceIconKey;
  iconAccent: 'primary' | 'secondary';
  latencyLabel: string;
  latencyValue: string;
  latencyColor: 'tertiary' | 'secondary';
  latencyBarPct: number;
  metaLabel: string;
  metaValue: string;
  metaHighlight?: boolean;
  lastCheckedText: string;
}

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

export interface AcademicFrozenParam {
  key: string;
  description: string;
  valueLabel: string;
}
