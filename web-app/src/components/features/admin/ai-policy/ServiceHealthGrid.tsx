import { BellRing, BrainCircuit, CloudSync, Database, GitFork, Mic, ShieldCheck, SmilePlus, Zap } from 'lucide-react';
import type { AiServiceCheck } from '@/services/adminAiPolicy';

const servicesInfo = {
  postgres: ['PostgreSQL Database', Database],
  fastapi: ['FastAPI AI Service', Zap],
  s3: ['AWS S3 Artifacts', CloudSync],
  push: ['Web Push / VAPID', BellRing],
  embedding: ['Embedding Model', BrainCircuit],
  dspy: ['DSPy / OpenRouter', GitFork],
  voice: ['OpenRouter STT/TTS', Mic],
  simli: ['Simli 3D Avatar', SmilePlus],
} as const;

const statuses = {
  UP: ['Hoạt động', 'bg-green-100 text-green-800'],
  CONFIGURED: ['Đã cấu hình', 'bg-blue-100 text-blue-800'],
  DOWN: ['Lỗi kết nối', 'bg-red-100 text-red-800'],
  DEGRADED: ['Hạn chế', 'bg-amber-100 text-amber-800'],
  DISABLED: ['Chưa bật / thiếu cấu hình', 'bg-slate-100 dark:bg-muted text-slate-700 dark:text-foreground'],
  UNKNOWN: ['Chưa xác định', 'bg-slate-100 dark:bg-muted text-slate-700 dark:text-foreground'],
} as const;

function Latency({ value }: { value: number | null | undefined }) {
  return value == null ? null : <span className="shrink-0 whitespace-nowrap font-mono">
    {value === 0 ? '<1 ms' : `${value.toLocaleString('vi-VN')} ms`}
  </span>;
}

function VoiceLatency({ label, result }: { label: string; result: AiServiceCheck }) {
  return <li className="flex justify-between gap-2">
    <span className={result.status === 'UP' ? undefined : 'text-red-700 dark:text-red-300'}>
      <strong>{label}</strong> · {result.detail}
    </span>
    <Latency value={result.latencyMs} />
  </li>;
}

export default function ServiceHealthGrid({ services, isCheckingHealth, measuredAt }: {
  services: AiServiceCheck[];
  isCheckingHealth: boolean;
  measuredAt?: Date;
}) {
  const confirmed = Object.keys(servicesInfo).filter((id) => services.some((item) => item.id === id && item.status === 'UP')).length;
  const stt = services.find((item) => item.id === 'stt');
  const tts = services.find((item) => item.id === 'tts');
  return (
    <section aria-busy={isCheckingHealth} className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-lg font-semibold">
          <ShieldCheck className="size-5 text-[#ad2c00] dark:text-orange-300" /> Trạng thái dịch vụ hạ tầng
        </h2>
        <div className="flex flex-wrap items-center gap-2" aria-live="polite">
          {measuredAt && <span className="text-xs text-muted-foreground">
            Lần đo gần nhất <time dateTime={measuredAt.toISOString()}>{measuredAt.toLocaleTimeString('vi-VN')}</time>
          </span>}
          <span className="rounded-full bg-[#edf0ff] dark:bg-muted px-3 py-1 text-xs">
            {isCheckingHealth ? 'Đang kiểm tra…' : `${confirmed}/${Object.keys(servicesInfo).length} xác nhận hoạt động`}
          </span>
        </div>
      </div>
      <div className="grid gap-3.5 sm:grid-cols-2 lg:grid-cols-4">
        {Object.entries(servicesInfo).map(([id, [label, Icon]]) => {
          const result = services.find((item) => item.id === id);
          const [status, style] = statuses[result?.status ?? 'UNKNOWN'];
          return <div key={id} className="space-y-3 rounded-xl bg-white dark:bg-card p-4 shadow-xs">
            <div className="flex items-center justify-between gap-2">
              <Icon className="box-content size-4.5 rounded-lg bg-[#f1f3ff] dark:bg-muted p-2 text-[#186392] dark:text-sky-300" />
              <span className={`rounded-full px-2 py-0.5 text-xs ${style}`}>{status}</span>
            </div>
            <h3 className="text-sm font-semibold">{label}</h3>
            <div className="border-t border-[#eef0ff] dark:border-border pt-2 text-xs">
              {id === 'voice' && stt && tts ? <ul className="space-y-1.5 text-[#5c4039] dark:text-muted-foreground">
                <VoiceLatency label="STT" result={stt} />
                <VoiceLatency label="TTS" result={tts} />
              </ul> : <div className="flex justify-between gap-2">
                <span className="[overflow-wrap:anywhere] text-[#5c4039] dark:text-muted-foreground">{result?.detail || 'Chưa kiểm tra'}</span>
                <Latency value={result?.latencyMs} />
              </div>}
            </div>
          </div>;
        })}
      </div>
    </section>
  );
}
