import Link from 'next/link';
import { IconUpload, IconArrow, IconCheck } from '@/components/ui/icons';

const TRUST_ITEMS = ['Miễn phí bắt đầu', 'Không cần thẻ tín dụng', 'Phân tích trong 30 giây'];

export function HeroSection() {
  return (
    <section className="relative overflow-hidden bg-[var(--color-bg-cream,#fdfbf7)] pb-24 pt-28">
      {/* Decorative blobs */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden>
        <div className="absolute -right-40 -top-40 h-[600px] w-[600px] rounded-full bg-brand-orange/6 blur-3xl" />
        <div className="absolute -bottom-20 -left-40 h-[500px] w-[500px] rounded-full bg-brand-green/6 blur-3xl" />
      </div>

      <div className="relative mx-auto max-w-4xl px-6 text-center">
        {/* Badge */}
        <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-brand-orange/20 bg-brand-orange/8 px-4 py-1.5 text-xs font-semibold uppercase tracking-widest text-brand-orange">
          <span className="size-1.5 animate-pulse rounded-full bg-brand-orange" />
          Được hỗ trợ bởi AI tiên tiến nhất
        </div>

        {/* Title */}
        <h1 className="mb-6 text-4xl font-extrabold leading-tight tracking-tight text-foreground sm:text-5xl lg:text-6xl">
          Phỏng vấn giả lập bằng AI.{' '}
          <span className="gradient-brand">Chuẩn xác, Tự nhiên,</span>{' '}
          Chuyên nghiệp.
        </h1>

        {/* Subtitle */}
        <p className="mx-auto mb-10 max-w-2xl text-lg leading-relaxed text-muted-foreground">
          Upload CV và Job Description — AI phân tích mức độ phù hợp, đặt câu hỏi thực tế
          bằng giọng nói 3D và cho bạn phản hồi chuyên sâu sau mỗi buổi luyện tập.
        </p>

        {/* CTAs */}
        <div className="flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
          <Link
            href="/interview/new"
            className="inline-flex items-center gap-2.5 rounded-xl bg-brand-orange px-7 py-3.5 text-sm font-bold text-white shadow-lg shadow-brand-orange/25 transition-all hover:bg-brand-orange-hover hover:shadow-xl hover:shadow-brand-orange/30 active:scale-[0.98]"
          >
            <IconUpload size={18} />
            Tải CV &amp; Bắt đầu ngay
            <IconArrow size={16} />
          </Link>
          <Link
            href="/history"
            className="inline-flex items-center gap-2 rounded-xl border border-border bg-card px-7 py-3.5 text-sm font-semibold text-foreground shadow-sm transition-all hover:border-brand-orange/40 hover:bg-accent hover:text-brand-orange"
          >
            Xem lịch sử
          </Link>
        </div>

        {/* Trust indicators */}
        <div className="mt-8 flex flex-wrap items-center justify-center gap-x-6 gap-y-2">
          {TRUST_ITEMS.map((t) => (
            <span key={t} className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <span className="flex size-4 items-center justify-center rounded-full bg-brand-green/15 text-brand-green">
                <IconCheck size={10} />
              </span>
              {t}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}
