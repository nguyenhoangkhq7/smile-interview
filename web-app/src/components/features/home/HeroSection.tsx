import Image from 'next/image';
import Link from 'next/link';
import { ArrowDown, ArrowRight, AudioLines, CheckCircle2, CircleHelp } from 'lucide-react';
import { Parallax, Reveal } from './HomeMotion';

const trustItems = ['Luyện tập mọi lúc 24/7', 'Phản hồi cá nhân hóa chuyên sâu'];

export function HeroSection() {
  return (
    <section className="relative overflow-hidden bg-[#fef9ee] dark:bg-background py-16 sm:py-20 lg:py-24">
      <div aria-hidden className="pointer-events-none absolute -right-40 top-0 h-[30rem] w-[30rem] rounded-full bg-[#dce8dc]/55 dark:bg-emerald-950/35 blur-3xl" />
      <div className="relative mx-auto grid max-w-6xl items-center gap-14 px-5 sm:px-8 lg:grid-cols-12 lg:gap-12">
        <Reveal className="lg:col-span-7">
          <h1 className="max-w-[700px] font-sans text-[clamp(2.5rem,4.5vw,3.8rem)] leading-[1.12] tracking-[-0.01em] text-[#113426] dark:text-foreground">
            Phỏng vấn <em className="text-[#70321b] dark:text-orange-300">tự tin hơn</em>. Sẵn sàng cho <em className="text-[#70321b] dark:text-orange-300">bước tiến tiếp theo</em> trong sự nghiệp.
          </h1>
          <p className="mt-6 max-w-[590px] text-[15px] leading-7 text-[#59645d] dark:text-muted-foreground">
            Chuẩn bị cho những cơ hội nghề nghiệp tốt hơn với trải nghiệm luyện phỏng vấn cá nhân hóa. Phân tích CV, thực hành đối thoại trực tiếp và nhận phản hồi đa chiều để tiến bộ rõ rệt mỗi ngày.
          </p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Link href="/interview/new" className="group inline-flex items-center justify-center gap-2 rounded-md bg-[#294b3c] px-6 py-3.5 text-sm font-semibold text-white shadow-sm transition duration-200 hover:-translate-y-0.5 hover:bg-[#113426] hover:shadow-lg">
              Bắt đầu luyện tập miễn phí <ArrowRight size={16} className="transition-transform group-hover:translate-x-1" />
            </Link>
            <a href="#quy-trinh" className="inline-flex items-center justify-center gap-2 rounded-md bg-[#f3ede2] dark:bg-secondary px-5 py-3.5 text-sm font-medium text-[#233b30] dark:text-foreground transition-colors hover:bg-[#e9e2d5] dark:hover:bg-muted">
              Khám phá cách hoạt động <ArrowDown size={15} />
            </a>
          </div>
          <div className="mt-8 flex flex-wrap gap-x-5 gap-y-2.5 text-[11px] text-[#68726b] dark:text-muted-foreground">
            {trustItems.map((item) => <span key={item} className="inline-flex items-center gap-1.5"><CheckCircle2 size={13} className="text-[#4c6450] dark:text-emerald-300" />{item}</span>)}
          </div>
        </Reveal>

        <Reveal className="relative lg:col-span-5" delay={140}>
          <Parallax>
            <div className="relative aspect-[4/4.45] overflow-hidden rounded-lg bg-[#e7e2d7] dark:bg-card shadow-[0_24px_60px_rgba(28,43,33,.14)]">
              <Image
                src="https://images.unsplash.com/photo-1551836022-d5d88e9218df?auto=format&fit=crop&w=1100&q=85"
                alt="Ứng viên tự tin luyện phỏng vấn trong không gian làm việc sáng"
                fill
                priority
                sizes="(max-width: 1024px) 90vw, 42vw"
                className="object-cover"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-[#113426]/25 via-transparent to-transparent" />
            </div>
          </Parallax>
          <div className="relative -mt-16 ml-5 mr-3 rounded-lg border border-white/80 bg-white dark:bg-card p-4 shadow-xl sm:absolute sm:-bottom-7 sm:-left-10 sm:mt-0 sm:ml-0 sm:mr-0 sm:w-[calc(100%+2.5rem)] sm:p-5">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2 text-[10px] font-semibold uppercase tracking-wide text-[#607066] dark:text-muted-foreground">
              <span className="inline-flex items-center gap-2"><span className="size-2 rounded-full bg-[#4c6450]" />Phiên thử nghiệm trực tiếp</span>
              <span className="rounded-full bg-[#e6f0e4] dark:bg-emerald-950/70 px-2.5 py-1 text-[#436555] dark:text-emerald-300">Tiến độ: 3/5 câu hỏi</span>
            </div>
            <p className="font-sans text-lg leading-snug text-[#113426] dark:text-foreground">“Hãy chia sẻ một tình huống bạn giải quyết bất đồng quan điểm trong đội ngũ dự án?”</p>
            <div className="mt-4 flex items-center justify-between border-t border-[#eee9df] dark:border-border pt-3 text-xs text-[#68726b] dark:text-muted-foreground">
              <span className="inline-flex items-center gap-2"><AudioLines size={17} className="text-[#4c6450] dark:text-emerald-300" /> Độ lưu loát: <strong className="text-[#113426] dark:text-foreground">92% (Tự tin)</strong></span>
              <span className="hidden sm:inline-flex items-center gap-1"><CircleHelp size={14} /> Khung STAR</span>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
