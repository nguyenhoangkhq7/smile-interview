import { NextRequest, NextResponse } from 'next/server';
import { forwardToBackend } from '@/lib/backendClient';

interface EvidenceItem {
  status: string;
  criteria_name: string;
  cv_evidence?: string;
  jd_requirement?: string;
}

interface ImprovementItem {
  criteria_name: string;
  actionable_advice?: string;
  suggestion?: string;
  priority?: string;
}

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const sessionId = searchParams.get('sessionId');
    const forceRefresh = searchParams.get('forceRefresh') || 'false';
    const fromSessionId = searchParams.get('fromSessionId') || '';

    if (!sessionId) {
      return NextResponse.json({ error: 'sessionId is required' }, { status: 400 });
    }

    const endpoint = `/api/v2/assess-resume?sessionId=${sessionId}&forceRefresh=${forceRefresh}${fromSessionId ? `&fromSessionId=${fromSessionId}` : ''}`;
    console.log(`[API Proxy Assess] Forwarding assessment to Spring Boot backend: ${endpoint}`);

    const backendRes = await forwardToBackend(endpoint, request, {
      method: 'GET',
    });

    if (!backendRes.ok) {
      const errText = await backendRes.text();
      console.error(`[API Proxy Assess] Backend error: ${backendRes.status} ${errText}`);
      return NextResponse.json({ error: errText }, { status: backendRes.status });
    }

    const data = await backendRes.json();

    const overallScore = data.overall_match_score ?? data.score_breakdown?.final_score ?? 0;
    const matchLevel = data.overall_match_level || (overallScore >= 80 ? 'High' : overallScore >= 60 ? 'Moderate' : 'Low');
    const candidateLevel = data.seniority_level || 'N/A';
    const roleTypeDetected = data.job_category || 'Software Engineer';
    const yearsOfExperienceEstimate = data.years_of_experience_estimate || '';

    const strongAreas = data.strong_areas || [];
    const gapAreas = data.gap_areas || [];
    const criticalMissingSkills = data.critical_missing_skills || [];
    const sectionWiseFeedback = data.section_wise_feedback || {};

    const gateItems = data.gate_evidence_items || [];
    const mustHave = data.must_have_evidence_items || data.evidence_items || [];
    const preferToHave = data.prefer_to_have_evidence_items || data.additional_evidence_items || [];
    const quickWins = data.quick_wins || [];
    const skillGaps = data.skill_gaps || [];

    const topImprovements = (data.top_priority_improvements || []).map((item: ImprovementItem | string) => {
      if (typeof item === 'string') return item;
      return item.actionable_advice || item.suggestion || item.criteria_name || '';
    }).filter(Boolean);

    const actionableImprovementSuggestions = topImprovements.length > 0 ? topImprovements : (data.actionable_suggestions || []);

    return NextResponse.json({
      id: data.id,
      sessionId: data.session_id || sessionId,
      competencyFitScore: overallScore,
      technicalDepthScore: overallScore,
      matchLevel,
      candidateLevel,
      roleTypeDetected,
      yearsOfExperienceEstimate,
      strongAreas,
      gapAreas,
      criticalMissingSkills,
      sectionWiseFeedback,
      actionableImprovementSuggestions,
      quickWins,
      skillGaps,
      cached: data.cached || false,
      createdAt: data.created_at || '',
      gateEvidenceItems: gateItems,
      mustHaveEvidenceItems: mustHave,
      preferToHaveEvidenceItems: preferToHave,
      evidenceItems: mustHave,
      additionalEvidenceItems: preferToHave,
      scoreBreakdown: data.score_breakdown || null,
      topPriorityImprovements: topImprovements,
      eligibility: data.eligibility || null,
    });
  } catch (error) {
    const err = error as Error;
    console.error('[API Proxy Assess] Error in proxy assessment:', err);
    return NextResponse.json({ error: err.message || 'Internal server error' }, { status: 500 });
  }
}
