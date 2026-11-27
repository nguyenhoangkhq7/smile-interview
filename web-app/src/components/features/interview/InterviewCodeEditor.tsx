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

function inferLanguage(spec: PublicCodingSpec | null | undefined, hintText: string): CodingLanguage {
  if (spec?.language) return spec.language;
  const lower = hintText.toLowerCase();
  if (/\b(?:sql|select\b|postgres|mysql|sqlite|index|query|truy vấn)\b/.test(lower)) return 'sql';
  if (/\b(?:javascript|typescript|node\.?js|react|next\.?js|const\s+\w+|function\s+\w+)\b/.test(lower)) return 'javascript';
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
  const [language, setLanguage] = useState<CodingLanguage>(() => inferLanguage(codingSpec, questionHint));
  const [autocompleteOn, setAutocompleteOn] = useState(defaultAutocomplete);
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState<RunCodeResult | null>(null);
  const [runError, setRunError] = useState('');

  const langMeta = languageOptions.find(opt => opt.value === language) ?? languageOptions[0];
  const sampleCount = codingSpec?.sample_tests?.length ?? 0;

  const extensions = useMemo(() => {
    const langExt = language === 'javascript'
      ? javascript({ jsx: true, typescript: true })
      : language === 'sql'
        ? sql()
        : python();
    const list = [langExt, EditorView.lineWrapping, editorChromeTheme];
    if (autocompleteOn && !readOnly && !disabled) {
      list.push(createSandboxAutocomplete(language));
    }
    return list;
  }, [language, autocompleteOn, readOnly, disabled]);

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
      <div className="flex items-center justify-between gap-2 border-b bg-muted/35 px-2.5 py-1.5 text-xs">
        <div className="flex min-w-0 items-center gap-2">
          <div className="relative shrink-0">
            <select
              aria-label="Ngôn ngữ lập trình"
              className="h-7 appearance-none rounded-md border border-border/80 bg-background pr-6 pl-2.5 text-xs font-semibold text-foreground outline-none transition-colors hover:border-foreground/30 focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60"
              value={language}
              disabled={disabled || readOnly || Boolean(codingSpec?.language)}
              onChange={e => setLanguage(e.target.value as CodingLanguage)}
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

          {sampleCount > 0 ? (
            <span className="inline-flex shrink-0 items-center rounded-md bg-emerald-500/10 px-2 py-0.5 text-[11px] font-medium text-emerald-700 dark:text-emerald-300">
              {sampleCount} ca mẫu
            </span>
          ) : (
            <span
              className="inline-flex min-w-0 items-center gap-1 truncate rounded-md bg-muted px-2 py-0.5 text-[11px] font-medium text-muted-foreground"
              title={`Chạy thử tự do · AI chấm ngữ nghĩa. ${langMeta.shortHint}`}
            >
              <span className="truncate">Tự do · Chấm ngữ nghĩa</span>
              <Info size={12} aria-hidden="true" className="hidden shrink-0 opacity-75 sm:inline" />
            </span>
          )}
        </div>

        <div className="flex shrink-0 items-center gap-1.5">
          {!readOnly && (
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
          {!readOnly && (
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

      {/* Main CodeMirror 6 surface */}
      <div className={`min-h-0 flex-1 overflow-auto ${compact ? 'min-h-36 max-h-56' : 'min-h-48'}`}>
        <CodeMirror
          value={value}
          height="100%"
          minHeight={compact ? '144px' : '196px'}
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
        <div role="status" className="border-t bg-muted/25 text-xs">
          <div className="flex items-center justify-between gap-2 border-b border-border/60 px-3 py-1.5">
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

          <div className="max-h-36 space-y-2 overflow-y-auto px-3 py-2.5">
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
              <pre className="max-h-28 overflow-auto rounded-lg bg-destructive/10 p-2 font-mono text-[11px] whitespace-pre-wrap text-destructive">
                {runResult.compile_error}
              </pre>
            )}
            {freeRunSuccess && (
              (runResult?.stdout ?? '').trim() ? (
                <pre className="max-h-28 overflow-auto rounded-lg bg-slate-950 px-3 py-2 font-mono text-[11px] whitespace-pre-wrap text-slate-100">
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
                {(runResult?.results ?? []).map(item => (
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
                    {item.error ? (
                      <p className="mt-1 font-mono text-[11px] break-words text-destructive">{item.error}</p>
                    ) : !item.passed ? (
                      <div className="mt-1 grid gap-1 font-mono text-[11px] text-muted-foreground sm:grid-cols-2">
                        <span>Thực tế: <strong className="text-foreground">{item.actual_output || '(rỗng)'}</strong></span>
                        <span>Kỳ vọng: <strong className="text-foreground">{item.expected_output}</strong></span>
                      </div>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
