import Link from 'next/link';
import { IconUpload } from '@/components/ui/icons';

export function CtaSection() {
  return (
    <section className="py-24">
      <div className="mx-auto max-w-4xl px-6">
        <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-brand-orange to-brand-orange-hover p-12 text-center shadow-2xl shadow-brand-orange/30">
          {/* Decorative ring */}
          <div className="pointer-events-none absolute -right-16 -top-16 size-64 rounded-full border-2 border-white/10" aria-hidden />
          <div className="pointer-events-none absolute -bottom-10 -left-10 size-48 rounded-full border-2 border-white/10" aria-hidden />

          <h2 className="mb-4 text-3xl font-extrabold text-white sm:text-4xl">
            Sẵn sàng chinh phục buổi phỏng vấn tiếp theo?
          </h2>
          <p className="mx-auto mb-8 max-w-xl text-base text-white/80">
            Hàng nghìn ứng viên đã cải thiện kỹ năng và tự tin hơn sau khi luyện tập với Smile Interview.
          </p>
          <Link
            href="/interview/new"
            className="inline-flex items-center gap-2.5 rounded-xl bg-white px-8 py-3.5 text-sm font-extrabold text-brand-orange shadow-lg transition-all hover:bg-white/90 hover:shadow-xl active:scale-[0.98]"
          >
            <IconUpload size={18} />
            Thử ngay — Miễn phí
          </Link>
        </div>
      </div>
    </section>
  );
}
