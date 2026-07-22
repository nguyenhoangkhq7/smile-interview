import { IconUpload, IconBriefcase, IconMic, IconBarChart, IconArrow } from '@/components/ui/icons';
import type { ReactNode } from 'react';

interface Step {
  step: string;
  icon: ReactNode;
  title: string;
  desc: string;
  accent: 'orange' | 'green';
}

const STEPS: Step[] = [
  {
    step: '01', icon: <IconUpload size={22} />, title: 'Tải CV lên',
    desc: 'Upload CV PDF — AI phân tích kỹ năng và kinh nghiệm ngay lập tức.',
    accent: 'orange',
  },
  {
    step: '02', icon: <IconBriefcase size={22} />, title: 'Chọn Job Description',
    desc: 'Tải JD hoặc dán trực tiếp. AI đối chiếu CV với yêu cầu vị trí.',
    accent: 'green',
  },
  {
    step: '03', icon: <IconMic size={22} />, title: 'Phỏng vấn giọng nói',
    desc: 'Trả lời bằng giọng nói với avatar AI 3D. Trải nghiệm như phỏng vấn thật.',
    accent: 'orange',
  },
  {
    step: '04', icon: <IconBarChart size={22} />, title: 'Nhận kết quả chi tiết',
    desc: 'Điểm số, phân tích điểm mạnh/yếu và gợi ý cải thiện cá nhân hóa.',
    accent: 'green',
  },
];

export function StepsSection() {
  return (
    <section className="py-24">
      <div className="mx-auto max-w-6xl px-6">
        {/* Heading */}
        <div className="mb-14 text-center">
          <h2 className="mb-3 text-3xl font-extrabold tracking-tight sm:text-4xl">
            4 bước để luyện tập{' '}
            <span className="gradient-brand">hiệu quả</span>
          </h2>
          <p className="text-muted-foreground">Từ CV đến phản hồi chi tiết — chỉ trong vài phút.</p>
        </div>

        {/* Step Cards */}
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map(({ step, icon, title, desc, accent }, idx) => (
            <div key={step} className="relative">
              {/* Connector arrow */}
              {idx < STEPS.length - 1 && (
                <div className="absolute -right-4 top-8 z-10 hidden text-muted-foreground/40 lg:block">
                  <IconArrow size={18} />
                </div>
              )}

              <div className={`group relative overflow-hidden rounded-2xl border p-6 shadow-sm transition-all hover:shadow-md hover:-translate-y-0.5 ${
                accent === 'orange'
                  ? 'border-brand-orange/20 bg-brand-orange/5 hover:border-brand-orange/40'
                  : 'border-brand-green/20 bg-brand-green/5 hover:border-brand-green/40'
              }`}>
                <span className="mb-1 block text-xs font-bold uppercase tracking-widest text-muted-foreground">
                  Bước {step}
                </span>
                <div className={`mb-4 inline-flex size-11 items-center justify-center rounded-xl ${
                  accent === 'orange'
                    ? 'bg-brand-orange/15 text-brand-orange'
                    : 'bg-brand-green/15 text-brand-green'
                }`}>
                  {icon}
                </div>
                <p className="mb-2 font-bold text-foreground">{title}</p>
                <p className="text-sm leading-relaxed text-muted-foreground">{desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
