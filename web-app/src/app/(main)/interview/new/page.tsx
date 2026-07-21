'use client';

import React, { useEffect, useState, useRef, DragEvent, ChangeEvent } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { cvJdMatchingService, AssessmentResponse } from '@/services/cvJdMatching';
import { historyService } from '@/services/historyService';
import { Calendar, FileText, UploadCloud, FolderOpen, Briefcase, CheckCircle, XCircle, Brain, Lightbulb, X, AlertTriangle, Check, AlertCircle, TrendingUp, UserCheck, Award, ShieldCheck, RefreshCw, Target, Wrench, Search, ChevronDown, Eye } from 'lucide-react';
import styles from './new.module.css';
import ProtectedRoute from '@/components/auth/ProtectedRoute';
import HighlightedText from '@/components/HighlightedText';
import dynamic from 'next/dynamic';
const PdfViewerModal = dynamic(() => import('@/components/common/PdfViewerModal'), { ssr: false });


import { ActiveSessionsList, type ActiveSession } from '@/components/interview/ActiveSessionsList';
import { useAuthStore } from '@/store/authStore';

// ── Custom Searchable Combobox Component ─────────────────────────────────────

interface ComboboxOption {
  id: number;
  label: string;
  date: string;
}

interface CustomComboboxProps {
  options: ComboboxOption[];
  selectedId: number | null;
  onSelect: (id: number | null) => void;
  placeholder: string;
  searchPlaceholder: string;
  icon: React.ReactNode;
}

function CustomCombobox({
  options,
  selectedId,
  onSelect,
  placeholder,
  searchPlaceholder,
  icon,
}: CustomComboboxProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  const selectedOption = options.find((opt) => opt.id === selectedId);
  const filteredOptions = options.filter((opt) =>
    opt.label.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div ref={wrapperRef} style={{ position: 'relative', width: '100%', zIndex: 10 }}>
      {/* Trigger Button */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0.75rem 1rem',
          backgroundColor: '#ffffff',
          border: isOpen ? '1px solid #ea580c' : '1px solid #cbd5e1',
          borderRadius: '0.5rem',
          fontSize: '0.9rem',
          color: selectedOption ? '#0f172a' : '#64748b',
          fontWeight: selectedOption ? 500 : 400,
          cursor: 'pointer',
          outline: 'none',
          boxShadow: isOpen ? '0 0 0 3px rgba(234, 88, 12, 0.12)' : 'none',
          transition: 'all 0.2s',
          textAlign: 'left',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', minWidth: 0, flex: 1 }}>
          {icon}
          <span style={{
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            width: '100%'
          }}>
            {selectedOption ? selectedOption.label : placeholder}
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', flexShrink: 0 }}>
          {selectedOption && (
            <span
              onClick={(e) => {
                e.stopPropagation();
                onSelect(null);
              }}
              style={{
                cursor: 'pointer',
                color: '#94a3b8',
                padding: '0.1rem',
                borderRadius: '50%',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
              onMouseOver={(e) => e.currentTarget.style.color = '#ef4444'}
              onMouseOut={(e) => e.currentTarget.style.color = '#94a3b8'}
            >
              <X size={14} />
            </span>
          )}
          <ChevronDown
            size={16}
            style={{
              color: '#94a3b8',
              transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)',
              transition: 'transform 0.2s'
            }}
          />
        </div>
      </button>

      {/* Dropdown Panel */}
      {isOpen && (
        <div style={{
          position: 'absolute',
          top: 'calc(100% + 5px)',
          left: 0,
          right: 0,
          backgroundColor: '#ffffff',
          border: '1px solid #cbd5e1',
          borderRadius: '0.5rem',
          boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.05)',
          zIndex: 50,
          padding: '0.5rem',
          display: 'flex',
          flexDirection: 'column',
          gap: '0.5rem',
        }}>
          {/* Search Box */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            padding: '0.4rem 0.60rem',
            backgroundColor: '#f8fafc',
            border: '1px solid #e2e8f0',
            borderRadius: '0.375rem',
          }}>
            <Search size={14} style={{ color: '#94a3b8' }} />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder={searchPlaceholder}
              style={{
                border: 'none',
                backgroundColor: 'transparent',
                fontSize: '0.85rem',
                outline: 'none',
                width: '100%',
                color: '#334155',
              }}
            />
          </div>

          {/* List Options */}
          <div style={{
            maxHeight: '220px',
            overflowY: 'auto',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.2rem',
          }}>
            {filteredOptions.length === 0 ? (
              <div style={{
                padding: '1.5rem 0.5rem',
                textAlign: 'center',
                fontSize: '0.8rem',
                color: '#94a3b8',
              }}>
                Không tìm thấy kết quả
              </div>
            ) : (
              filteredOptions.map((opt) => {
                const isSelected = opt.id === selectedId;
                return (
                  <button
                    key={opt.id}
                    type="button"
                    onClick={() => {
                      onSelect(opt.id);
                      setIsOpen(false);
                      setSearchTerm('');
                    }}
                    style={{
                      width: '100%',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '0.5rem 0.75rem',
                      borderRadius: '0.375rem',
                      border: 'none',
                      backgroundColor: isSelected ? '#fff7ed' : 'transparent',
                      color: isSelected ? '#ea580c' : '#334155',
                      fontSize: '0.85rem',
                      textAlign: 'left',
                      cursor: 'pointer',
                      transition: 'background-color 0.15s',
                    }}
                    onMouseOver={(e) => {
                      if (!isSelected) {
                        e.currentTarget.style.backgroundColor = '#f1f5f9';
                      }
                    }}
                    onMouseOut={(e) => {
                      if (!isSelected) {
                        e.currentTarget.style.backgroundColor = 'transparent';
                      }
                    }}
                  >
                    <span style={{
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                      maxWidth: '75%',
                      fontWeight: isSelected ? 600 : 400,
                    }} title={opt.label}>
                      {opt.label}
                    </span>
                    <span style={{
                      fontSize: '0.72rem',
                      color: isSelected ? '#ea580c' : '#94a3b8',
                      opacity: 0.8,
                    }}>
                      {opt.date}
                    </span>
                  </button>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Data Adapter: derive Jobscan keyword arrays from AI evaluation results ────
//
// Iterates the evidenceItems / additionalEvidenceItems arrays (same data that
// renders the AI Cards) and extracts raw keyword tokens per-criterion.
//
// Enhanced extraction pipeline for splitCriteriaName:
//   1. Pull out terms inside parentheses as extra tokens (e.g. "(REST/GraphQL)" → ["REST", "GraphQL"])
//   2. Strip the parenthetical from the main string
//   3. Remove common descriptor filler words that never appear verbatim in CVs
//   4. Split on all compound delimiters: & / | ,
//   5. Filter out blank / single-character noise tokens

/** Words that are purely descriptive and will never match raw CV/JD text as standalone terms. */
const DESCRIPTOR_WORDS = new Set([
  'fundamentals', 'fundamental', 'practices', 'practice',
  'ecosystem', 'architecture', 'design', 'management',
  'principles', 'principle', 'concepts', 'concept',
  'techniques', 'technique', 'methodology', 'methodologies',
  'basics', 'advanced', 'modern', 'best', 'patterns', 'pattern',
  'tools', 'tool', 'skills', 'skill', 'knowledge', 'experience',
  'proficiency', 'understanding', 'overview', 'introduction',
  'development', 'implementation', 'integration', 'systems', 'system',
  'and', 'or', 'the', 'for', 'with', 'using', 'via',
  // Vietnamese prepositions and common filler words
  'trong', 'tại', 'ở', 'cho', 'với', 'như', 'các', 'những', 'của', 'và', 'hoặc',
  'để', 'về', 'bằng', 'từ', 'đến', 'trên', 'dưới', 'một', 'hai', 'ba', 'nhiều',
  // Vietnamese descriptive terms (often used in criteria names)
  'phát', 'triển', 'xây', 'dựng', 'sử', 'dụng', 'thiết', 'kế', 'quản', 'lý',
  'tối', 'ưu', 'triển', 'khai', 'áp', 'dụng', 'thực', 'hiện', 'phân', 'tích',
  'đánh', 'giá', 'chức', 'năng', 'hệ', 'thống', 'công', 'cụ', 'kỹ', 'năng',
  'kinh', 'nghiệm', 'kiến', 'thức', 'hiểu', 'biết', 'nền', 'tảng', 'ngôn', 'ngữ',
  'quy', 'trình', 'phương', 'pháp', 'dự', 'án', 'ứng', 'dụng', 'vị', 'trí',
  'yêu', 'cầu', 'tiêu', 'chí', 'đối', 'chiếu', 'khả', 'năng'
]);

function splitCriteriaName(name: string): string[] {
  if (!name) return [];

  const tokens: string[] = [];

  // Step 1: extract terms inside parentheses as extra tokens
  // e.g. "API Design (REST/GraphQL)" → parenthetical content "REST/GraphQL"
  const parenMatches = name.match(/\(([^)]+)\)/g) || [];
  for (const paren of parenMatches) {
    const inner = paren.replace(/[()]/g, '');
    // Split the inner part too
    inner.split(/[&/|,\s]+/).forEach((t) => tokens.push(t.trim()));
  }

  // Step 2: strip all parenthetical groups from the main name
  let cleaned = name.replace(/\([^)]*\)/g, ' ');

  // Step 3: split on compound delimiters
  cleaned.split(/[&/|,]+/).forEach((segment) => {
    // Step 4: within each segment, further split on whitespace and push individual words
    segment.split(/\s+/).forEach((word) => tokens.push(word.trim()));
  });

  // Step 5: normalise, drop descriptor words and short noise tokens
  return tokens
    .map((t) => t.replace(/[^a-zA-Z0-9#+.]/g, '').trim()) // keep alphanumeric + tech chars like C#, C++, .NET
    .filter((t) => t.length >= 2)
    .filter((t) => !DESCRIPTOR_WORDS.has(t.toLowerCase()));
}

interface DerivedKeywords {
  matchingSkills: string[];  // from matched items
  variationSkills: string[]; // from weak items
  missingSkills: string[];   // from missing items
}

function extractKeywordsFromEvaluation(evidenceItems: any[], additionalEvidenceItems: any[]): DerivedKeywords {
  const matchingSkills: string[] = [];
  const variationSkills: string[] = [];
  const missingSkills: string[] = [];

  const allItems = [...(evidenceItems || []), ...(additionalEvidenceItems || [])];

  for (const item of allItems) {
    const name: string = item.criteria_name || '';
    const status: string = (item.status || '').toLowerCase();
    const tokens = splitCriteriaName(name);

    if (status === 'matched') {
      matchingSkills.push(...tokens);
    } else if (status === 'weak') {
      variationSkills.push(...tokens);
    } else if (status === 'missing') {
      missingSkills.push(...tokens);
    }
  }

  // Deduplicate while preserving order
  const dedupe = (arr: string[]) => [...new Set(arr)];
  return {
    matchingSkills: dedupe(matchingSkills),
    variationSkills: dedupe(variationSkills),
    missingSkills: dedupe(missingSkills)
  };
}

const getDisplayRoleTitle = (rawRole: string | null | undefined) => {
  if (!rawRole) return 'Software Engineer';
  const roleUpper = rawRole.toUpperCase();
  const roleMapping: Record<string, string> = {
    BACKEND: 'Backend Engineer',
    FRONTEND: 'Frontend Engineer',
    FULLSTACK: 'Fullstack Engineer',
    DEVOPS: 'DevOps Engineer',
    DATA_ENGINEERING: 'Data Engineer',
    ML_ENGINEERING: 'ML Engineer',
    MOBILE: 'Mobile Developer',
    SECURITY: 'Security Engineer',
    QA: 'QA/QC Engineer',
    OTHER: 'Software Engineer'
  };
  return roleMapping[roleUpper] || rawRole;
};

export default function NewInterviewPage() {
  const router = useRouter();
  const { user } = useAuthStore();
  const [roleTitle, setRoleTitle] = useState('React Frontend Engineer');

  // Files & Sources
  const [cvFile, setCvFile] = useState<File | null>(null);
  const [jdFile, setJdFile] = useState<File | null>(null);
  const [jdText, setJdText] = useState('');
  const [jdInputType, setJdInputType] = useState<'file' | 'text'>('file'); // Note: we'll use jdSource for detailed tabs, keeping this for backward compatibility

  // Saved database entities
  const [savedResumes, setSavedResumes] = useState<any[]>([]);
  const [savedJds, setSavedJds] = useState<any[]>([]);
  const [selectedResumeId, setSelectedResumeId] = useState<number | null>(null);
  const [selectedJdId, setSelectedJdId] = useState<number | null>(null);
  const [cvSource, setCvSource] = useState<'upload' | 'saved' | 'default'>('upload');
  const [jdSource, setJdSource] = useState<'upload' | 'text' | 'saved'>('upload');

  // Drag states
  const [dragOverCv, setDragOverCv] = useState(false);
  const [dragOverJd, setDragOverJd] = useState(false);

  // Error and UI states
  const [cvError, setCvError] = useState<string | null>(null);
  const [jdError, setJdError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [analyzing, setAnalyzing] = useState(false);
  const [isCloning, setIsCloning] = useState<string | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);

  // PDF Viewer Modal State
  const [viewerOpen, setViewerOpen] = useState(false);
  const [viewerUrl, setViewerUrl] = useState('');
  const [viewerTitle, setViewerTitle] = useState('');

  // Result state
  const [assessment, setAssessment] = useState<AssessmentResponse | null>(null);
  const [criteriaFilter, setCriteriaFilter] = useState<'all' | 'matched' | 'weak' | 'missing'>('all');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [ingested, setIngested] = useState(false);
  const [activeSessions, setActiveSessions] = useState<ActiveSession[]>([]);

  const fileInputCvRef = useRef<HTMLInputElement>(null);
  const fileInputJdRef = useRef<HTMLInputElement>(null);

  // Jobscan keyword matching states
  const [keywordMetadata, setKeywordMetadata] = useState<any>(null);
  const [rawCvText, setRawCvText] = useState<string | null>(null);
  const [rawJdText, setRawJdText] = useState<string | null>(null);
  const [activeView, setActiveView] = useState<'ai-cards' | 'visual-match'>('ai-cards');
  // Display names for the Jobscan panel headers (file name labels)
  const [cvDisplayName, setCvDisplayName] = useState<string>('CV');
  const [jdDisplayName, setJdDisplayName] = useState<string>('JD');
  // resumeId / jdId for the currently loaded assessment (used to fetch raw texts from DB)
  const [activeResumeId, setActiveResumeId] = useState<number | null>(null);
  const [activeJdId, setActiveJdId] = useState<number | null>(null);

  // React to sessionId changes to pull raw text and match values from sessionStorage.
  // Fallback: if sessionStorage is empty (e.g. loaded from history / different tab),
  // fetch raw texts directly from the DB via the stored resumeId / jdId.
  useEffect(() => {
    if (!sessionId) {
      setKeywordMetadata(null);
      setRawCvText(null);
      setRawJdText(null);
      return;
    }
    try {
      const raw = sessionStorage.getItem(`keyword_data_${sessionId}`);
      if (raw) {
        const parsed = JSON.parse(raw);
        setKeywordMetadata(parsed.keywordMetadata ?? null);
        setRawCvText(parsed.rawCvText ?? null);
        setRawJdText(parsed.rawJdText ?? null);
        return; // sessionStorage hit – done
      }
    } catch (e) {
      console.warn('[NewPage] Could not read keyword data from sessionStorage:', e);
    }

    // sessionStorage miss – fetch raw texts from the DB
    if (!activeResumeId && !activeJdId) return;

    const params = new URLSearchParams();
    if (activeResumeId) params.set('resumeId', String(activeResumeId));
    if (activeJdId) params.set('jdId', String(activeJdId));

    fetch(`/api/matching/raw-texts?${params.toString()}`)
      .then((res) => res.json())
      .then((data) => {
        setKeywordMetadata(null); // no LLM keyword metadata on this path; use adapter
        setRawCvText(data.rawCvText ?? null);
        setRawJdText(data.rawJdText ?? null);
        if (data.cvFilename) setCvDisplayName(data.cvFilename);
        if (data.jdFilename) setJdDisplayName(data.jdFilename);
      })
      .catch((err) => {
        console.error('[NewPage] Failed to fetch raw texts from DB:', err);
      });
  }, [sessionId, activeResumeId, activeJdId]);

  useEffect(() => {
    let mounted = true;

    async function loadActiveSessions() {
      try {
        const sessions = await historyService.getHistory();
        if (!mounted) return;

        const inProgressSessions = sessions
          .filter((item) => item.status !== 'Completed')
          .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
          .map((item) => ({
            sessionId: item.id,
            roleTitle: item.roleTitle,
            cvFilename: item.cvFilename,
            jdFilename: item.jdFilename,
            status: item.status,
            date: item.date,
            hasAssessment: item.competencyFitScore !== undefined
          }));

        setActiveSessions(inProgressSessions);
      } catch (error) {
        console.error('[NewInterviewPage] Failed to load active sessions:', error);
      }
    }

    async function loadSavedEntities() {
      try {
        const resumesRes = await fetch('/api/resumes');
        if (resumesRes.ok && mounted) {
          const resumes = await resumesRes.json();
          setSavedResumes(resumes);
        }
        const jdsRes = await fetch('/api/jds');
        if (jdsRes.ok && mounted) {
          const jds = await jdsRes.json();
          setSavedJds(jds);
        }
      } catch (error) {
        console.error('[NewInterviewPage] Failed to load saved resumes/JDs:', error);
      }
    }

    loadActiveSessions();
    loadSavedEntities();

    return () => {
      mounted = false;
    };
  }, []);

  // ── Drag & Drop Handlers ──
  const handleDragOver = (e: DragEvent<HTMLDivElement>, zone: 'cv' | 'jd') => {
    e.preventDefault();
    if (zone === 'cv') setDragOverCv(true);
    else setDragOverJd(true);
  };

  const handleDragLeave = (zone: 'cv' | 'jd') => {
    if (zone === 'cv') setDragOverCv(false);
    else setDragOverJd(false);
  };

  const validateFile = (file: File, zone: 'cv' | 'jd'): boolean => {
    const isCv = zone === 'cv';
    const maxSize = 10 * 1024 * 1024; // 10MB

    if (isCv) {
      if (file.type !== 'application/pdf' && !file.name.endsWith('.pdf')) {
        setCvError('CV phải ở định dạng PDF (.pdf)');
        return false;
      }
      setCvError(null);
    } else {
      const allowedTypes = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'application/msword'];
      const ext = file.name.split('.').pop()?.toLowerCase();
      if (!allowedTypes.includes(file.type) && ext !== 'pdf' && ext !== 'docx' && ext !== 'doc') {
        setJdError('JD phải ở định dạng PDF (.pdf) hoặc Word (.docx, .doc)');
        return false;
      }
      setJdError(null);
    }

    if (file.size > maxSize) {
      if (isCv) setCvError('Kích thước tệp tin CV không được vượt quá 10MB');
      else setJdError('Kích thước tệp tin JD không được vượt quá 10MB');
      return false;
    }

    return true;
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>, zone: 'cv' | 'jd') => {
    e.preventDefault();
    handleDragLeave(zone);

    const files = e.dataTransfer.files;
    if (files.length > 0) {
      const file = files[0];
      if (validateFile(file, zone)) {
        if (zone === 'cv') setCvFile(file);
        else setJdFile(file);
      }
    }
  };

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>, zone: 'cv' | 'jd') => {
    const files = e.target.files;
    if (files && files.length > 0) {
      const file = files[0];
      if (validateFile(file, zone)) {
        if (zone === 'cv') setCvFile(file);
        else setJdFile(file);
      }
    }
  };

  const triggerFileSelect = (zone: 'cv' | 'jd') => {
    if (zone === 'cv') fileInputCvRef.current?.click();
    else fileInputJdRef.current?.click();
  };

  const handleResumeSession = async (resumeSessionId: string) => {
    try {
      const session = await historyService.getSessionById(resumeSessionId);
      if (session) {
        const hasQuestions = session.questions && session.questions.length > 0;
        const hasQuestionsGenerated = session.actionableSuggestions && session.actionableSuggestions.length > 0;

        // Case 1: CV & JD were uploaded/ingested, but CV assessment hasn't run yet
        if (session.competencyFitScore === undefined && !hasQuestions) {
          setSessionId(session.id);
          setRoleTitle(session.roleTitle);
          setIngested(true);
          setAssessment(null);
          return;
        }

        // Case 2: CV assessment is done, but Question Bank hasn't been generated yet
        if (session.competencyFitScore !== undefined && !hasQuestions && !hasQuestionsGenerated) {
          setAssessment({
            id: '',
            sessionId: session.id,
            competencyFitScore: session.competencyFitScore || 0,
            technicalDepthScore: session.technicalDepthScore || 0,
            matchLevel: session.matchLevel || '',
            candidateLevel: session.candidateLevel || '',
            roleTypeDetected: session.roleTypeDetected || '',
            yearsOfExperienceEstimate: session.yearsOfExperienceEstimate || '',
            strongAreas: session.strongAreas || [],
            gapAreas: session.gapAreas || [],
            criticalMissingSkills: session.criticalMissingSkills || [],
            sectionWiseFeedback: session.sectionWiseFeedback || {},
            actionableImprovementSuggestions: session.actionableSuggestions || [],
            cached: true,
            createdAt: session.date,
            evidenceItems: session.evidenceItems || [],
            additionalEvidenceItems: session.additionalEvidenceItems || [],
            scoreBreakdown: session.scoreBreakdown || null,
            topPriorityImprovements: session.topPriorityImprovements || []
          });
          setSessionId(session.id);
          setRoleTitle(session.roleTitle);
          setIngested(true);
          return;
        }
      }
    } catch (err) {
      console.error('Error resuming session:', err);
    }
    router.push(`/interview/session/${resumeSessionId}`);
  };

  const handleViewAssessment = async (resumeSessionId: string) => {
    try {
      const session = await historyService.getSessionById(resumeSessionId);
      if (session) {
        setAssessment({
          id: '',
          sessionId: session.id,
          competencyFitScore: session.competencyFitScore || 0,
          technicalDepthScore: session.technicalDepthScore || 0,
          matchLevel: session.matchLevel || '',
          candidateLevel: session.candidateLevel || '',
          roleTypeDetected: session.roleTypeDetected || '',
          yearsOfExperienceEstimate: session.yearsOfExperienceEstimate || '',
          strongAreas: session.strongAreas || [],
          gapAreas: session.gapAreas || [],
          criticalMissingSkills: session.criticalMissingSkills || [],
          sectionWiseFeedback: session.sectionWiseFeedback || {},
          actionableImprovementSuggestions: session.actionableSuggestions || [],
          cached: true,
          createdAt: session.date,
          evidenceItems: session.evidenceItems || [],
          additionalEvidenceItems: session.additionalEvidenceItems || [],
          scoreBreakdown: session.scoreBreakdown || null,
          topPriorityImprovements: session.topPriorityImprovements || []
        });
        setSessionId(session.id);
        setRoleTitle(session.roleTitle);
        setIngested(true);

        // Persist the resumeId / jdId so the sessionId useEffect can fetch raw texts from DB
        if (session.resumeId) setActiveResumeId(session.resumeId);
        if (session.jdId) setActiveJdId(session.jdId);

        // Set display names from history immediately (may be refined by the DB fetch)
        if (session.cvFilename) setCvDisplayName(session.cvFilename);
        if (session.jdFilename) setJdDisplayName(session.jdFilename);

        if (typeof window !== 'undefined') {
          const url = new URL(window.location.href);
          url.searchParams.set('sessionId', resumeSessionId);
          window.history.pushState({}, '', url.toString());
        }
      }
    } catch (err) {
      console.error('Error loading assessment:', err);
    }
  };

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const params = new URLSearchParams(window.location.search);
    const urlSessionId = params.get('sessionId');
    if (urlSessionId) {
      handleViewAssessment(urlSessionId);
    }
  }, []);

  const handleUploadAndIngest = async () => {
    // Validate CV selection
    if (cvSource === 'upload' && !cvFile) return;
    if ((cvSource === 'saved' || cvSource === 'default') && !selectedResumeId) return;

    // Validate JD selection
    if (jdSource === 'upload' && !jdFile) return;
    if (jdSource === 'text' && !jdText.trim()) return;
    if (jdSource === 'saved' && !selectedJdId) return;

    setUploading(true);
    setApiError(null);

    // Simulate upload progress
    let progress = 0;
    const interval = setInterval(() => {
      progress += 20;
      if (progress >= 100) {
        clearInterval(interval);
        setUploadProgress(100);

        // Start API pipeline
        setTimeout(async () => {
          setUploading(false);
          setAnalyzing(true);
          const newSessionId = `session-${Date.now()}`;
          try {
            const displayCvName = cvSource === 'upload' && cvFile
              ? cvFile.name
              : (savedResumes.find(r => r.id === selectedResumeId)?.file_name || 'Saved_CV.pdf');

            const displayJdName = jdSource === 'upload' && jdFile
              ? jdFile.name
              : (jdSource === 'text'
                ? 'JD_Pasted_Text.txt'
                : (savedJds.find(j => j.id === selectedJdId)?.title || 'Saved_JD.pdf'));

            const initialRoleTitle = 
              jdSource === 'saved' && selectedJdId
                ? (savedJds.find(j => j.id === selectedJdId)?.title || 'Software Engineer')
                : jdSource === 'upload' && jdFile
                ? jdFile.name.replace(/\.[^/.]+$/, '').replace(/[-_]/g, ' ')
                : 'Software Engineer';

            setRoleTitle(initialRoleTitle);

            await historyService.saveSession({
              id: newSessionId,
              date: new Date().toISOString(),
              interviewType: 'Technical',
              roleTitle: initialRoleTitle,
              cvFilename: displayCvName,
              jdFilename: displayJdName,
              status: 'In progress',
              questions: [],
              resumeId: (cvSource === 'saved' || cvSource === 'default') ? (selectedResumeId || undefined) : undefined,
              jdId: jdSource === 'saved' ? (selectedJdId || undefined) : undefined
            });

            // Step 1: Ingestion
            const ingestRes = await cvJdMatchingService.ingestCvJd(
              newSessionId,
              cvSource === 'upload' ? cvFile : null,
              jdSource === 'upload' ? jdFile : null,
              jdSource === 'text' ? jdText : null,
              (cvSource === 'saved' || cvSource === 'default') ? selectedResumeId : null,
              jdSource === 'saved' ? selectedJdId : null
            );

            // If new files were uploaded and saved, update the IDs
            if (ingestRes.resumeId) setSelectedResumeId(ingestRes.resumeId);
            if (ingestRes.jdId) setSelectedJdId(ingestRes.jdId);

            // Persist Jobscan keyword metadata + raw texts to sessionStorage so the
            // result page can render the visual skill comparison without an extra API call.
            if (ingestRes.keywordMetadata || ingestRes.rawCvText || ingestRes.rawJdText) {
              try {
                sessionStorage.setItem(
                  `keyword_data_${newSessionId}`,
                  JSON.stringify({
                    keywordMetadata: ingestRes.keywordMetadata ?? { matching_skills: [], missing_skills: [] },
                    rawCvText: ingestRes.rawCvText ?? null,
                    rawJdText: ingestRes.rawJdText ?? null,
                  })
                );
              } catch (storageErr) {
                console.warn('[Ingest] Could not persist keyword data to sessionStorage:', storageErr);
              }
            }

            setSessionId(newSessionId);
            setIngested(true);
            // Store active IDs + display names for the Jobscan panel headers
            const finalResumeId = ingestRes.resumeId || (cvSource !== 'upload' ? selectedResumeId : null);
            const finalJdId = ingestRes.jdId || (jdSource === 'saved' ? selectedJdId : null);
            if (finalResumeId) setActiveResumeId(finalResumeId);
            if (finalJdId) setActiveJdId(finalJdId);
            setCvDisplayName(displayCvName);
            setJdDisplayName(displayJdName);

            // Directly set raw texts to component state to guarantee immediate availability
            if (ingestRes.rawCvText) setRawCvText(ingestRes.rawCvText);
            if (ingestRes.rawJdText) setRawJdText(ingestRes.rawJdText);

          } catch (err: any) {
            console.error('Ingestion error:', err);
            setApiError('Đã xảy ra lỗi khi tải lên và xử lý tài liệu. Vui lòng thử lại sau.');
          } finally {
            setAnalyzing(false);
          }
        }, 300);
      } else {
        setUploadProgress(progress);
      }
    }, 100);
  };

  const handleRunAssessment = async (forceRefresh: boolean | React.MouseEvent = false) => {
    if (!sessionId) return;
    const isForce = forceRefresh === true;
    setAnalyzing(true);
    setApiError(null);
    try {
      const result = await cvJdMatchingService.getAssessment(
        sessionId,
        isForce,
        selectedResumeId,
        selectedJdId
      );
      setAssessment(result);

      // Save CV match results to database immediately so history is preserved
      const displayCvName = cvSource === 'upload' && cvFile
        ? cvFile.name
        : (savedResumes.find(r => r.id === selectedResumeId)?.file_name || 'Saved_CV.pdf');

      const displayJdName = jdSource === 'upload' && jdFile
        ? jdFile.name
        : (jdSource === 'text'
          ? 'JD_Pasted_Text.txt'
          : (savedJds.find(j => j.id === selectedJdId)?.title || 'Saved_JD.pdf'));

      const finalRoleTitle = result.roleTypeDetected
        ? getDisplayRoleTitle(result.roleTypeDetected)
        : jdSource === 'saved' && selectedJdId
        ? (savedJds.find(j => j.id === selectedJdId)?.title || 'Software Engineer')
        : jdSource === 'upload' && jdFile
        ? jdFile.name.replace(/\.[^/.]+$/, '').replace(/[-_]/g, ' ')
        : 'Software Engineer';

      setRoleTitle(finalRoleTitle);

      await historyService.saveSession({
        id: result.sessionId || sessionId,
        date: new Date().toISOString(),
        interviewType: 'Technical',
        roleTitle: finalRoleTitle,
        cvFilename: displayCvName,
        jdFilename: displayJdName,
        resumeId: selectedResumeId || undefined,
        jdId: selectedJdId || undefined,
        status: 'In progress',
        questions: [],
        replaceQuestions: false,
        competencyFitScore: result.competencyFitScore,
        technicalDepthScore: result.technicalDepthScore,
        matchLevel: result.matchLevel,
        candidateLevel: result.candidateLevel,
        roleTypeDetected: result.roleTypeDetected,
        yearsOfExperienceEstimate: result.yearsOfExperienceEstimate,
        strongAreas: result.strongAreas,
        gapAreas: result.gapAreas,
        criticalMissingSkills: result.criticalMissingSkills,
        sectionWiseFeedback: result.sectionWiseFeedback,
        actionableSuggestions: result.actionableImprovementSuggestions,
        evidenceItems: result.evidenceItems,
        additionalEvidenceItems: result.additionalEvidenceItems,
        scoreBreakdown: result.scoreBreakdown,
        topPriorityImprovements: result.topPriorityImprovements,
        eligibility: result.eligibility
      });
    } catch (err: any) {
      console.error('Assessment error:', err);
      setApiError('Đã xảy ra lỗi khi kết nối với máy chủ AI. Vui lòng thử lại sau.');
    } finally {
      setAnalyzing(false);
    }
  };

  const [generating, setGenerating] = useState(false);

  const handleContinueToSelection = async () => {
    if (!assessment || !sessionId) return;
    setGenerating(true);
    setApiError(null);
    try {
      const displayCvName = cvSource === 'upload' && cvFile
        ? cvFile.name
        : (savedResumes.find(r => r.id === selectedResumeId)?.file_name || 'Saved_CV.pdf');

      const displayJdName = jdSource === 'upload' && jdFile
        ? jdFile.name
        : (jdSource === 'text'
          ? 'JD_Pasted_Text.txt'
          : (savedJds.find(j => j.id === selectedJdId)?.title || 'Saved_JD.pdf'));

      // Generate Question Bank
      const token = useAuthStore.getState().token;
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const qbRes = await fetch('/api/question-banks', {
        method: 'POST',
        headers: headers,
        body: JSON.stringify({
          sessionId: assessment.sessionId,
          questionConfig: {
            behavioural: 1,
            technical: 3,
            coding: 1,
            systemDesign: 0
          }
        })
      });

      if (!qbRes.ok) {
        throw new Error('Failed to generate question bank');
      }

      const qbData = await qbRes.json();

      const questionsToSave = (qbData.questionBank || qbData.question_bank || []).map((q: any) => ({
        question: q.question || '',
        answer: '',
        score: 0,
        strengths: '',
        improvements: '',
        suggestedAnswer: '',
        topicTag: q.topic || '',
        isDeepDive: false,
        goodAnswerSignals: q.good_answer_signals || q.goodAnswerSignals || []
      }));

      // Persist the assessment result and generated questions (including follow-ups) to the existing session draft
      await historyService.saveSession({
        id: assessment.sessionId,
        date: new Date().toISOString(),
        interviewType: 'Technical',
        roleTitle: assessment.roleTypeDetected ? getDisplayRoleTitle(assessment.roleTypeDetected) : roleTitle,
        cvFilename: displayCvName,
        jdFilename: displayJdName,
        resumeId: selectedResumeId || undefined,
        jdId: selectedJdId || undefined,
        status: 'In progress',
        questions: questionsToSave,
        replaceQuestions: true,
        competencyFitScore: assessment.competencyFitScore,
        technicalDepthScore: assessment.technicalDepthScore,
        matchLevel: assessment.matchLevel,
        candidateLevel: assessment.candidateLevel,
        roleTypeDetected: assessment.roleTypeDetected,
        yearsOfExperienceEstimate: assessment.yearsOfExperienceEstimate,
        strongAreas: assessment.strongAreas,
        gapAreas: assessment.gapAreas,
        criticalMissingSkills: assessment.criticalMissingSkills,
        sectionWiseFeedback: assessment.sectionWiseFeedback,
        actionableSuggestions: assessment.actionableImprovementSuggestions || [],
        evidenceItems: assessment.evidenceItems,
        additionalEvidenceItems: assessment.additionalEvidenceItems,
        scoreBreakdown: assessment.scoreBreakdown,
        topPriorityImprovements: assessment.topPriorityImprovements,
        eligibility: assessment.eligibility
      });

      // Navigate directly to the interview session room
      router.push(`/interview/session/${assessment.sessionId}`);
    } catch (err) {
      console.error('Error creating interview session:', err);
      setApiError('Đã xảy ra lỗi khi tạo ngân hàng câu hỏi. Vui lòng thử lại sau.');
      setGenerating(false);
    }
  };

  const handleRestart = async (id: string) => {
    try {
      setIsCloning(id);
      const newSessionId = await historyService.cloneSession(id);
      router.push(`/interview/session/${newSessionId}`);
    } catch (err) {
      console.error('Lỗi khi thực hiện lại phiên:', err);
      alert('Không thể thực hiện lại phiên này. Vui lòng thử lại sau.');
      setIsCloning(null);
    }
  };

  const handleReset = () => {
    if (assessment) {
      setAssessment(null);
    }
    setCvFile(null);
    setJdFile(null);
    setJdText('');
    setSelectedResumeId(null);
    setSelectedJdId(null);
    setUploadProgress(0);
    setApiError(null);
    setIngested(false);
    setSessionId(null);

    // Also remove the search parameter from the URL
    if (typeof window !== 'undefined') {
      const url = new URL(window.location.href);
      url.searchParams.delete('sessionId');
      window.history.pushState({}, '', url.toString());
    }
  };

  // SVG Circular progress values
  const radius = 50;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = assessment
    ? circumference - (assessment.competencyFitScore / 100) * circumference
    : circumference;
  const depthStrokeDashoffset = assessment
    ? circumference - (assessment.technicalDepthScore / 100) * circumference
    : circumference;

  const renderFeedbackValue = (val: any) => {
    if (val && typeof val === 'object') {
      return val.analysis || JSON.stringify(val);
    }
    return String(val || '');
  };

  const getSectionName = (key: string) => {
    const SECTION_NAMES: Record<string, string> = {
      cs_fundamentals: "Kiến thức Khoa học Máy tính cốt lõi (CS Fundamentals)",
      tech_stack_alignment: "Mức độ tương thích Tech Stack",
      project_technical_depth: "Chiều sâu kỹ thuật trong các dự án",
      engineering_practices: "Quy trình và Thực hành Kỹ nghệ",
      experience_evaluation: "Đánh giá kinh nghiệm làm việc",
      education_and_certifications: "Đánh giá học vấn & chứng chỉ"
    };
    return SECTION_NAMES[key] || key.replace(/_/g, ' ').toUpperCase();
  };

  const getPriorityStyles = (rank: number) => {
    switch (rank) {
      case 1:
        return {
          bubbleBg: '#ffe4e6', // light rose
          bubbleBorder: '#fda4af', // rose-300
          bubbleText: '#e11d48', // rose-600
          badgeBg: '#fecdd3', // rose-200
          badgeText: '#9f1239', // rose-800
          cardBg: '#fffdfd',
          cardBorder: '#ffe4e6'
        };
      case 2:
        return {
          bubbleBg: '#ffedd5', // light orange
          bubbleBorder: '#fdba74', // orange-300
          bubbleText: '#ea580c', // orange-600
          badgeBg: '#fed7aa', // orange-200
          badgeText: '#9a3412', // orange-800
          cardBg: '#fffbf7',
          cardBorder: '#ffedd5'
        };
      case 3:
        return {
          bubbleBg: '#fef9c3', // light yellow
          bubbleBorder: '#fde047', // yellow-300
          bubbleText: '#ca8a04', // yellow-600
          badgeBg: '#fef08a', // yellow-200
          badgeText: '#854d0e', // yellow-800
          cardBg: '#fffdf2',
          cardBorder: '#fef9c3'
        };
      default:
        return {
          bubbleBg: '#f0fdf4', // light green
          bubbleBorder: '#bbf7d0', // green-300
          bubbleText: '#16a34a', // green-600
          badgeBg: '#dcfce7', // green-200
          badgeText: '#166534', // green-800
          cardBg: '#fafdfb',
          cardBorder: '#f0fdf4'
        };
    }
  };

  const renderFormattedFeedback = (text: string) => {
    if (!text) return null;

    if (text.includes('|')) {
      const parts = text.split('|').map(p => p.trim()).filter(Boolean);
      return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginTop: '0.25rem' }}>
          {parts.map((part, index) => {
            let displayPart = part;
            let prefix = "";

            // Check for prefix "Các kỹ năng còn yếu hoặc thiếu chiều sâu: " or similar
            const prefixMatch = part.match(/^(Các kỹ năng còn yếu hoặc thiếu chiều sâu:\s*)/i);
            if (prefixMatch) {
              prefix = prefixMatch[1];
              displayPart = part.substring(prefix.length).trim();
            }

            // Bold headers "Yêu cầu JD:", "Minh chứng CV:"
            const highlightText = (txt: string) => {
              const tokens = txt.split(/(Yêu cầu JD:|Minh chứng CV:)/g);
              return tokens.map((token, tIdx) => {
                if (token === 'Yêu cầu JD:' || token === 'Minh chứng CV:') {
                  return <strong key={tIdx} style={{ color: '#0f172a', fontWeight: 700 }}>{token}</strong>;
                }
                return token;
              });
            };

            return (
              <div key={index} style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                {prefix && (
                  <div style={{ fontWeight: 700, color: '#e11d48', fontSize: '0.85rem', marginBottom: '0.1rem' }}>
                    {prefix}
                  </div>
                )}
                <div style={{
                  fontSize: '0.88rem',
                  color: '#334155',
                  lineHeight: '1.5',
                  paddingLeft: prefix ? '0.5rem' : '0'
                }}>
                  {highlightText(displayPart)}
                </div>
                {index < parts.length - 1 && (
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#cbd5e1',
                    fontSize: '0.75rem',
                    fontWeight: 'bold',
                    marginTop: '0.5rem',
                    marginBottom: '0.25rem',
                    borderBottom: '1px dashed #e2e8f0',
                    paddingBottom: '0.5rem'
                  }}>
                    <span style={{ margin: '0 0.5rem', color: '#94a3b8' }}>|</span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      );
    }

    return (
      <p style={{ margin: 0, fontSize: '0.88rem', color: '#334155', lineHeight: '1.5', whiteSpace: 'pre-line' }}>
        {text}
      </p>
    );
  };

  return (
    <ProtectedRoute>
      <div className={styles.container}>

        {/* Main Content */}
        <main className={styles.content}>
          <div className={styles.titleSection}>
            <h1>Khởi tạo phỏng vấn</h1>
            <p className={styles.subtitle}>Tải lên CV và Mô tả công việc (JD) để AI phân tích mức độ tương thích</p>
          </div>

          {/* Active Sessions — rendered only when not in a result/loading state */}
          {!assessment && !uploading && !analyzing && (
            <ActiveSessionsList
              sessions={activeSessions}
              cloningId={isCloning}
              onResume={handleResumeSession}
              onRestart={handleRestart}
              onViewAssessment={handleViewAssessment}
            />
          )}

          {apiError && (
            <div className={styles.errorBanner}>
              <span>⚠️ {apiError}</span>
              <button onClick={handleReset}>Thử lại</button>
            </div>
          )}

          {/* ── State 1: Ready to Upload ── */}
          {!uploading && !analyzing && !assessment && !ingested && (
            <div className={styles.formSection}>
              <div className={styles.uploadGrid}>
                {/* CV Upload */}
                <div className={styles.uploadCol}>
                  <label className={styles.uploadLabel}>Hồ sơ cá nhân (CV)</label>
                  <div className={styles.tabButtons} style={{ marginBottom: '1rem' }}>
                    <button
                      type="button"
                      className={`${styles.tabButton} ${cvSource === 'upload' ? styles.tabButtonActive : ''}`}
                      onClick={() => setCvSource('upload')}
                    >
                      Tải CV mới
                    </button>
                    <button
                      type="button"
                      className={`${styles.tabButton} ${cvSource === 'saved' ? styles.tabButtonActive : ''}`}
                      onClick={() => setCvSource('saved')}
                    >
                      Chọn CV đã lưu
                    </button>
                    {user?.defaultResumeId && (
                      <button
                        type="button"
                        className={`${styles.tabButton} ${cvSource === 'default' ? styles.tabButtonActive : ''}`}
                        onClick={() => {
                          setCvSource('default');
                          const defId = user.defaultResumeId;
                          setSelectedResumeId(defId ? parseInt(defId, 10) : null);
                        }}
                      >
                        Sử dụng CV mặc định
                      </button>
                    )}
                  </div>

                  {cvSource === 'default' ? (
                    (() => {
                      const defResume = savedResumes.find(r => String(r.id) === String(user?.defaultResumeId));
                      return (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', width: '100%' }}>
                          <div className={styles.fileCard} style={{ border: '1px solid #ffedd5', backgroundColor: '#fff7ed' }}>
                            <div className={styles.fileInfo}>
                              <FileText size={24} style={{ color: '#ea580c' }} />
                              <div>
                                <p className={styles.fileName}>{defResume?.file_name || 'Đang tải thông tin CV mặc định...'}</p>
                                <p className={styles.fileSize} style={{ color: '#ea580c', fontWeight: 600, fontSize: '0.75rem' }}>CV mặc định của bạn</p>
                              </div>
                            </div>
                          </div>
                          {defResume?.file_url && (
                            <button
                              type="button"
                              className={styles.secondaryButton}
                              onClick={() => {
                                setViewerUrl(defResume.file_url);
                                setViewerTitle(`CV mặc định: ${defResume.file_name}`);
                                setViewerOpen(true);
                              }}
                              style={{ width: 'fit-content', padding: '0.4rem 0.85rem', fontSize: '0.78rem', display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}
                            >
                              <Eye size={12} />
                              Xem CV mặc định
                            </button>
                          )}
                        </div>
                      );
                    })()
                  ) : cvSource === 'upload' ? (
                    !cvFile ? (
                      <div
                        className={`${styles.dropzone} ${dragOverCv ? styles.dropzoneActive : ''}`}
                        onDragOver={(e) => handleDragOver(e, 'cv')}
                        onDragLeave={() => handleDragLeave('cv')}
                        onDrop={(e) => handleDrop(e, 'cv')}
                        onClick={() => triggerFileSelect('cv')}
                      >
                        <FolderOpen size={48} className={styles.uploadIcon} />
                        <p className={styles.dropzoneText}>
                          Kéo thả CV hoặc <span className={styles.browseLink}>chọn tệp</span>
                        </p>
                        <p className={styles.dropzoneHint}>Hỗ trợ định dạng PDF. Tối đa 10MB.</p>
                        <input
                          ref={fileInputCvRef}
                          type="file"
                          style={{ display: 'none' }}
                          accept=".pdf"
                          onChange={(e) => handleFileChange(e, 'cv')}
                        />
                      </div>
                    ) : (
                      <div className={styles.fileCard}>
                        <div className={styles.fileInfo}>
                          <FileText size={24} className={styles.fileIcon} />
                          <div>
                            <p className={styles.fileName}>{cvFile.name}</p>
                            <p className={styles.fileSize}>{(cvFile.size / 1024 / 1024).toFixed(2)} MB</p>
                          </div>
                        </div>
                        <button className={styles.removeBtn} onClick={() => setCvFile(null)}><X size={14} /></button>
                      </div>
                    )
                  ) : (
                    <div className="flex flex-col gap-2">
                      <CustomCombobox
                        options={savedResumes.map((r) => ({
                          id: r.id,
                          label: r.file_name,
                          date: new Date(r.created_at).toLocaleDateString('vi-VN'),
                        }))}
                        selectedId={selectedResumeId}
                        onSelect={setSelectedResumeId}
                        placeholder="-- Chọn CV trong danh sách --"
                        searchPlaceholder="Tìm kiếm CV theo tên..."
                        icon={<FileText size={16} style={{ color: '#ea580c', flexShrink: 0 }} />}
                      />
                      {selectedResumeId && (() => {
                        const selResume = savedResumes.find(r => r.id === selectedResumeId);
                        return selResume?.file_url ? (
                          <button
                            type="button"
                            className={styles.secondaryButton}
                            onClick={() => {
                              setViewerUrl(selResume.file_url);
                              setViewerTitle(`CV đã lưu: ${selResume.file_name}`);
                              setViewerOpen(true);
                            }}
                            style={{ width: 'fit-content', padding: '0.4rem 0.85rem', fontSize: '0.78rem', display: 'inline-flex', alignItems: 'center', gap: '0.35rem', marginTop: '0.25rem' }}
                          >
                            <Eye size={12} />
                            Xem CV đã chọn
                          </button>
                        ) : null;
                      })()}
                      {savedResumes.length === 0 && (
                        <p className="text-xs text-slate-400 mt-1">Không có CV nào được lưu trước đó.</p>
                      )}
                    </div>
                  )}
                  {cvError && (
                    <span className={styles.errorText} style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
                      <AlertTriangle size={12} /> {cvError}
                    </span>
                  )}
                </div>

                {/* JD Upload / Text Area */}
                <div className={styles.uploadCol}>
                  <label className={styles.uploadLabel}>Mô tả công việc (JD)</label>
                  <div className={styles.jdTabContainer}>
                    <div className={styles.tabButtons}>
                      <button
                        className={`${styles.tabButton} ${jdSource === 'upload' ? styles.tabButtonActive : ''}`}
                        onClick={() => setJdSource('upload')}
                      >
                        Tải tệp JD
                      </button>
                      <button
                        className={`${styles.tabButton} ${jdSource === 'text' ? styles.tabButtonActive : ''}`}
                        onClick={() => setJdSource('text')}
                      >
                        Dán văn bản
                      </button>
                      <button
                        className={`${styles.tabButton} ${jdSource === 'saved' ? styles.tabButtonActive : ''}`}
                        onClick={() => setJdSource('saved')}
                      >
                        Chọn JD đã lưu
                      </button>
                    </div>

                    {jdSource === 'upload' ? (
                      !jdFile ? (
                        <div
                          className={`${styles.dropzone} ${dragOverJd ? styles.dropzoneActive : ''}`}
                          onDragOver={(e) => handleDragOver(e, 'jd')}
                          onDragLeave={() => handleDragLeave('jd')}
                          onDrop={(e) => handleDrop(e, 'jd')}
                          onClick={() => triggerFileSelect('jd')}
                        >
                          <Briefcase size={48} className={styles.uploadIcon} />
                          <p className={styles.dropzoneText}>
                            Kéo thả JD hoặc <span className={styles.browseLink}>chọn tệp</span>
                          </p>
                          <p className={styles.dropzoneHint}>Hỗ trợ PDF, DOCX, DOC. Tối đa 10MB.</p>
                          <input
                            ref={fileInputJdRef}
                            type="file"
                            style={{ display: 'none' }}
                            accept=".pdf,.docx,.doc"
                            onChange={(e) => handleFileChange(e, 'jd')}
                          />
                        </div>
                      ) : (
                        <div className={styles.fileCard}>
                          <div className={styles.fileInfo}>
                            <FileText size={24} className={styles.fileIcon} />
                            <div>
                              <p className={styles.fileName}>{jdFile.name}</p>
                              <p className={styles.fileSize}>{(jdFile.size / 1024 / 1024).toFixed(2)} MB</p>
                            </div>
                          </div>
                          <button className={styles.removeBtn} onClick={() => setJdFile(null)}><X size={14} /></button>
                        </div>
                      )
                    ) : jdSource === 'text' ? (
                      <textarea
                        className={styles.textAreaJd}
                        value={jdText}
                        onChange={(e) => setJdText(e.target.value)}
                        placeholder="Dán toàn bộ nội dung bản mô tả công việc (JD) vào đây..."
                      />
                    ) : (
                      <div className="flex flex-col gap-2 mt-2">
                        <CustomCombobox
                          options={savedJds.map((j) => ({
                            id: j.id,
                            label: j.title,
                            date: new Date(j.created_at).toLocaleDateString('vi-VN'),
                          }))}
                          selectedId={selectedJdId}
                          onSelect={setSelectedJdId}
                          placeholder="-- Chọn JD trong danh sách --"
                          searchPlaceholder="Tìm kiếm JD theo tên..."
                          icon={<Briefcase size={16} style={{ color: '#3b82f6', flexShrink: 0 }} />}
                        />
                        {selectedJdId && (() => {
                          const selJd = savedJds.find(j => j.id === selectedJdId);
                          return selJd?.file_url ? (
                            <button
                              type="button"
                              className={styles.secondaryButton}
                              onClick={() => {
                                setViewerUrl(selJd.file_url);
                                setViewerTitle(`JD đã chọn: ${selJd.title}`);
                                setViewerOpen(true);
                              }}
                              style={{ width: 'fit-content', padding: '0.4rem 0.85rem', fontSize: '0.78rem', display: 'inline-flex', alignItems: 'center', gap: '0.35rem', marginTop: '0.25rem' }}
                            >
                              <Eye size={12} />
                              Xem JD đã chọn
                            </button>
                          ) : null;
                        })()}
                        {savedJds.length === 0 && (
                          <p className="text-xs text-slate-400 mt-1">Không có JD nào được lưu trước đó.</p>
                        )}
                      </div>
                    )}
                    {jdError && (
                      <span className={styles.errorText} style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
                        <AlertTriangle size={12} /> {jdError}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              <div className={styles.formActions}>
                <Link href="/" className={styles.secondaryButton}>
                  Hủy bỏ
                </Link>
                <button
                  className={styles.primaryButton}
                  disabled={
                    (cvSource === 'upload' && !cvFile) ||
                    ((cvSource === 'saved' || cvSource === 'default') && !selectedResumeId) ||
                    (jdSource === 'upload' && !jdFile) ||
                    (jdSource === 'text' && !jdText.trim()) ||
                    (jdSource === 'saved' && !selectedJdId)
                  }
                  onClick={handleUploadAndIngest}
                >
                  Tải lên CV &amp; JD
                </button>
              </div>
            </div>
          )}

          {/* ── State 2: Uploading ── */}
          {uploading && (
            <div className={styles.loadingOverlay}>
              <div className={styles.spinner} />
              <div>
                <h3>Đang tải tài liệu lên...</h3>
                <p className={styles.subtitle} style={{ marginTop: '0.25rem' }}>Hồ sơ của bạn đang được truyền tải an toàn</p>
              </div>
              <div className={styles.progressContainer}>
                <div className={styles.progressBar} style={{ width: `${uploadProgress}%` }} />
              </div>
            </div>
          )}

          {/* ── State 3: AI Analyzing (Ingesting or Assessing) ── */}
          {analyzing && (
            <div className={styles.loadingOverlay}>
              <div className={styles.spinner} style={{ borderTopColor: '#8b5cf6' }} />
              <div>
                <h3>AI đang xử lý tài liệu của bạn...</h3>
                <p className={styles.subtitle} style={{ marginTop: '0.25rem' }}>Quá trình này có thể mất tới 10-35 giây đối với tài liệu mới</p>
              </div>
              <div className={styles.loadingSteps}>
                {!ingested ? (
                  <>
                    <p>✓ Trích xuất nội dung văn bản từ PDF...</p>
                    <p>➜ Chuẩn hóa định dạng tài liệu...</p>
                  </>
                ) : (
                  <p>➜ Đối chiếu và chấm điểm mức độ tương thích kỹ năng...</p>
                )}
              </div>
            </div>
          )}

          {/* ── State 3.5: Ingested Successfully, Ready for Assessment ── */}
          {ingested && !analyzing && !assessment && (
            <div className={styles.formSection} style={{ textAlign: 'center', padding: '3rem' }}>
              <CheckCircle size={64} style={{ color: '#10b981', margin: '0 auto 1.5rem auto' }} />
              <h2 style={{ fontSize: '1.5rem', fontWeight: 600, color: '#1e293b', marginBottom: '0.5rem' }}>Tải lên thành công!</h2>
              <p style={{ color: '#64748b', marginBottom: '2rem' }}>
                Tài liệu của bạn đã được chuẩn hóa và lưu trữ. Hệ thống đã sẵn sàng để phân tích độ tương thích.
              </p>
              <div className={styles.formActions} style={{ justifyContent: 'center' }}>
                <button className={styles.secondaryButton} onClick={handleReset}>
                  Tải lại tài liệu khác
                </button>
                <button className={styles.primaryButton} onClick={handleRunAssessment}>
                  Tiến hành Đánh giá (Assessment)
                </button>
              </div>
            </div>
          )}

          {/* ── State 4: Display Assessment Result ── */}
          {assessment && (
            <div className={styles.resultSection}>

              {/* Title & Cache Meta */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #e2e8f0', paddingBottom: '1rem', flexWrap: 'wrap', gap: '1rem' }}>
                <div>
                  <h2 style={{ fontSize: '1.5rem', fontWeight: 800, color: '#0f172a', margin: 0 }}>
                    Kết quả phân tích độ tương thích
                  </h2>
                  <p style={{ color: '#64748b', fontSize: '0.9rem', margin: '0.25rem 0 0 0' }}>
                    Dành cho vị trí <strong>{roleTitle}</strong>
                  </p>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.78rem', padding: '0.35rem 0.75rem', borderRadius: '0.5rem', backgroundColor: '#f1f5f9', border: '1px solid #e2e8f0', color: '#475569' }}>
                    <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: assessment.cached ? '#10b981' : '#f59e0b' }}></span>
                    {assessment.cached ? 'Kết quả từ Cache' : 'Phân tích mới'}
                  </div>

                  {assessment.cached && (
                    <button
                      onClick={() => handleRunAssessment(true)}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.3rem',
                        fontSize: '0.78rem',
                        padding: '0.35rem 0.75rem',
                        borderRadius: '0.5rem',
                        backgroundColor: '#ffffff',
                        border: '1px solid #ea580c',
                        color: '#ea580c',
                        cursor: 'pointer',
                        fontWeight: 600,
                        transition: 'all 0.2s',
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.backgroundColor = '#fff7ed';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.backgroundColor = '#ffffff';
                      }}
                    >
                      <RefreshCw size={12} />
                      <span>Đánh giá lại</span>
                    </button>
                  )}
                </div>
              </div>

              {/* Sleek Dual-Mode Toggle Tab Group */}
              {(rawCvText || rawJdText) && (
                <div style={{ display: 'flex', justifyContent: 'center', margin: '2rem 0' }}>
                  <div style={{
                    display: 'inline-flex',
                    padding: '4px',
                    backgroundColor: '#f1f5f9',
                    borderRadius: '12px',
                    border: '1px solid #e2e8f0',
                    boxShadow: 'inset 0 2px 4px rgba(0,0,0,0.02)'
                  }}>
                    <button
                      onClick={() => setActiveView('ai-cards')}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        padding: '10px 24px',
                        borderRadius: '8px',
                        fontSize: '0.85rem',
                        fontWeight: 700,
                        border: 'none',
                        cursor: 'pointer',
                        transition: 'all 0.2s ease',
                        backgroundColor: activeView === 'ai-cards' ? '#ffffff' : 'transparent',
                        color: activeView === 'ai-cards' ? '#4f46e5' : '#64748b',
                        boxShadow: activeView === 'ai-cards' ? '0 1px 3px rgba(0,0,0,0.08)' : 'none'
                      }}
                    >
                      <Brain size={16} />
                      <span>Phân tích AI chuyên sâu</span>
                    </button>
                    <button
                      onClick={() => setActiveView('visual-match')}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        padding: '10px 24px',
                        borderRadius: '8px',
                        fontSize: '0.85rem',
                        fontWeight: 700,
                        border: 'none',
                        cursor: 'pointer',
                        transition: 'all 0.2s ease',
                        backgroundColor: activeView === 'visual-match' ? '#ffffff' : 'transparent',
                        color: activeView === 'visual-match' ? '#4f46e5' : '#64748b',
                        boxShadow: activeView === 'visual-match' ? '0 1px 3px rgba(0,0,0,0.08)' : 'none'
                      }}
                    >
                      <Target size={16} />
                      <span>Đối chiếu từ khóa</span>
                    </button>
                  </div>
                </div>
              )}


              {/* Mode 1: AI Cards */}
              {activeView === 'ai-cards' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                  {/* Dashboard: Circular rings & Badges panel */}

                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1.5rem' }}>

                    {/* Single Merged Ring: Professional Alignment */}
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '1.5rem', backgroundColor: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '0.75rem', textAlign: 'center' }}>
                      <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#4f46e5', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '1rem' }}>Điểm tương thích chuyên môn</span>
                      <div className={styles.scoreRing}>
                        <svg width="110" height="110" viewBox="0 0 120 120">
                          <circle cx="60" cy="60" r={radius} fill="transparent" stroke="#e2e8f0" strokeWidth="8" />
                          <circle
                            cx="60"
                            cy="60"
                            r={radius}
                            fill="transparent"
                            stroke="#4f46e5"
                            strokeWidth="8"
                            strokeDasharray={circumference}
                            strokeDashoffset={strokeDashoffset}
                            strokeLinecap="round"
                            transform="rotate(-90 60 60)"
                          />
                        </svg>
                        <span className={styles.scoreVal}>{assessment.competencyFitScore}%</span>
                      </div>
                      <div style={{
                        marginTop: '1rem',
                        fontSize: '0.75rem',
                        fontWeight: 700,
                        padding: '0.2rem 0.5rem',
                        borderRadius: '0.25rem',
                        display: 'inline-block',
                        backgroundColor: assessment.matchLevel?.toLowerCase().includes('high') || assessment.matchLevel?.toLowerCase().includes('rất tốt') ? '#ecfdf5' : assessment.matchLevel?.toLowerCase().includes('moderate') || assessment.matchLevel?.toLowerCase().includes('khớp') ? '#f0f9ff' : '#fffbeb',
                        color: assessment.matchLevel?.toLowerCase().includes('high') || assessment.matchLevel?.toLowerCase().includes('rất tốt') ? '#047857' : assessment.matchLevel?.toLowerCase().includes('moderate') || assessment.matchLevel?.toLowerCase().includes('khớp') ? '#0369a1' : '#b45309',
                        border: '1px solid currentColor'
                      }}>
                        Mức độ khớp: {assessment.matchLevel || 'N/A'}
                      </div>
                      <p style={{ fontSize: '0.8rem', color: '#64748b', marginTop: '0.75rem', maxWidth: '240px', marginInline: 'auto' }}>Độ tương thích tổng quan của hồ sơ ứng viên với các yêu cầu kỹ năng và kinh nghiệm</p>
                    </div>

                    {/* Classifications Badges Panel (Requirements from JD) */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', padding: '1.5rem', backgroundColor: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '0.75rem', justifyContent: 'center' }}>
                      <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#475569', textTransform: 'uppercase', marginBottom: '0.25rem' }}>Yêu cầu từ Mô tả công việc (JD)</span>

                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #e2e8f0', paddingBottom: '0.5rem' }}>
                        <span style={{ fontSize: '0.82rem', color: '#64748b', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                          <Award size={13} style={{ color: '#8b5cf6' }} /> Vị trí yêu cầu:
                        </span>
                        <span style={{ fontSize: '0.72rem', fontWeight: 700, padding: '0.2rem 0.5rem', borderRadius: '0.25rem', backgroundColor: '#f5f3ff', color: '#6d28d9' }}>
                          {assessment.roleTypeDetected || 'N/A'}
                        </span>
                      </div>

                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #e2e8f0', paddingBottom: '0.5rem' }}>
                        <span style={{ fontSize: '0.82rem', color: '#64748b', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                          <UserCheck size={13} style={{ color: '#0ea5e9' }} /> Cấp bậc yêu cầu:
                        </span>
                        <span style={{ fontSize: '0.72rem', fontWeight: 700, padding: '0.2rem 0.5rem', borderRadius: '0.25rem', backgroundColor: '#f1f5f9', color: '#334155' }}>
                          {assessment.candidateLevel || 'N/A'}
                        </span>
                      </div>

                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontSize: '0.82rem', color: '#64748b', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                          <ShieldCheck size={13} style={{ color: '#10b981' }} /> Kinh nghiệm yêu cầu:
                        </span>
                        <span style={{ fontSize: '0.82rem', fontWeight: 600, color: '#334155' }}>
                          {assessment.yearsOfExperienceEstimate || 'N/A'}
                        </span>
                      </div>

                    </div>

                    {/* Eligibility Card */}
                    {assessment.eligibility && (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', padding: '1.5rem', backgroundColor: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '0.75rem', justifyContent: 'center' }}>
                        <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#475569', textTransform: 'uppercase', marginBottom: '0.25rem' }}>Kết quả sàng lọc hồ sơ</span>

                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', borderBottom: '1px solid #e2e8f0', paddingBottom: '0.75rem', marginBottom: '0.25rem' }}>
                          <span style={{ fontSize: '0.82rem', color: '#64748b' }}>Trạng thái:</span>
                          <span style={{
                            fontSize: '0.75rem',
                            fontWeight: 700,
                            padding: '0.2rem 0.5rem',
                            borderRadius: '0.25rem',
                            backgroundColor: assessment.eligibility.status === 'ELIGIBLE' ? '#ecfdf5' : '#fef2f2',
                            color: assessment.eligibility.status === 'ELIGIBLE' ? '#047857' : '#b91c1c',
                            border: '1px solid currentColor'
                          }}>
                            {assessment.eligibility.status === 'ELIGIBLE' ? 'ĐỦ ĐIỀU KIỆN (ELIGIBLE)' : 'CHƯA ĐỦ ĐIỀU KIỆN'}
                          </span>
                        </div>

                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                          {(assessment.eligibility.gate_checks || []).map((check: any, idx: number) => {
                            const isMet = check.status === 'met' || check.status === 'MET';
                            return (
                              <div key={idx} style={{ display: 'flex', flexDirection: 'column', gap: '0.15rem', padding: '0.4rem 0.65rem', backgroundColor: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '0.35rem' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                  <strong style={{ fontSize: '0.78rem', color: '#0f172a' }}>{check.criteria_name}</strong>
                                  <span style={{ fontSize: '0.68rem', fontWeight: 700, color: isMet ? '#047857' : '#b91c1c', display: 'flex', alignItems: 'center', gap: '0.15rem' }}>
                                    {isMet ? '✓ Đạt' : '✗ Chưa đạt'}
                                  </span>
                                </div>
                                <div style={{ fontSize: '0.7rem', color: '#64748b' }}>
                                  Yêu cầu: <span style={{ color: '#475569', fontWeight: 500 }}>{check.required_value}</span>
                                </div>
                                <div style={{ fontSize: '0.7rem', color: '#64748b' }}>
                                  Thực tế: <span style={{ color: isMet ? '#047857' : '#b91c1c', fontWeight: 600 }}>{check.actual_value}</span>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}

                  </div>

                  {/* Removed tag badges alignment matrix based on user feedback */}

                  {/* Detailed Criteria Alignment Matrix */}
                  <div className={styles.evaluationBox} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', marginTop: '1rem', padding: '1.25rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #e2e8f0', paddingBottom: '0.75rem', flexWrap: 'wrap', gap: '1rem' }}>
                      <h3 style={{ fontSize: '1rem', fontWeight: 800, color: '#0f172a', margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <Award size={18} style={{ color: '#4f46e5' }} />
                        <span>Chi tiết đối chiếu tiêu chí (CV vs JD)</span>
                      </h3>

                      {/* Tabs */}
                      <div style={{ display: 'flex', gap: '0.25rem', padding: '0.2rem', backgroundColor: '#f1f5f9', borderRadius: '0.5rem', border: '1px solid #e2e8f0' }}>
                        {(['all', 'matched', 'weak', 'missing'] as const).map((tab) => {
                          const labelMap = { all: 'Tất cả', matched: 'Khớp', weak: 'Yếu', missing: 'Thiếu' };
                          const count = [
                            ...(assessment.evidenceItems || []),
                            ...(assessment.additionalEvidenceItems || [])
                          ].filter(item => tab === 'all' || item.status === tab).length;

                          const isActive = criteriaFilter === tab;
                          return (
                            <button
                              key={tab}
                              onClick={() => setCriteriaFilter(tab)}
                              style={{
                                border: 'none',
                                padding: '0.3rem 0.65rem',
                                fontSize: '0.75rem',
                                fontWeight: 700,
                                borderRadius: '0.35rem',
                                cursor: 'pointer',
                                backgroundColor: isActive ? '#ffffff' : 'transparent',
                                color: isActive ? '#0f172a' : '#64748b',
                                boxShadow: isActive ? '0 1px 3px rgba(0,0,0,0.08)' : 'none',
                                transition: 'all 0.15s ease'
                              }}
                            >
                              {labelMap[tab]} ({count})
                            </button>
                          );
                        })}
                      </div>
                    </div>

                    {/* Score Breakdown if present */}
                    {assessment.scoreBreakdown && (
                      <div style={{
                        backgroundColor: '#f8fafc',
                        border: '1px solid #e2e8f0',
                        borderRadius: '0.5rem',
                        padding: '1rem',
                        fontSize: '0.82rem',
                        color: '#334155'
                      }}>
                        <div style={{ fontWeight: 700, color: '#0f172a', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                          <TrendingUp size={14} style={{ color: '#10b981' }} />
                          <span>Chi tiết tính điểm (Score Breakdown)</span>
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginTop: '0.25rem' }}>
                          <div>
                            <div>• Tổng điểm tích lũy đạt được: <strong style={{ color: '#4f46e5' }}>{assessment.scoreBreakdown.weighted_points_sum}</strong></div>
                            <div>• Tổng hệ số quan trọng của các yêu cầu: <strong style={{ color: '#0f172a' }}>{assessment.scoreBreakdown.total_weight_used}</strong></div>
                          </div>
                          <div style={{ gridColumn: 'span 2' }}>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1.5rem', alignItems: 'center', marginTop: '0.25rem' }}>
                              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                                <span style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: 500 }}>Công thức tính:</span>
                                <div style={{
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  padding: '0.5rem 1rem',
                                  backgroundColor: '#f8fafc',
                                  border: '1px solid #e2e8f0',
                                  borderRadius: '0.5rem',
                                  fontFamily: 'monospace',
                                  fontSize: '0.75rem',
                                  color: '#334155',
                                  gap: '0.4rem'
                                }}>
                                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1px' }}>
                                    <span style={{ borderBottom: '1px solid #94a3b8', paddingBottom: '1px', paddingLeft: '2px', paddingRight: '2px' }}>
                                      ∑(hệ_số_quan_trọng × điểm_trạng_thái)
                                    </span>
                                    <span style={{ paddingTop: '1px', paddingLeft: '2px', paddingRight: '2px' }}>
                                      ∑(hệ_số_quan_trọng)
                                    </span>
                                  </div>
                                  <span style={{ fontSize: '0.85rem', fontWeight: 'bold' }}>×</span>
                                  <span style={{ fontWeight: 'bold' }}>100</span>
                                </div>
                              </div>

                              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                                <span style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: 500 }}>Chi tiết phép tính:</span>
                                <div style={{
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  padding: '0.5rem 1rem',
                                  backgroundColor: '#fff7ed',
                                  border: '1px solid #ffedd5',
                                  borderRadius: '0.5rem',
                                  fontFamily: 'monospace',
                                  fontSize: '0.75rem',
                                  color: '#ea580c',
                                  gap: '0.4rem'
                                }}>
                                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1px' }}>
                                    <span style={{ borderBottom: '1px solid #fdba74', paddingBottom: '1px', paddingLeft: '2px', paddingRight: '2px' }}>
                                      {assessment.scoreBreakdown.weighted_points_sum}
                                    </span>
                                    <span style={{ paddingTop: '1px', paddingLeft: '2px', paddingRight: '2px' }}>
                                      {assessment.scoreBreakdown.total_weight_used}
                                    </span>
                                  </div>
                                  <span style={{ fontSize: '0.85rem', fontWeight: 'bold' }}>×</span>
                                  <span style={{ fontWeight: 'bold' }}>100</span>
                                  <span style={{ fontWeight: 'bold', marginLeft: '0.15rem' }}>=</span>
                                  <span style={{ fontWeight: 'bold', fontSize: '0.85rem' }}>{assessment.competencyFitScore}%</span>
                                </div>
                              </div>
                            </div>
                          </div>
                        </div>
                        <div style={{ borderTop: '1px solid #e2e8f0', marginTop: '0.75rem', paddingTop: '0.5rem', fontSize: '0.75rem', color: '#64748b', display: 'flex', flexWrap: 'wrap', gap: '1rem' }}>
                          <span>Quy đổi trạng thái:</span>
                          <span>Khớp (Matched) = <strong>{assessment.scoreBreakdown.points_config?.matched || 1.0}</strong></span>
                          <span>Yếu (Weak) = <strong>{assessment.scoreBreakdown.points_config?.weak || 0.3}</strong></span>
                          <span>Thiếu (Missing) = <strong>{assessment.scoreBreakdown.points_config?.missing || 0.0}</strong></span>
                        </div>
                      </div>
                    )}

                    {/* Criteria List */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                      {/* Must Have Section */}
                      <div>
                        <h4 style={{ fontSize: '0.9rem', fontWeight: 700, color: '#0f172a', marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                          <span style={{ width: '4px', height: '14px', backgroundColor: '#e11d48', borderRadius: '2px' }}></span>
                          Yêu cầu bắt buộc (Must Have)
                        </h4>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                          {(() => {
                            const items = (assessment.evidenceItems || []).filter(item => criteriaFilter === 'all' || item.status === criteriaFilter);
                            if (items.length === 0) {
                              return <div style={{ fontSize: '0.8rem', color: '#64748b', fontStyle: 'italic', padding: '1rem', border: '1px dashed #e2e8f0', borderRadius: '0.5rem', backgroundColor: '#f8fafc', textAlign: 'center' }}>Không có yêu cầu bắt buộc nào trong danh mục này</div>;
                            }
                            return items.map((item, idx) => renderCriterionItem(item, idx, CheckCircle, AlertCircle, XCircle));
                          })()}
                        </div>
                      </div>

                      {/* Prefer Section */}
                      <div>
                        <h4 style={{ fontSize: '0.9rem', fontWeight: 700, color: '#0f172a', marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                          <span style={{ width: '4px', height: '14px', backgroundColor: '#0284c7', borderRadius: '2px' }}></span>
                          Yêu cầu khuyến khích (Prefer)
                        </h4>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                          {(() => {
                            const items = (assessment.additionalEvidenceItems || []).filter(item => criteriaFilter === 'all' || item.status === criteriaFilter);
                            if (items.length === 0) {
                              return <div style={{ fontSize: '0.8rem', color: '#64748b', fontStyle: 'italic', padding: '1rem', border: '1px dashed #e2e8f0', borderRadius: '0.5rem', backgroundColor: '#f8fafc', textAlign: 'center' }}>Không có yêu cầu khuyến khích nào trong danh mục này</div>;
                            }
                            return items.map((item, idx) => renderCriterionItem(item, idx + 1000, CheckCircle, AlertCircle, XCircle));
                          })()}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* In-depth AI Evaluation Feedbacks */}
                  {assessment.sectionWiseFeedback && Object.keys(assessment.sectionWiseFeedback).length > 0 && (
                    <div className={styles.evaluationBox} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                      <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#1e293b', display: 'flex', alignItems: 'center', gap: '0.5rem', borderBottom: '1px solid #e2e8f0', paddingBottom: '0.5rem', margin: 0 }}>
                        <Brain size={18} style={{ color: '#4f46e5' }} />
                        <span>Phân tích chi tiết từ AI</span>
                      </h3>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                        {Object.entries(assessment.sectionWiseFeedback).map(([section, feedback], idx) => {
                          const cleanText = renderFeedbackValue(feedback);
                          if (!cleanText) return null;
                          return (
                            <div key={idx} style={{ borderLeft: '3px solid #818cf8', paddingLeft: '1rem' }}>
                              <h4 style={{ fontSize: '0.82rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: '#475569', margin: '0 0 0.25rem 0' }}>
                                {getSectionName(section)}
                              </h4>
                              {renderFormattedFeedback(cleanText)}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* Actionable Suggestions */}
                  <div className={styles.evaluationBox}>
                    <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '1rem', fontWeight: 700, color: '#1e293b', borderBottom: '1px solid #e2e8f0', paddingBottom: '0.5rem', margin: '0 0 1rem 0' }}>
                      <Lightbulb size={18} style={{ color: '#eab308' }} />
                      <span>Lời khuyên chuẩn bị phỏng vấn</span>
                    </h3>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                      {assessment.topPriorityImprovements && assessment.topPriorityImprovements.length > 0 ? (
                        assessment.topPriorityImprovements.map((item: any, index: number) => {
                          const rank = Number(item.priority_rank || index + 1);
                          const pStyles = getPriorityStyles(rank);
                          return (
                            <div
                              key={index}
                              style={{
                                display: 'flex',
                                gap: '1rem',
                                alignItems: 'flex-start',
                                backgroundColor: pStyles.cardBg,
                                border: `1px solid ${pStyles.cardBorder}`,
                                borderRadius: '0.5rem',
                                padding: '1rem',
                                boxShadow: '0 1px 2px rgba(0,0,0,0.02)'
                              }}
                            >
                              {/* Priority Bubble */}
                              <div
                                style={{
                                  backgroundColor: pStyles.bubbleBg,
                                  border: `1.5px solid ${pStyles.bubbleBorder}`,
                                  color: pStyles.bubbleText,
                                  width: '30px',
                                  height: '30px',
                                  borderRadius: '50%',
                                  display: 'flex',
                                  alignItems: 'center',
                                  justifyContent: 'center',
                                  fontWeight: 800,
                                  fontSize: '0.85rem',
                                  flexShrink: 0
                                }}
                              >
                                {rank}
                              </div>

                              {/* Content */}
                              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                                  <span style={{ fontSize: '0.85rem', fontWeight: 800, color: '#1e293b' }}>
                                    {item.criteria_name || 'Đề xuất'}
                                  </span>
                                  <span style={{
                                    fontSize: '0.65rem',
                                    fontWeight: 700,
                                    padding: '0.1rem 0.35rem',
                                    borderRadius: '0.25rem',
                                    backgroundColor: pStyles.badgeBg,
                                    color: pStyles.badgeText
                                  }}>
                                    Ưu tiên {rank}
                                  </span>
                                </div>
                                <p style={{ margin: 0, fontSize: '0.8rem', color: '#475569', lineHeight: '1.5' }}>
                                  {item.suggestion}
                                </p>
                              </div>
                            </div>
                          );
                        })
                      ) : (assessment.actionableImprovementSuggestions || []).length > 0 ? (
                        (assessment.actionableImprovementSuggestions || []).map((suggestion, index) => (
                          <div
                            key={index}
                            style={{
                              display: 'flex',
                              gap: '0.75rem',
                              alignItems: 'flex-start',
                              backgroundColor: '#ffffff',
                              border: '1px solid #e2e8f0',
                              borderRadius: '0.5rem',
                              padding: '0.85rem 1rem',
                              boxShadow: '0 1px 2px rgba(0,0,0,0.02)'
                            }}
                          >
                            <span style={{ color: '#ea580c', fontWeight: 'bold', fontSize: '1rem', lineHeight: '1.2' }}>➔</span>
                            <span style={{ fontSize: '#0.8rem', color: '#475569', lineHeight: '1.5' }}>{suggestion}</span>
                          </div>
                        ))
                      ) : (
                        <p style={{ fontSize: '0.8rem', color: '#64748b', fontStyle: 'italic', margin: 0 }}>Không có đề xuất thêm.</p>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* Mode 2: Jobscan-style Visual Skill Comparison */}
              {activeView === 'visual-match' && (rawCvText || rawJdText) && (() => {
                // Data Adapter: transform evaluation results → keyword arrays
                const derived = extractKeywordsFromEvaluation(
                  assessment?.evidenceItems || [],
                  assessment?.additionalEvidenceItems || []
                );
                const matchingKeywords = derived.matchingSkills;
                const variationKeywords = derived.variationSkills;
                const missingKeywords = derived.missingSkills;

                // Build a keyword-to-reasoning details map for popovers
                const keywordDetails: Record<string, { criteriaName: string; reasoning: string }> = {};
                if (assessment) {
                  const allItems = [...(assessment.evidenceItems || []), ...(assessment.additionalEvidenceItems || [])];
                  for (const item of allItems) {
                    const name = item.criteria_name || '';
                    const reasoning = item.reasoning || item.jd_requirement || '';
                    const tokens = splitCriteriaName(name);
                    for (const token of tokens) {
                      keywordDetails[token.toLowerCase()] = {
                        criteriaName: name,
                        reasoning: reasoning
                      };
                    }
                  }
                }

                // Unified match rate: always use the AI-computed competencyFitScore
                // for consistency with the AI Cards tab — never recalculate from keyword counts.
                const pct = assessment ? assessment.competencyFitScore : 0;
                const ringColor = pct >= 70 ? '#16a34a' : pct >= 40 ? '#d97706' : '#dc2626';
                const ringTextColor = pct >= 70 ? '#15803d' : pct >= 40 ? '#b45309' : '#b91c1c';

                return (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem', marginTop: '1rem' }}>

                    {/* Header Card */}
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      flexWrap: 'wrap',
                      gap: '1.5rem',
                      padding: '1.5rem 1.75rem',
                      backgroundColor: '#ffffff',
                      border: '1px solid #e2e8f0',
                      borderRadius: '0.75rem',
                      boxShadow: '0 2px 8px rgba(15,23,42,0.04)'
                    }}>
                      <div style={{ flex: 1, minWidth: '280px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.5rem' }}>
                          <Target size={18} style={{ color: '#4f46e5' }} />
                          <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 800, color: '#0f172a' }}>
                            So sánh kỹ năng chuyên môn (Hard Skills)
                          </h3>
                          <span style={{
                            fontSize: '0.62rem', fontWeight: 800, padding: '0.2rem 0.55rem',
                            borderRadius: '4px', background: '#fef9c3', color: '#854d0e',
                            border: '1px solid #fde047', textTransform: 'uppercase', letterSpacing: '0.05em'
                          }}>HIGH SCORE IMPACT</span>
                        </div>
                        <p style={{ margin: 0, fontSize: '0.82rem', color: '#64748b', lineHeight: 1.55 }}>
                          Hệ thống tự động trích xuất các từ khóa kỹ năng từ JD và đối chiếu trực tiếp với CV của bạn. Hãy điều chỉnh CV để tăng điểm số tương thích.
                        </p>
                      </div>

                      {/* Circular Match Rate */}
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.35rem', flexShrink: 0 }}>
                        <div style={{
                          width: 68, height: 68, borderRadius: '50%', position: 'relative',
                          background: `conic-gradient(${ringColor} ${pct * 3.6}deg, #e2e8f0 0deg)`,
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                        }}>
                          <div style={{
                            width: 52, height: 52, borderRadius: '50%',
                            background: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center'
                          }}>
                            <span style={{ fontSize: '0.95rem', fontWeight: 800, color: ringTextColor }}>{pct}%</span>
                          </div>
                        </div>
                        <span style={{ fontSize: '0.65rem', color: '#64748b', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em' }}>Tỷ lệ khớp</span>
                      </div>
                    </div>

                    {/* Skill Tag Bank (Pill Tags Container) */}
                    <div style={{
                      padding: '1.5rem 1.75rem',
                      border: '1px solid #e2e8f0',
                      borderRadius: '0.75rem',
                      background: '#fafafa',
                      boxShadow: '0 2px 8px rgba(15,23,42,0.02)'
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
                        <Wrench size={16} style={{ color: '#475569' }} />
                        <h4 style={{ margin: 0, fontSize: '0.8rem', fontWeight: 800, color: '#475569', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                          Ngân hàng từ khóa kỹ năng (Skill Tag Bank)
                        </h4>
                      </div>

                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                        {matchingKeywords.map((keyword: string, idx: number) => (
                          <span
                            key={`match-${idx}`}
                            title="Kỹ năng phù hợp"
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              padding: '0.35rem 0.85rem',
                              backgroundColor: '#dcfce7',
                              color: '#15803d',
                              border: '1px solid #86efac',
                              borderRadius: '9999px',
                              fontSize: '0.78rem',
                              fontWeight: 600,
                              cursor: 'help'
                            }}
                          >
                            ✓ {keyword}
                          </span>
                        ))}
                        {variationKeywords.map((keyword: string, idx: number) => (
                          <span
                            key={`var-${idx}`}
                            title="Biến thể kỹ năng / Chưa rõ ràng"
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              padding: '0.35rem 0.85rem',
                              backgroundColor: '#fef3c7',
                              color: '#d97706',
                              border: '1px solid #fcd34d',
                              borderRadius: '9999px',
                              fontSize: '0.78rem',
                              fontWeight: 600,
                              cursor: 'help'
                            }}
                          >
                            ~ {keyword}
                          </span>
                        ))}
                        {missingKeywords.map((keyword: string, idx: number) => (
                          <span
                            key={`miss-${idx}`}
                            title="Không tìm thấy trong CV"
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              padding: '0.35rem 0.85rem',
                              backgroundColor: '#fee2e2',
                              color: '#b91c1c',
                              border: '1px solid #fca5a5',
                              borderRadius: '9999px',
                              fontSize: '0.78rem',
                              fontWeight: 600,
                              cursor: 'help'
                            }}
                          >
                            ✗ {keyword}
                          </span>
                        ))}
                        {matchingKeywords.length === 0 && variationKeywords.length === 0 && missingKeywords.length === 0 && (
                          <span style={{ fontSize: '0.82rem', color: '#94a3b8', fontStyle: 'italic' }}>Chưa trích xuất được kỹ năng.</span>
                        )}
                      </div>
                    </div>

                    {/* Two-column Highlighted Text panel */}
                    <div style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
                      gap: '1.5rem'
                    }}>

                      {/* LEFT: Resume */}
                      <div style={{
                        position: 'relative',
                        border: '1px solid #e2e8f0',
                        borderRadius: '0.75rem',
                        overflow: 'hidden',
                        backgroundColor: '#ffffff',
                        display: 'flex',
                        flexDirection: 'column',
                        height: '600px',
                        boxShadow: '0 2px 8px rgba(15,23,42,0.03)'
                      }}>
                        <div style={{
                          position: 'sticky', top: 0,
                          backgroundColor: '#f8fafc',
                          borderBottom: '1px solid #e2e8f0',
                          padding: '0.85rem 1.25rem',
                          zIndex: 10,
                          display: 'flex', alignItems: 'center', justifyContent: 'space-between'
                        }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <UserCheck size={16} style={{ color: '#4f46e5' }} />
                            <span style={{ fontWeight: 800, fontSize: '0.82rem', color: '#334155', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Resume:</span>
                          </div>
                          <span style={{ fontSize: '0.72rem', color: '#64748b', maxWidth: '220px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                            title={cvFile ? cvFile.name : cvDisplayName}>
                            {cvFile ? cvFile.name : cvDisplayName}
                          </span>
                        </div>

                        <div style={{ flex: 1, overflowY: 'auto', padding: '1.25rem 1.5rem', lineHeight: 1.75, fontSize: '0.85rem', color: '#334155' }}>
                          {rawCvText ? (
                            <HighlightedText
                              text={rawCvText}
                              matches={matchingKeywords}
                              variations={variationKeywords}
                              missing={[]}
                              keywordDetails={keywordDetails}
                            />
                          ) : (
                            <p style={{ color: '#94a3b8', fontStyle: 'italic', fontSize: '0.82rem', margin: 0 }}>
                              Nội dung CV chưa được lưu. Hãy tạo phiên mới để xem phân tích.
                            </p>
                          )}
                        </div>
                      </div>

                      {/* RIGHT: Job Description */}
                      <div style={{
                        position: 'relative',
                        border: '1px solid #e2e8f0',
                        borderRadius: '0.75rem',
                        overflow: 'hidden',
                        backgroundColor: '#ffffff',
                        display: 'flex',
                        flexDirection: 'column',
                        height: '600px',
                        boxShadow: '0 2px 8px rgba(15,23,42,0.03)'
                      }}>
                        <div style={{
                          position: 'sticky', top: 0,
                          backgroundColor: '#f8fafc',
                          borderBottom: '1px solid #e2e8f0',
                          padding: '0.85rem 1.25rem',
                          zIndex: 10,
                          display: 'flex', alignItems: 'center', justifyContent: 'space-between'
                        }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <Briefcase size={16} style={{ color: '#0891b2' }} />
                            <span style={{ fontWeight: 800, fontSize: '0.82rem', color: '#334155', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Job Description:</span>
                          </div>
                          <span style={{ fontSize: '0.72rem', color: '#64748b', maxWidth: '220px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                            title={jdFile ? jdFile.name : jdDisplayName}>
                            {jdFile ? jdFile.name : jdDisplayName}
                          </span>
                        </div>

                        <div style={{ flex: 1, overflowY: 'auto', padding: '1.25rem 1.5rem', lineHeight: 1.75, fontSize: '0.85rem', color: '#334155' }}>
                          {rawJdText ? (
                            <HighlightedText
                              text={rawJdText}
                              matches={matchingKeywords}
                              variations={variationKeywords}
                              missing={missingKeywords}
                              keywordDetails={keywordDetails}
                            />
                          ) : (
                            <p style={{ color: '#94a3b8', fontStyle: 'italic', fontSize: '0.82rem', margin: 0 }}>
                              Nội dung JD chưa được lưu. Hãy tạo phiên mới để xem phân tích.
                            </p>
                          )}
                        </div>
                      </div>

                    </div>

                    {/* Bottom Legend */}
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-around',
                      gap: '1.5rem',
                      flexWrap: 'wrap',
                      padding: '1rem 1.5rem',
                      border: '1px solid #e2e8f0',
                      borderRadius: '0.75rem',
                      background: '#f8fafc',
                      boxShadow: '0 2px 8px rgba(15,23,42,0.02)'
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', fontSize: '0.8rem', color: '#334155' }}>
                        <span style={{
                          padding: '0.25rem 0.75rem',
                          borderRadius: '6px',
                          background: '#dcfce7',
                          color: '#15803d',
                          fontWeight: 700,
                          fontSize: '0.72rem',
                          border: '1px solid #86efac',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '0.25rem'
                        }}>
                          <CheckCircle size={12} /> Matching Skill
                        </span>
                        <span>Có trong cả CV và JD</span>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', fontSize: '0.8rem', color: '#334155' }}>
                        <span style={{
                          padding: '0.25rem 0.75rem',
                          borderRadius: '6px',
                          background: '#fef3c7',
                          color: '#d97706',
                          fontWeight: 700,
                          fontSize: '0.72rem',
                          border: '1px solid #fcd34d',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '0.25rem'
                        }}>
                          <AlertCircle size={12} /> Skill Variation
                        </span>
                        <span>Khớp ở dạng biến thể / chưa rõ ràng</span>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', fontSize: '0.8rem', color: '#334155' }}>
                        <span style={{
                          padding: '0.25rem 0.75rem',
                          borderRadius: '6px',
                          background: '#fee2e2',
                          color: '#b91c1c',
                          fontWeight: 700,
                          fontSize: '0.72rem',
                          border: '1px solid #fca5a5',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '0.25rem'
                        }}>
                          <XCircle size={12} /> Missing Skill
                        </span>
                        <span>Yêu cầu có trong JD nhưng thiếu trong CV</span>
                      </div>
                    </div>
                  </div>
                );
              })()}

              {/* Navigation buttons */}
              <div className={styles.formActions} style={{ borderTop: '1px solid #e2e8f0', paddingTop: '1.5rem', margin: 0 }}>
                <button className={styles.secondaryButton} onClick={handleReset}>
                  Quay lại
                </button>
                <button className={styles.primaryButton} onClick={handleContinueToSelection}>
                  Tiếp tục phỏng vấn ➔
                </button>
              </div>

            </div>
          )}
          {/* ── State 5: Generating Question Bank ── */}
          {generating && (
            <div className={styles.loadingOverlay}>
              <div className={styles.spinner} style={{ borderTopColor: '#f59e0b' }} />
              <div>
                <h3>Đang tạo bộ câu hỏi phỏng vấn...</h3>
                <p className={styles.subtitle} style={{ marginTop: '0.25rem' }}>AI đang thiết kế câu hỏi dựa trên CV và JD của bạn</p>
              </div>
              <div className={styles.loadingSteps}>
                <p>➜ Phân tích kỹ năng cốt lõi...</p>
                <p>➜ Lên danh sách câu hỏi phù hợp...</p>
              </div>
            </div>
          )}
        </main>

      </div>
      <PdfViewerModal
        isOpen={viewerOpen}
        onClose={() => setViewerOpen(false)}
        pdfUrl={viewerUrl}
        title={viewerTitle}
      />
    </ProtectedRoute>
  );
}

function renderCriterionItem(item: any, idx: number, CheckCircle: any, AlertCircle: any, XCircle: any) {
  const statusConfig = {
    matched: { bg: '#ecfdf5', color: '#047857', border: '#a7f3d0', label: 'Khớp (Matched)', icon: CheckCircle },
    weak: { bg: '#fffbeb', color: '#b45309', border: '#fde68a', label: 'Chưa rõ ràng (Weak)', icon: AlertCircle },
    missing: { bg: '#fef2f2', color: '#b91c1c', border: '#fca5a5', label: 'Thiếu hụt (Missing)', icon: XCircle }
  }[item.status as 'matched' | 'weak' | 'missing'] || { bg: '#f1f5f9', color: '#475569', border: '#cbd5e1', label: item.status, icon: AlertCircle };

  const StatusIcon = statusConfig.icon;

  return (
    <div
      key={idx}
      style={{
        border: `1px solid ${statusConfig.border}`,
        borderRadius: '0.5rem',
        backgroundColor: '#ffffff',
        overflow: 'hidden',
        boxShadow: '0 1px 2px rgba(0,0,0,0.01)'
      }}
    >
      {/* Criterion Header */}
      <div style={{
        backgroundColor: statusConfig.bg,
        padding: '0.6rem 0.85rem',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: '0.5rem',
        borderBottom: `1px solid ${statusConfig.border}`
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <StatusIcon size={15} style={{ color: statusConfig.color }} />
          <strong style={{ fontSize: '0.85rem', color: '#0f172a' }}>{item.criteria_name}</strong>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          {item.weight_used !== undefined && (
            <span style={{ fontSize: '0.72rem', color: '#475569', backgroundColor: 'rgba(255,255,255,0.6)', padding: '0.15rem 0.4rem', borderRadius: '0.25rem', border: '1px solid rgba(0,0,0,0.05)' }}>
              Hệ số quan trọng: <strong>{item.weight_used}</strong>
              {item.score_contribution !== undefined && <> | Điểm đóng góp vào tổng: <strong>{item.score_contribution}</strong></>}
            </span>
          )}
          <span style={{
            fontSize: '0.68rem',
            fontWeight: 700,
            padding: '0.15rem 0.45rem',
            borderRadius: '0.25rem',
            backgroundColor: '#ffffff',
            color: statusConfig.color,
            border: `1px solid ${statusConfig.color}`
          }}>
            {statusConfig.label}
          </span>
        </div>
      </div>

      {/* Criterion Details */}
      <div style={{ padding: '0.85rem', display: 'flex', flexDirection: 'column', gap: '0.6rem', fontSize: '0.8rem' }}>
        {item.jd_requirement && (
          <div>
            <div style={{ fontWeight: 700, color: '#475569', marginBottom: '0.15rem' }}>Yêu cầu tuyển dụng (JD):</div>
            <div style={{ color: '#0f172a', backgroundColor: '#f8fafc', padding: '0.4rem 0.65rem', borderRadius: '0.25rem', border: '1px solid #f1f5f9' }}>
              {item.jd_requirement}
            </div>
          </div>
        )}
        {item.cv_evidence && (
          <div>
            <div style={{ fontWeight: 700, color: '#475569', marginBottom: '0.15rem' }}>Minh chứng trong CV:</div>
            <div style={{ color: '#0f172a', backgroundColor: '#f8fafc', padding: '0.4rem 0.65rem', borderRadius: '0.25rem', border: '1px solid #f1f5f9' }}>
              {item.cv_evidence}
            </div>
          </div>
        )}
        {item.reasoning && (
          <div>
            <div style={{ fontWeight: 700, color: '#475569', marginBottom: '0.15rem' }}>Phân tích &amp; Đánh giá của AI:</div>
            <div style={{ color: '#334155', fontStyle: 'italic', paddingLeft: '0.65rem', borderLeft: `3px solid ${statusConfig.color}` }}>
              {item.reasoning}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
