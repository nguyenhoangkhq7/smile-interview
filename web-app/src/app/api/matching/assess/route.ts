import { NextRequest, NextResponse } from 'next/server';
import { query } from '@/lib/db';
import { customFetch } from '@/lib/customFetch';

interface EvidenceItem {
  status: string;
  criteria_name: string;
  cv_evidence?: string;
  jd_requirement?: string;
}

interface ImprovementItem {
  criteria_name: string;
  actionable_advice?: string;
  suggestion?: string;  // fallback / legacy
  priority?: string;
}

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const sessionId = searchParams.get('sessionId');
    const forceRefresh = searchParams.get('forceRefresh') || 'false';
    const resumeId = searchParams.get('resumeId');
    const jdId = searchParams.get('jdId');

    if (!sessionId) {
      return NextResponse.json({ error: 'sessionId is required' }, { status: 400 });
    }

    // Cache lookup: Check if we have an existing completed assessment for this resumeId & jdId
    if (forceRefresh !== 'true' && resumeId && jdId) {
      console.log(`[API Proxy Assess] Checking local DB cache for resumeId=${resumeId}, jdId=${jdId}`);
      const cachedSessionRes = await query(
        `SELECT * FROM sessions 
         WHERE resume_id = $1 AND jd_id = $2 
           AND competency_fit_score IS NOT NULL 
         ORDER BY date DESC LIMIT 1`,
        [resumeId, jdId]
      );

      if (cachedSessionRes.rows.length > 0) {
        const cachedSession = cachedSessionRes.rows[0];
        console.log(`[API Proxy Assess] Cache HIT for resumeId=${resumeId}, jdId=${jdId}. Reusing session assessment.`);

        // Call the Java backend to register/clone the assessment for this sessionId
        const backendUrl = process.env.MATCHING_SERVICE_URL || 'http://localhost:8081';
        const targetUrl = `${backendUrl}/api/v2/assess-resume?sessionId=${sessionId}&forceRefresh=false&fromSessionId=${cachedSession.id}`;
        console.log(`[API Proxy Assess] Triggering Java backend cache/clone at: ${targetUrl}`);
        
        try {
          const authHeader = request.headers.get('Authorization');
          const headers: Record<string, string> = {};
          if (authHeader) {
            headers['Authorization'] = authHeader;
          }
          await customFetch(targetUrl, { headers });
          console.log(`[API Proxy Assess] Java backend cloned successfully for sessionId=${sessionId}`);
        } catch (e) {
          console.error(`[API Proxy Assess] Failed to trigger Java backend clone:`, e);
        }

        const parseJsonField = (val: unknown) => {
          if (typeof val === 'string') {
            try {
              return JSON.parse(val);
            } catch (e) {
              console.error('[API Proxy Assess] Error parsing JSON field:', e);
              return val;
            }
          }
          return val;
        };

        return NextResponse.json({
          id: cachedSession.id,
          sessionId: sessionId, // Preserve the new sessionId requested by client
          competencyFitScore: cachedSession.competency_fit_score,
          technicalDepthScore: cachedSession.technical_depth_score,
          matchLevel: cachedSession.match_level,
          candidateLevel: cachedSession.candidate_level,
          roleTypeDetected: cachedSession.role_type_detected,
          yearsOfExperienceEstimate: cachedSession.years_of_experience_estimate,
          strongAreas: parseJsonField(cachedSession.strong_areas) || [],
          gapAreas: parseJsonField(cachedSession.gap_areas) || [],
          criticalMissingSkills: parseJsonField(cachedSession.critical_missing_skills) || [],
          sectionWiseFeedback: parseJsonField(cachedSession.section_wise_feedback) || {},
          actionableImprovementSuggestions: parseJsonField(cachedSession.actionable_suggestions) || [],
          cached: true,
          createdAt: cachedSession.date || '',
          gateEvidenceItems: parseJsonField(cachedSession.gate_evidence_items) || [],
          mustHaveEvidenceItems: parseJsonField(cachedSession.must_have_evidence_items) || parseJsonField(cachedSession.evidence_items) || [],
          preferToHaveEvidenceItems: parseJsonField(cachedSession.prefer_to_have_evidence_items) || parseJsonField(cachedSession.additional_evidence_items) || [],
          evidenceItems: parseJsonField(cachedSession.must_have_evidence_items) || parseJsonField(cachedSession.evidence_items) || [],
          additionalEvidenceItems: parseJsonField(cachedSession.prefer_to_have_evidence_items) || parseJsonField(cachedSession.additional_evidence_items) || [],
          scoreBreakdown: parseJsonField(cachedSession.score_breakdown) || null,
          topPriorityImprovements: parseJsonField(cachedSession.top_priority_improvements) || [],
          eligibility: parseJsonField(cachedSession.eligibility) || null
        });
      }
    }

    const backendUrl = process.env.MATCHING_SERVICE_URL || 'http://localhost:8081';
    const targetUrl = `${backendUrl}/api/v2/assess-resume?sessionId=${sessionId}&forceRefresh=${forceRefresh}`;

    console.log(`[API Proxy Assess] Forwarding to backend: ${targetUrl}`);
    const authHeader = request.headers.get('Authorization');
    const headers: Record<string, string> = {};
    if (authHeader) {
      headers['Authorization'] = authHeader;
    }
    const backendRes = await customFetch(targetUrl, {
      headers: headers
    });

    if (!backendRes.ok) {
      const errText = await backendRes.text();
      console.error(`[API Proxy Assess] Backend error status ${backendRes.status}:`, errText);
      let detail = errText;
      try {
        const parsed = JSON.parse(errText);
        detail = parsed.message || parsed.error || errText;
      } catch {
        // use raw errText
      }
      const errorMessage = detail
        ? `Backend error (${backendRes.status}): ${detail}`
        : `Backend error: ${backendRes.status} ${backendRes.statusText}`.trim();
      return NextResponse.json({ error: errorMessage }, { status: backendRes.status });
    }

    const data = await backendRes.json();
    
    // Map Java response structure to frontend AssessmentResponse interface
    const overallScore = data.overall_match_score ?? data.score_breakdown?.final_score ?? 0;
    
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

    // Map evidence items to strong / gap / missing categories
    const gateItems = data.gate_evidence_items || [];
    const mustHave = data.must_have_evidence_items || data.evidence_items || [];
    const preferToHave = data.prefer_to_have_evidence_items || data.additional_evidence_items || [];
    const allEvidence = [...gateItems, ...mustHave, ...preferToHave];

    const isMatched = (s?: string) => {
      const st = (s || '').toLowerCase();
      return st === 'matched' || st === 'pass' || st === 'passed';
    };
    const isWeak = (s?: string) => (s || '').toLowerCase() === 'weak';
    const isMissing = (s?: string) => {
      const st = (s || '').toLowerCase();
      return st === 'missing' || st === 'fail' || st === 'failed';
    };

    const strongAreas = (allEvidence as EvidenceItem[])
      .filter((item) => isMatched(item.status))
      .map((item) => item.criteria_name);

    const gapAreas = (allEvidence as EvidenceItem[])
      .filter((item) => isWeak(item.status))
      .map((item) => item.criteria_name);

    const criticalMissingSkills = (allEvidence as EvidenceItem[])
      .filter((item) => isMissing(item.status))
      .map((item) => item.criteria_name);

    // Group section-wise feedback
    const sectionWiseFeedback: Record<string, string> = {};
    if (allEvidence.length > 0) {
      const matchedText = (allEvidence as EvidenceItem[])
        .filter((item) => isMatched(item.status))
        .map((item) => `${item.criteria_name}${item.cv_evidence ? ` (${item.cv_evidence})` : ''}`)
        .join('; ');
      const weakText = (allEvidence as EvidenceItem[])
        .filter((item) => isWeak(item.status))
        .map((item) => `${item.criteria_name}: Yêu cầu JD: ${item.jd_requirement || ''}. Minh chứng CV: ${item.cv_evidence || 'chưa rõ ràng'}.`)
        .join(' | ');
      const missingText = (allEvidence as EvidenceItem[])
        .filter((item) => isMissing(item.status))
        .map((item) => item.criteria_name)
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
    const topImprovements = (data.top_priority_improvements as ImprovementItem[]) || [];
    let actionableImprovementSuggestions: string[] = [];
    if (topImprovements.length > 0) {
      actionableImprovementSuggestions = topImprovements.map(
        (item) => `[${item.criteria_name}] ${item.actionable_advice || item.suggestion || ''}`
      );
    } else {
      const nonMatchedItems = (allEvidence as EvidenceItem[]).filter((item) => !isMatched(item.status));
      actionableImprovementSuggestions = nonMatchedItems.map((item) => {
        const req = item.jd_requirement ? `Yêu cầu: ${item.jd_requirement}. ` : '';
        const reas = (item as unknown as { reasoning?: string }).reasoning || 'Cần bổ sung minh chứng cho kỹ năng này trong CV.';
        return `[${item.criteria_name}] ${req}${reas}`;
      });
    }

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
      gateEvidenceItems: gateItems,
      mustHaveEvidenceItems: mustHave,
      preferToHaveEvidenceItems: preferToHave,
      evidenceItems: mustHave,
      additionalEvidenceItems: preferToHave,
      scoreBreakdown: data.score_breakdown || null,
      topPriorityImprovements: topImprovements,
      eligibility: data.eligibility || null
    });

  } catch (error) {
    const err = error as Error;
    console.error('[API Proxy Assess] Error in proxy assessment:', err);
    return NextResponse.json({ error: err.message || 'Internal server error' }, { status: 500 });
  }
}
