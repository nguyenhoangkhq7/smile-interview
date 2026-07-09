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
    const authHeader = request.headers.get('Authorization');
    const headers: Record<string, string> = {};
    if (authHeader) {
      headers['Authorization'] = authHeader;
    }
    const backendRes = await fetch(targetUrl, {
      headers: headers
    });

    if (!backendRes.ok) {
      const errText = await backendRes.text();
      console.error(`[API Proxy Assess] Backend error status ${backendRes.status}:`, errText);
      return NextResponse.json({ error: `Backend error: ${backendRes.statusText}` }, { status: backendRes.status });
    }

    const data = await backendRes.json();
    
    // Map Java response structure to frontend AssessmentResponse interface
    const overallScore = data.overall_match_score || 0;
    
    // Compute match level
    let matchLevel = 'Low (Cần cải thiện)';
    if (overallScore >= 80) matchLevel = 'High (Rất tốt)';
    else if (overallScore >= 60) matchLevel = 'Moderate (Khớp)';

    // Candidate level mapping
    const levelMap: Record<string, string> = {
      INTERN: 'Thực tập sinh (Intern)',
      FRESHER: 'Mới tốt nghiệp (Fresher)',
      JUNIOR: 'Dưới 2 năm kinh nghiệm (Junior)',
      MID: '2-5 năm kinh nghiệm (Mid-level)',
      SENIOR: 'Trên 5 năm kinh nghiệm (Senior)',
      LEAD: 'Trưởng nhóm kỹ thuật (Lead)'
    };
    const candidateLevel = levelMap[data.seniority_level] || data.seniority_level || 'N/A';

    // Role type mapping
    const roleTypeDetected = data.job_category || 'N/A';

    // Experience mapping
    const expMap: Record<string, string> = {
      INTERN: 'Thực tập sinh',
      FRESHER: 'Dưới 1 năm',
      JUNIOR: '1 - 2 năm',
      MID: '2 - 5 năm',
      SENIOR: 'Trên 5 năm',
      LEAD: 'Dẫn dắt / Quản lý'
    };
    const yearsOfExperienceEstimate = expMap[data.seniority_level] || data.seniority_level || 'N/A';

    // Map evidence items to strong / gap / missing categories, combining both core and ad-hoc evidence items
    const allEvidence = [
      ...(data.evidence_items || []),
      ...(data.additional_evidence_items || [])
    ];

    const strongAreas = allEvidence
      .filter((item: any) => item.status === 'matched')
      .map((item: any) => item.criteria_name);

    const gapAreas = allEvidence
      .filter((item: any) => item.status === 'weak')
      .map((item: any) => item.criteria_name);

    const criticalMissingSkills = allEvidence
      .filter((item: any) => item.status === 'missing')
      .map((item: any) => item.criteria_name);

    // Group section-wise feedback
    const sectionWiseFeedback: Record<string, string> = {};
    if (allEvidence.length > 0) {
      const matchedText = allEvidence
        .filter((item: any) => item.status === 'matched')
        .map((item: any) => `${item.criteria_name} (${item.cv_evidence || ''})`)
        .join('; ');
      const weakText = allEvidence
        .filter((item: any) => item.status === 'weak')
        .map((item: any) => `${item.criteria_name}: Yêu cầu JD: ${item.jd_requirement || ''}. Minh chứng CV: ${item.cv_evidence || 'chưa rõ ràng'}.`)
        .join(' | ');
      const missingText = allEvidence
        .filter((item: any) => item.status === 'missing')
        .map((item: any) => item.criteria_name)
        .join(', ');

      if (matchedText) {
        sectionWiseFeedback['tech_stack_alignment'] = `Các điểm tương thích tốt: ${matchedText}.`;
      }
      if (weakText) {
        sectionWiseFeedback['project_technical_depth'] = `Các kỹ năng còn yếu hoặc thiếu chiều sâu: ${weakText}.`;
      }
      if (missingText) {
        sectionWiseFeedback['cs_fundamentals'] = `Yêu cầu quan trọng trong JD nhưng thiếu trong CV: ${missingText}.`;
      }
    }

    // Actionable improvement suggestions mapping
    const actionableImprovementSuggestions = (data.top_priority_improvements || [])
      .map((item: any) => `[${item.criteria_name}] ${item.suggestion}`);

    return NextResponse.json({
      id: data.id,
      sessionId: data.session_id,
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
      cached: data.cached || false,
      createdAt: data.created_at || '',
      evidenceItems: data.evidence_items || [],
      additionalEvidenceItems: data.additional_evidence_items || [],
      scoreBreakdown: data.score_breakdown || null,
      topPriorityImprovements: data.top_priority_improvements || []
    });
  } catch (error: any) {
    console.error('[API Proxy Assess] Error in proxy assessment:', error);
    return NextResponse.json({ error: error.message || 'Internal server error' }, { status: 500 });
  }
}
