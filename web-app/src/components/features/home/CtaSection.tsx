import Link from 'next/link';
import { ArrowRight } from 'lucide-react';
import { Reveal } from './HomeMotion';

export function CtaSection() {
  return (
    <section className="bg-[#113426] py-16 text-white sm:py-20">
      <Reveal className="mx-auto max-w-3xl px-5 text-center sm:px-8">
        <p className="text-[10px] font-semibold uppercase tracking-[.18em] text-[#c5ebd7]">Bắt đầu bước chuyển dịch</p>
        <h2 className="mt-3 font-sans text-3xl leading-tight tracking-[-0.01em] sm:text-4xl">Sẵn sàng cho cơ hội nghề nghiệp tiếp theo?</h2>
        <p className="mx-auto mt-4 max-w-xl text-sm leading-6 text-[#c3d2c8]">Rèn luyện kỹ năng, hoàn thiện câu trả lời và tự tin bước vào mọi vòng phỏng vấn với tâm thế của một ứng viên dẫn dắt.</p>
        <Link href="/register" className="group mt-7 inline-flex items-center gap-2 rounded-md bg-[#fef9ee] px-6 py-3.5 text-sm font-semibold text-[#244533] transition duration-200 hover:-translate-y-0.5 hover:bg-white hover:shadow-lg">Bắt đầu luyện tập miễn phí <ArrowRight size={16} className="transition-transform group-hover:translate-x-1" /></Link>
      </Reveal>
    </section>
  );
}
