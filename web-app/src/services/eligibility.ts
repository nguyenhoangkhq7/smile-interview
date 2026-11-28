export interface EligibilityResult {
  condition_id: string;
  type: 'education' | 'gpa' | 'experience' | 'manual';
  priority: 'required' | 'preferred' | 'unspecified';
  jd_quote: string;
  cv_quotes: string[];
  status: 'met' | 'not_met' | 'insufficient_evidence';
  reason: string;
}

export interface EligibilityReport {
  state: 'complete' | 'partial' | 'unavailable';
  results: EligibilityResult[];
}
