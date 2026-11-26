'use client';

import ProtectedRoute from '@/components/auth/ProtectedRoute';
import { EvidenceInterview } from '@/components/features/interview/EvidenceInterview';

export default function InterviewSessionPage() {
  return (
    <ProtectedRoute>
      <EvidenceInterview />
    </ProtectedRoute>
  );
}
