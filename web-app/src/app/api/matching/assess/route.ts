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
      skillsAnalysis: {
        analysis: data.section_wise_feedback?.skills_evaluation?.analysis || '',
        criticalMissingSkills: data.section_wise_feedback?.skills_evaluation?.critical_missing_skills || []
      },
      experienceEvaluation: data.section_wise_feedback?.experience_evaluation || '',
      projectEvaluation: data.section_wise_feedback?.project_evaluation || '',
      actionableSuggestions: data.actionable_improvement_suggestions || [],
      cached: data.cached || false,
      createdAt: data.created_at || ''
    });
  } catch (error: any) {
    console.error('[API Proxy Assess] Error in proxy assessment:', error);
    return NextResponse.json({ error: error.message || 'Internal server error' }, { status: 500 });
  }
}
