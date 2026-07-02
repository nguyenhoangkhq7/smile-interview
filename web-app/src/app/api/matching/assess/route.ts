import { NextRequest, NextResponse } from 'next/server';

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const sessionId = searchParams.get('sessionId');
    const forceRefresh = searchParams.get('forceRefresh') || 'false';

    if (!sessionId) {
      return NextResponse.json({ error: 'sessionId is required' }, { status: 400 });
    }

    const backendUrl = process.env.MATCHING_SERVICE_URL || 'http://localhost:8081';
    const targetUrl = `${backendUrl}/api/v2/assess-resume?sessionId=${sessionId}&forceRefresh=${forceRefresh}`;

    console.log(`[API Proxy Assess] Forwarding to backend: ${targetUrl}`);
    const backendRes = await fetch(targetUrl);

    if (!backendRes.ok) {
      const errText = await backendRes.text();
      console.error(`[API Proxy Assess] Backend error status ${backendRes.status}:`, errText);
      return NextResponse.json({ error: `Backend error: ${backendRes.statusText}` }, { status: backendRes.status });
    }

    const data = await backendRes.json();
    
    // Map Java response structure to frontend AssessmentResponse interface
    return NextResponse.json({
      id: data.id,
      sessionId: data.session_id,
      competencyFitScore: data.competency_fit_score || 0,
      technicalDepthScore: data.technical_depth_score || 0,
      matchLevel: data.match_level || '',
      candidateLevel: data.candidate_level || '',
      roleTypeDetected: data.role_type_detected || '',
      yearsOfExperienceEstimate: data.years_of_experience_estimate || '',
      strongAreas: data.strong_areas || [],
      gapAreas: data.gap_areas || [],
      criticalMissingSkills: data.critical_missing_skills || [],
      sectionWiseFeedback: data.section_wise_feedback || {},
      actionableImprovementSuggestions: data.actionable_improvement_suggestions || [],
      cached: data.cached || false,
      createdAt: data.created_at || ''
    });
  } catch (error: any) {
    console.error('[API Proxy Assess] Error in proxy assessment:', error);
    return NextResponse.json({ error: error.message || 'Internal server error' }, { status: 500 });
  }
}
