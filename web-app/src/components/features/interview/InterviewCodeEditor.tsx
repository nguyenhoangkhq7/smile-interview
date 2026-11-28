'use client';

import { useMemo, useState } from 'react';
import CodeMirror, { EditorView } from '@uiw/react-codemirror';
import { python } from '@codemirror/lang-python';
import { javascript } from '@codemirror/lang-javascript';
import { sql } from '@codemirror/lang-sql';
import { oneDark } from '@codemirror/theme-one-dark';
import { useTheme } from 'next-themes';
import {
  CheckCircle2,
  ChevronDown,
  Info,
  LoaderCircle,
  Play,
  RotateCcw,
  Sparkles,
  Terminal,
  X,
  XCircle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  type CodingLanguage,
  type PublicCodingSpec,
  type RunCodeResult,
  evidenceInterview,
  interviewError,
} from '@/services/evidenceInterview';
import { createSandboxAutocomplete } from './codeCompletions';

const languageOptions: { value: CodingLanguage; label: string; shortHint: string }[] = [
  {
    value: 'python',
    label: 'Python',
    shortHint: 'Python 3.12 · Thư viện chuẩn, Pydantic, FastAPI/HTTPX, Redis & MongoDB giả lập trong RAM',
  },
  {
    value: 'javascript',
    label: 'JavaScript',
    shortHint: 'Node.js · Thư viện chuẩn (crypto, url, util, JSON, Map/Set)',
  },
  {
    value: 'sql',
    label: 'SQL',
    shortHint: 'SQLite trong bộ nhớ · Hỗ trợ SELECT, JOIN, CTE, Window Functions',
  },
];

const editorChromeTheme = EditorView.theme({
  '&': {
    fontSize: '13.5px',
    backgroundColor: 'transparent',
  },
  '.cm-scroller': {
    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace',
    lineHeight: '1.6',
    padding: '8px 0',
  },
  '.cm-content': {
    padding: '0 12px 0 6px',
  },
  '.cm-gutters': {
    backgroundColor: 'transparent',
    borderRight: '1px solid rgba(148, 163, 184, 0.2)',
    color: 'rgba(100, 116, 139, 0.75)',
    minWidth: '38px',
  },
  '.cm-lineNumbers .cm-gutterElement': {
    padding: '0 10px 0 8px',
    fontSize: '12px',
  },
  '.cm-activeLine': {
    backgroundColor: 'rgba(16, 185, 129, 0.05)',
  },
  '.cm-activeLineGutter': {
    backgroundColor: 'transparent',
    color: 'inherit',
    fontWeight: '600',
  },
  '&.cm-focused': {
    outline: 'none',
  },
});

function detectNonSandboxLanguage(spec: PublicCodingSpec | null | undefined, hintText: string): string | null {
  if (spec) return null;
  const lower = hintText.toLowerCase();
  if (/\b(?:java|spring\s*boot|springboot|jvm)\b/.test(lower)) return 'Java / Spring';
  if (/\b(?:golang|go\s+func|func\s+\w+\s*\([^)]*\)\s*(?:\[|error|int|string))\b/.test(lower)) return 'Go';
  if (/\b(?:c#|csharp|\.net|dotnet|asp\.net)\b/.test(lower)) return 'C# / .NET';
  if (/\b(?:c\+\+|cpp|std::)\b/.test(lower)) return 'C++';
  if (/\b(?:react|next\.?js|jsx|tsx)\b/.test(lower)) return 'React / TypeScript';
  if (/\btypescript\b/.test(lower)) return 'TypeScript';
  return null;
}

function inferLanguage(spec: PublicCodingSpec | null | undefined, hintText: string): CodingLanguage {
  if (spec?.language) return spec.language;
  const lower = hintText.toLowerCase();
  if (/\b(?:sql|select\b|postgres|mysql|sqlite|index|query|truy vấn)\b/.test(lower)) return 'sql';
  if (/\b(?:javascript|typescript|node\.?js|react|next\.?js|const\s+\w+|function\s+\w+|java|spring|golang|c#|c\+\+)\b/.test(lower)) return 'javascript';
  return 'python';
}

interface InterviewCodeEditorProps {
  sessionId: string;
  turnId: string;
  value: string;
  onChange: (next: string) => void;
  codingSpec?: PublicCodingSpec | null;
  questionHint?: string;
  disabled?: boolean;
  readOnly?: boolean;
  compact?: boolean;
  defaultAutocomplete?: boolean;
}

export function InterviewCodeEditor({
  sessionId,
  turnId,
  value,
  onChange,
  codingSpec,
  questionHint = '',
  disabled = false,
  readOnly = false,
  compact = false,
  defaultAutocomplete = true,
}: InterviewCodeEditorProps) {
  const { resolvedTheme } = useTheme();
  const nonSandboxLabel = detectNonSandboxLanguage(codingSpec, questionHint);
  const [language, setLanguage] = useState<CodingLanguage>(() => inferLanguage(codingSpec, questionHint));
  const [sandboxOverride, setSandboxOverride] = useState(false);
  const [autocompleteOn, setAutocompleteOn] = useState(defaultAutocomplete);
  const [showSamples, setShowSamples] = useState(false);
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState<RunCodeResult | null>(null);
  const [runError, setRunError] = useState('');

  const langMeta = languageOptions.find(opt => opt.value === language) ?? languageOptions[0];
  const sampleCount = codingSpec?.sample_tests?.length ?? 0;
  const isSemanticOnly = Boolean(nonSandboxLabel) && !sandboxOverride;

  const extensions = useMemo(() => {
    const langExt = language === 'javascript'
      ? javascript({ jsx: isSemanticOnly, typescript: isSemanticOnly })
      : language === 'sql'
        ? sql()
        : python();
    const list = [langExt, EditorView.lineWrapping, editorChromeTheme];
    if (autocompleteOn && !readOnly && !disabled) {
      list.push(createSandboxAutocomplete(language));
    }
    return list;
  }, [language, isSemanticOnly, autocompleteOn, readOnly, disabled]);

  async function handleRun() {
    if (!value.trim() || running || disabled) return;
    setRunning(true);
    setRunError('');
    try {
      const outcome = await evidenceInterview.runCode(sessionId, {
        turn_id: turnId,
        code: value,
        language,
      });
      setRunResult(outcome);
    } catch (cause) {
      setRunError(interviewError(cause));
      setRunResult(null);
    } finally {
      setRunning(false);
    }
  }

  const hasConsole = Boolean(runError || runResult);
  const freeRunSuccess = Boolean(runResult && !runResult.compile_error && runResult.total === 0);

  return (
    <div
      data-code-editor="codemirror"
      className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-border/90 bg-background shadow-2xs transition-shadow focus-within:border-brand-green/60 focus-within:ring-2 focus-within:ring-brand-green/15"
    >
      {/* Single-row IDE toolbar */}
      <div className="flex shrink-0 items-center justify-between gap-2 border-b bg-muted/35 px-2.5 py-1.5 text-xs">
        <div className="flex min-w-0 items-center gap-2">
          {!isSemanticOnly && (
            <div className="relative shrink-0">
              <select
                aria-label="Ngôn ngữ lập trình"
                className="h-7 appearance-none rounded-md border border-border/80 bg-background pr-6 pl-2.5 text-xs font-semibold text-foreground outline-none transition-colors hover:border-foreground/30 focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60"
                value={language}
                disabled={disabled || readOnly || Boolean(codingSpec?.language)}
                onChange={e => { setLanguage(e.target.value as CodingLanguage); setSandboxOverride(true); }}
              >
                {languageOptions.map(opt => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
              <ChevronDown
                size={13}
                aria-hidden="true"
                className="pointer-events-none absolute top-1/2 right-1.5 -translate-y-1/2 text-muted-foreground"
              />
            </div>
          )}

          {sampleCount > 0 ? (
            <button
              type="button"
              aria-expanded={showSamples}
              onClick={() => setShowSamples(prev => !prev)}
              className="inline-flex min-w-0 cursor-pointer items-center gap-1 truncate rounded-md bg-emerald-500/10 px-2 py-0.5 text-[11px] font-medium text-emerald-700 transition-colors hover:bg-emerald-500/15 dark:text-emerald-300"
              title={codingSpec?.entry_point
                ? `Xem ${sampleCount} ca thử mẫu · Hàm kỳ vọng: ${codingSpec.entry_point}()`
                : `Xem ${sampleCount} ca thử mẫu`}
            >
              <span className="shrink-0">
                {codingSpec?.setup_sql?.trim() ? `${sampleCount} ca mẫu · Schema` : `${sampleCount} ca mẫu`}
              </span>
              {codingSpec?.entry_point && (
                <>
                  <span aria-hidden="true">·</span>
                  <code className="truncate font-mono text-[11px]">{codingSpec.entry_point}()</code>
                </>
              )}
              <ChevronDown
                size={12}
                aria-hidden="true"
                className={`shrink-0 transition-transform ${showSamples ? 'rotate-180' : ''}`}
              />
            </button>
          ) : isSemanticOnly ? (
            <span
              className="inline-flex min-w-0 items-center gap-1 truncate rounded-md bg-amber-500/10 px-2 py-0.5 text-[11px] font-semibold text-amber-800 dark:text-amber-200"
              title={`Sandbox chỉ chạy Python/JS/SQL. Với ${nonSandboxLabel}, bạn viết code tự do và bấm Gửi câu trả lời để AI chấm ngữ nghĩa.`}
            >
              <span className="truncate">{nonSandboxLabel} · Chấm ngữ nghĩa</span>
              <Info size={12} aria-hidden="true" className="hidden shrink-0 opacity-75 sm:inline" />
            </span>
          ) : (
            <span
              className="inline-flex min-w-0 items-center gap-1 truncate rounded-md bg-muted px-2 py-0.5 text-[11px] font-medium text-muted-foreground"
              title={`Chạy thử tự do · AI chấm ngữ nghĩa. ${langMeta.shortHint}`}
            >
              <span className="truncate">
                {codingSpec?.entry_point ? `Hàm ${codingSpec.entry_point}()` : 'Tự do · Chấm ngữ nghĩa'}
              </span>
              <Info size={12} aria-hidden="true" className="hidden shrink-0 opacity-75 sm:inline" />
            </span>
          )}
        </div>

        <div className="flex shrink-0 items-center gap-1.5">
          {!readOnly && isSemanticOnly && (
            <button
              type="button"
              disabled={disabled}
              title="Chuyển sang trình chạy thử Python / JavaScript / SQL"
              onClick={() => setSandboxOverride(true)}
              className="inline-flex h-7 cursor-pointer items-center gap-1 rounded-md border border-border/70 px-2 text-[11px] font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:pointer-events-none disabled:opacity-50"
            >
              Dùng sandbox
            </button>
          )}
          {!readOnly && !isSemanticOnly && (
            <button
              type="button"
              aria-pressed={autocompleteOn}
              disabled={disabled}
              title={autocompleteOn ? 'Tắt gợi ý cú pháp & thư viện' : 'Bật gợi ý cú pháp & thư viện'}
              onClick={() => setAutocompleteOn(prev => !prev)}
              className={`inline-flex h-7 cursor-pointer items-center gap-1 rounded-md border px-2 text-[11px] font-medium transition-colors disabled:pointer-events-none disabled:opacity-50 ${
                autocompleteOn
                  ? 'border-brand-green/35 bg-brand-green/10 text-brand-green'
                  : 'border-transparent text-muted-foreground hover:bg-muted hover:text-foreground'
              }`}
            >
              <Sparkles size={12} aria-hidden="true" />
              <span className="hidden sm:inline">Gợi ý</span>
            </button>
          )}
          {codingSpec?.starter_code && !readOnly && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-7 px-2 text-[11px] text-muted-foreground hover:text-foreground"
              disabled={disabled || running}
              title="Khôi phục mã mẫu ban đầu"
              onClick={() => onChange(codingSpec.starter_code)}
            >
              <RotateCcw size={12} aria-hidden="true" />
              <span className="hidden sm:inline">Mã mẫu</span>
            </Button>
          )}
          {!readOnly && !isSemanticOnly && (
            <Button
              type="button"
              size="sm"
              className="h-7 bg-brand-green px-2.5 text-xs font-semibold text-white shadow-2xs hover:bg-brand-green/90"
              disabled={disabled || running || !value.trim()}
              onClick={() => void handleRun()}
            >
              {running
                ? <LoaderCircle size={13} className="animate-spin" aria-hidden="true" />
                : <Play size={12} className="fill-current" aria-hidden="true" />}
              {running ? 'Đang chạy…' : 'Chạy thử'}
            </Button>
          )}
        </div>
      </div>

      {/* Collapsible sample test & SQL schema preview */}
      {showSamples && (sampleCount > 0 || Boolean(codingSpec?.setup_sql?.trim())) && (
        <div className="max-h-36 shrink-0 space-y-1.5 overflow-y-auto border-b bg-muted/20 px-3 py-2 text-[11px]">
          {codingSpec?.setup_sql?.trim() && (
            <div className="rounded-md border border-border/70 bg-background px-2.5 py-1.5">
              <p className="font-semibold text-foreground">Lược đồ bảng mẫu (SQLite)</p>
              <pre className="mt-1 overflow-x-auto font-mono text-[11px] whitespace-pre-wrap text-muted-foreground">
                {codingSpec.setup_sql.trim()}
              </pre>
            </div>
          )}
          {(codingSpec?.sample_tests ?? []).map((sample, idx) => (
            <div key={`${sample.name}-${idx}`} className="rounded-md border border-border/70 bg-background px-2.5 py-1.5">
              <p className="font-semibold text-foreground">{sample.name}</p>
              <div className="mt-1 grid gap-1 font-mono text-muted-foreground sm:grid-cols-2">
                {sample.input_data && (
                  <span className="break-all">Đầu vào: <strong className="text-foreground">{sample.input_data}</strong></span>
                )}
                <span className="break-all">Kỳ vọng: <strong className="text-foreground">{sample.expected_output}</strong></span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Main CodeMirror 6 surface */}
      <div
        className={`flex-1 overflow-auto ${
          hasConsole
            ? (compact ? 'min-h-24 max-h-40' : 'min-h-24')
            : (compact ? 'min-h-36 max-h-56' : 'min-h-44')
        }`}
      >
        <CodeMirror
          value={value}
          height="100%"
          minHeight={hasConsole ? '88px' : (compact ? '144px' : '176px')}
          theme={resolvedTheme === 'dark' ? oneDark : 'light'}
          extensions={extensions}
          editable={!disabled && !readOnly}
          basicSetup={{
            lineNumbers: true,
            highlightActiveLine: true,
            autocompletion: false,
            foldGutter: false,
          }}
          onChange={onChange}
        />
      </div>

      {/* Docked collapsible console drawer */}
      {hasConsole && (
        <div
          role="status"
          className={`flex min-h-0 shrink-0 flex-col border-t bg-muted/25 text-xs ${compact ? '' : 'max-h-[55%]'}`}
        >
          <div className="flex shrink-0 items-center justify-between gap-2 border-b border-border/60 px-3 py-1.5">
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1.5 font-semibold text-foreground">
                <Terminal size={13} className="text-muted-foreground" aria-hidden="true" />
                Kết quả chạy thử
              </span>
              {runResult && (
                <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] font-semibold text-muted-foreground uppercase">
                  {runResult.language}
                </span>
              )}
              {runResult && runResult.total > 0 && (
                <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${
                  runResult.passed === runResult.total
                    ? 'bg-emerald-100 text-emerald-900 dark:bg-emerald-500/20 dark:text-emerald-200'
                    : 'bg-orange-100 text-orange-900 dark:bg-orange-500/20 dark:text-orange-200'
                }`}>
                  Đạt {runResult.passed}/{runResult.total} ca mẫu
                </span>
              )}
              {freeRunSuccess && (
                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-[11px] font-semibold text-emerald-900 dark:bg-emerald-500/20 dark:text-emerald-200">
                  <CheckCircle2 size={11} aria-hidden="true" />
                  Chạy thành công
                </span>
              )}
            </div>
            <button
              type="button"
              aria-label="Đóng kết quả chạy thử"
              onClick={() => { setRunResult(null); setRunError(''); }}
              className="rounded p-0.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              <X size={13} aria-hidden="true" />
            </button>
          </div>

          <div className={`min-h-0 flex-1 space-y-2 overflow-y-auto overscroll-contain px-3 py-2.5 ${compact ? 'max-h-52' : ''}`}>
            {runError && (
              <p role="alert" className="rounded-lg border border-destructive/40 bg-destructive/10 px-2.5 py-2 text-xs text-destructive">
                {runError}
              </p>
            )}
            {runResult?.environment_notice && (
              <p
                role="note"
                className="flex items-start gap-2 rounded-lg border border-amber-300/80 bg-amber-50/90 px-2.5 py-2 text-xs leading-relaxed text-amber-950 dark:border-amber-500/40 dark:bg-amber-950/40 dark:text-amber-200"
              >
                <Info size={14} className="mt-0.5 shrink-0" aria-hidden="true" />
                <span>{runResult.environment_notice}</span>
              </p>
            )}
            {runResult?.compile_error && (
              <pre className="overflow-x-auto rounded-lg bg-destructive/10 p-2 font-mono text-[11px] whitespace-pre-wrap text-destructive">
                {runResult.compile_error}
              </pre>
            )}
            {freeRunSuccess && (
              (runResult?.stdout ?? '').trim() ? (
                <pre className="overflow-x-auto rounded-lg bg-slate-950 px-3 py-2 font-mono text-[11px] whitespace-pre-wrap text-slate-100">
                  {(runResult?.stdout ?? '').trim()}
                </pre>
              ) : (
                <p className="text-[11px] text-muted-foreground">
                  Mã thực thi không có lỗi và không in ra stdout (thêm <code className="rounded bg-muted px-1 py-0.5 font-mono text-foreground">print(...)</code> nếu muốn xem giá trị trả về khi chạy tự do).
                </p>
              )
            )}
            {(runResult?.results ?? []).length > 0 && (
              <ul className="space-y-1.5">
                {(runResult?.results ?? []).map(item => {
                  const sampleInput = codingSpec?.sample_tests?.find(s => s.name === item.name)?.input_data;
                  return (
                    <li key={item.name} className="rounded-lg border bg-background px-2.5 py-2">
                      <div className="flex items-center justify-between gap-2">
                        <span className="flex items-center gap-1.5 font-medium">
                          {item.passed
                            ? <CheckCircle2 size={13} className="text-emerald-600" aria-hidden="true" />
                            : <XCircle size={13} className="text-destructive" aria-hidden="true" />}
                          {item.name}
                        </span>
                        <span className="tabular-nums text-[11px] text-muted-foreground">{item.elapsed_ms} ms</span>
                      </div>
                      {sampleInput && (
                        <p className="mt-1 font-mono text-[11px] break-all text-muted-foreground">
                          Đầu vào: <strong className="text-foreground">{sampleInput}</strong>
                        </p>
                      )}
                      {item.error ? (
                        <p className="mt-1 font-mono text-[11px] break-words text-destructive">{item.error}</p>
                      ) : !item.passed ? (
                        <div className="mt-1 grid gap-1 font-mono text-[11px] text-muted-foreground sm:grid-cols-2">
                          <span>Thực tế: <strong className="text-foreground">{item.actual_output || '(rỗng)'}</strong></span>
                          <span>Kỳ vọng: <strong className="text-foreground">{item.expected_output}</strong></span>
                        </div>
                      ) : null}
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
