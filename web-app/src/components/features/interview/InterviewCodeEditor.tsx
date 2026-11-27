'use client';

import { useMemo, useState } from 'react';
import CodeMirror from '@uiw/react-codemirror';
import { python } from '@codemirror/lang-python';
import { javascript } from '@codemirror/lang-javascript';
import { sql } from '@codemirror/lang-sql';
import { oneDark } from '@codemirror/theme-one-dark';
import { useTheme } from 'next-themes';
import { CheckCircle2, LoaderCircle, Play, RotateCcw, Terminal, XCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  type CodingLanguage,
  type PublicCodingSpec,
  type RunCodeResult,
  evidenceInterview,
  interviewError,
} from '@/services/evidenceInterview';

const languageOptions: { value: CodingLanguage; label: string }[] = [
  { value: 'python', label: 'Python' },
  { value: 'javascript', label: 'JavaScript' },
  { value: 'sql', label: 'SQL (SQLite)' },
];

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
}: InterviewCodeEditorProps) {
  const { resolvedTheme } = useTheme();
  const [language, setLanguage] = useState<CodingLanguage>(() => inferLanguage(codingSpec, questionHint));
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState<RunCodeResult | null>(null);
  const [runError, setRunError] = useState('');

  const extensions = useMemo(() => {
    if (language === 'javascript') return [javascript({ jsx: true, typescript: true })];
    if (language === 'sql') return [sql()];
    return [python()];
  }, [language]);

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

  return (
    <div data-code-editor="codemirror" className="flex min-h-0 flex-1 flex-col gap-2.5">
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border bg-muted/30 px-3 py-1.5 text-xs">
        <div className="flex items-center gap-2">
          <Terminal size={14} className="text-muted-foreground" aria-hidden="true" />
          <select
            aria-label="Ngôn ngữ lập trình"
            className="rounded border bg-background px-2 py-1 text-xs font-medium outline-none focus-visible:ring-2 focus-visible:ring-ring"
            value={language}
            disabled={disabled || readOnly || Boolean(codingSpec?.language)}
            onChange={e => setLanguage(e.target.value as CodingLanguage)}
          >
            {languageOptions.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
          {codingSpec?.sample_tests?.length ? (
            <span className="text-muted-foreground">
              {codingSpec.sample_tests.length} ca thử mẫu
            </span>
          ) : null}
        </div>
        <div className="flex items-center gap-1.5">
          {codingSpec?.starter_code && !readOnly && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-7 px-2 text-xs"
              disabled={disabled || running}
              onClick={() => onChange(codingSpec.starter_code)}
            >
              <RotateCcw size={13} aria-hidden="true" /> Mã mẫu
            </Button>
          )}
          {!readOnly && (
            <Button
              type="button"
              variant="secondary"
              size="sm"
              className="h-7 px-2.5 text-xs font-semibold"
              disabled={disabled || running || !value.trim()}
              onClick={() => void handleRun()}
            >
              {running ? <LoaderCircle size={13} className="animate-spin" aria-hidden="true" /> : <Play size={13} aria-hidden="true" />}
              {running ? 'Đang chạy…' : 'Chạy thử'}
            </Button>
          )}
        </div>
      </div>

      <div className={`overflow-hidden rounded-xl border bg-background ${compact ? 'min-h-36' : 'min-h-52 flex-1'}`}>
        <CodeMirror
          value={value}
          height={compact ? '160px' : '240px'}
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

      {runError && (
        <p role="alert" className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive">
          {runError}
        </p>
      )}

      {runResult && (
        <div role="status" className="space-y-2 rounded-xl border bg-muted/25 p-3 text-xs">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="font-semibold text-foreground">
              Kết quả chạy thử ({runResult.language.toUpperCase()})
            </span>
            {runResult.total > 0 && (
              <span className={`rounded-full px-2 py-0.5 font-semibold ${
                runResult.passed === runResult.total
                  ? 'bg-emerald-100 text-emerald-900 dark:bg-emerald-500/20 dark:text-emerald-200'
                  : 'bg-orange-100 text-orange-900 dark:bg-orange-500/20 dark:text-orange-200'
              }`}>
                Đạt {runResult.passed}/{runResult.total} ca mẫu
              </span>
            )}
          </div>
          {runResult.compile_error && (
            <pre className="max-h-32 overflow-auto rounded-lg bg-destructive/10 p-2 font-mono text-[11px] whitespace-pre-wrap text-destructive">
              {runResult.compile_error}
            </pre>
          )}
          {!runResult.compile_error && runResult.total === 0 && (
            <pre className="max-h-32 overflow-auto rounded-lg bg-slate-900 p-2 font-mono text-[11px] whitespace-pre-wrap text-slate-100">
              {runResult.stdout.trim() || '(Không có đầu ra stdout)'}
            </pre>
          )}
          {runResult.results.length > 0 && (
            <ul className="space-y-1.5">
              {runResult.results.map(item => (
                <li key={item.name} className="rounded-lg border bg-background p-2">
                  <div className="flex items-center justify-between gap-2">
                    <span className="flex items-center gap-1.5 font-medium">
                      {item.passed
                        ? <CheckCircle2 size={13} className="text-emerald-600" aria-hidden="true" />
                        : <XCircle size={13} className="text-destructive" aria-hidden="true" />}
                      {item.name}
                    </span>
                    <span className="tabular-nums text-muted-foreground">{item.elapsed_ms} ms</span>
                  </div>
                  {item.error ? (
                    <p className="mt-1 font-mono text-[11px] text-destructive">{item.error}</p>
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
      )}
    </div>
  );
}
