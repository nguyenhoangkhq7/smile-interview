import type { AiConfiguration, AiCredentials, AiModels } from '@/services/adminAiPolicy';

const textFields = [
  ['interviewModel', 'Phỏng vấn · OpenRouter', true],
  ['fastModel', 'Phỏng vấn nhanh · OpenRouter', false],
  ['matchingModel', 'Đối sánh CV–JD · OpenRouter', true],
  ['verifierModel', 'Xác minh kỹ năng · OpenRouter', false],
  ['skillGapModel', 'Skill Gap · OpenRouter', true],
  ['embeddingModel', 'Embedding · Hugging Face', true],
  ['embeddingRevision', 'Revision embedding', false],
  ['sttModel', 'Nhận dạng giọng nói · OpenRouter', true],
  ['ttsModel', 'Tổng hợp giọng nói · OpenRouter', true],
  ['ttsVoice', 'Giọng đọc', true],
  ['simliFaceId', 'Simli Face ID', false],
] as const;

const input = 'w-full rounded-lg border border-[#dbe2f9] bg-[#f8f9ff] px-3 py-2 text-sm text-[#141b2c]';

interface Props {
  settings: AiConfiguration;
  models: AiModels;
  credentials: AiCredentials;
  onModels: (value: AiModels) => void;
  onCredentials: (value: AiCredentials) => void;
}

export default function AiModelsForm({ settings, models, credentials, onModels, onCredentials }: Props) {
  const providerKeys = [
    ['OpenRouter', 'openRouterKey', 'resetOpenRouterKey', settings.openRouterConfigured, settings.openRouterOverridden],
    ['Simli', 'simliKey', 'resetSimliKey', settings.simliConfigured, settings.simliOverridden],
  ] as const;
  return (
    <section className="space-y-4 rounded-2xl bg-white p-5 shadow-xs">
      <div>
        <h2 className="text-lg font-semibold">Mô hình và thông tin kết nối</h2>
        <p className="text-sm text-[#5c4039]">
          {settings.overridden ? 'Đang dùng cấu hình đã lưu' : 'Đang dùng mặc định triển khai'} · Phiên bản {settings.revision}.
          {settings.embeddingDimension && <> Model embedding phải xuất vector {settings.embeddingDimension} chiều.</>}
        </p>
        <p className="text-sm text-[#5c4039]">Dịch vụ AI đọc model và API key đã lưu khi nhận yêu cầu mới.</p>
      </div>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {textFields.map(([key, label, required]) => (
          <label className="space-y-1 text-sm font-medium" key={key}>
            <span>{label}</span>
            <input
              autoComplete="off" className={input} maxLength={key === 'ttsVoice' || key === 'embeddingRevision' ? 120 : 200}
              placeholder={required ? undefined : 'Tùy chọn'} required={required} value={models[key]}
              onChange={(event) => onModels({ ...models, [key]: event.target.value })}
            />
          </label>
        ))}
        <label className="space-y-1 text-sm font-medium">
          <span>Định dạng giọng đọc</span>
          <select className={input} value={models.ttsFormat}
            onChange={(event) => onModels({ ...models, ttsFormat: event.target.value })}>
            <option value="pcm">PCM</option><option value="mp3">MP3</option>
          </select>
        </label>
        <label className="space-y-1 text-sm font-medium">
          <span>Tần số lấy mẫu TTS (Hz)</span>
          <select className={input} value={models.ttsSampleRate}
            onChange={(event) => onModels({ ...models, ttsSampleRate: +event.target.value })}>
            {[16000, 22050, 24000, 44100, 48000].map((rate) => <option key={rate} value={rate}>{rate}</option>)}
          </select>
        </label>
      </div>
      <div className="grid gap-3 border-t border-[#eef0ff] pt-4 md:grid-cols-2">
        {providerKeys.map(([provider, field, reset, configured, overridden]) => (
          <div key={field} className="space-y-2 border border-[#eef0ff] p-3">
            <label className="block space-y-1 text-sm font-medium">
              <span>API key {provider} · {overridden ? 'Đã lưu từ admin' : configured ? 'Đã cấu hình khi triển khai' : 'Chưa cấu hình'}</span>
              <input type="password" autoComplete="new-password" className={input} maxLength={512}
                placeholder="Để trống để giữ key hiện tại" value={credentials[field]} disabled={credentials[reset]}
                onChange={(event) => onCredentials({ ...credentials, [field]: event.target.value })} />
            </label>
            {overridden && <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={credentials[reset]}
                onChange={(event) => onCredentials({ ...credentials, [reset]: event.target.checked, [field]: '' })} />
              Dùng lại API key từ môi trường
            </label>}
          </div>
        ))}
      </div>
    </section>
  );
}
