import Link from 'next/link';
import { IconCheck, IconArrow } from '@/components/ui/icons';

const FEATURES = [
  'Phân tích CV & JD tức thì bằng AI',
  'Avatar 3D với giọng nói tự nhiên',
  'Câu hỏi được cá nhân hóa theo vị trí',
  'Phản hồi chi tiết sau mỗi buổi',
  'Lưu lịch sử & theo dõi tiến trình',
  'Hỗ trợ tiếng Việt & tiếng Anh',
];

export function FeaturesSection() {
  return (
    <section className="bg-card/40 py-24">
      <div className="mx-auto max-w-6xl px-6">
        <div className="grid items-center gap-16 lg:grid-cols-2">
          {/* Left: copy */}
          <div>
            <h2 className="mb-5 text-3xl font-extrabold leading-tight tracking-tight sm:text-4xl">
              Tất cả những gì bạn cần để{' '}
              <span className="gradient-brand">tự tin phỏng vấn</span>
            </h2>
            <p className="mb-8 leading-relaxed text-muted-foreground">
              Smile Interview không chỉ hỏi câu hỏi — nền tảng hiểu CV của bạn, hiểu JD
              của nhà tuyển dụng và cho bạn trải nghiệm phỏng vấn thực tế nhất.
            </p>
            <Link
              href="/interview/new"
              className="inline-flex items-center gap-2 rounded-xl bg-brand-orange px-6 py-3 text-sm font-bold text-white shadow-md shadow-brand-orange/25 transition-all hover:bg-brand-orange-hover hover:shadow-lg active:scale-[0.98]"
            >
              Bắt đầu miễn phí
              <IconArrow size={15} />
            </Link>
          </div>

          {/* Right: feature grid */}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {FEATURES.map((feat) => (
              <div
                key={feat}
                className="flex items-start gap-3 rounded-xl border border-border bg-card p-4 shadow-sm transition-all hover:border-brand-orange/30 hover:shadow-md"
              >
                <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full bg-brand-orange/15 text-brand-orange">
                  <IconCheck size={11} />
                </span>
                <span className="text-sm font-medium leading-snug text-foreground">{feat}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
