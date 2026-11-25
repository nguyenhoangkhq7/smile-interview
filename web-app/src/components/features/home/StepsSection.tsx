import { FileText, Target, Mic2, ChartNoAxesCombined, LockKeyhole, SlidersHorizontal, AudioLines, ChartNoAxesColumnIncreasing } from 'lucide-react';
import { Reveal } from './HomeMotion';

const steps = [
  { number: '01', title: 'Tải CV lên', description: 'Định dạng PDF hoặc Word. Hệ thống tự động bóc tách dự án, kỹ năng cốt lõi và kinh nghiệm.', note: 'Bảo mật dữ liệu tuyệt đối', Icon: FileText, NoteIcon: LockKeyhole },
  { number: '02', title: 'Chọn Job Description', description: 'Dán nội dung JD để AI tổng hợp câu hỏi trọng tâm và đối chiếu yêu cầu vị trí.', note: 'Tùy biến cấp bậc Senior/Lead', Icon: Target, NoteIcon: SlidersHorizontal },
  { number: '03', title: 'Phỏng vấn giọng nói', description: 'Đối thoại hai chiều tự nhiên với câu hỏi đào sâu linh hoạt như buổi phỏng vấn thật.', note: 'Nhận diện ngữ điệu & phản xạ', Icon: Mic2, NoteIcon: AudioLines },
  { number: '04', title: 'Nhận kết quả & lộ trình', description: 'Báo cáo chi tiết điểm mạnh, lỗ hổng kiến thức và kế hoạch hành động từng ngày.', note: 'Bản đồ khắc phục rõ ràng', Icon: ChartNoAxesCombined, NoteIcon: ChartNoAxesColumnIncreasing },
];

export function StepsSection() {
  return (
    <section id="quy-trinh" className="scroll-mt-20 bg-[#fef9ee] dark:bg-background py-20 sm:py-24">
      <div className="mx-auto max-w-6xl px-5 sm:px-8">
        <Reveal className="mb-10 max-w-2xl sm:mb-12">
          <p className="text-[10px] font-semibold uppercase tracking-[.18em] text-[#647a68] dark:text-muted-foreground">Quy trình tinh gọn</p>
          <h2 className="mt-2 font-sans text-3xl leading-tight tracking-[-0.01em] text-[#113426] dark:text-foreground sm:text-4xl">4 bước chuẩn bị cho buổi phỏng vấn thành công</h2>
          <p className="mt-3 max-w-xl text-sm leading-6 text-[#68726b] dark:text-muted-foreground">Từ CV và bản mô tả công việc đến báo cáo năng lực cùng lộ trình ôn tập phù hợp với bạn.</p>
        </Reveal>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {steps.map(({ number, title, description, note, Icon, NoteIcon }, index) => (
            <Reveal key={number} delay={index * 90} className="h-full">
              <article className="group flex h-full min-h-[226px] flex-col rounded-md border border-[#eee9df] dark:border-border bg-white dark:bg-card p-5 transition duration-300 hover:-translate-y-1 hover:border-[#ccd8cc] dark:hover:border-border hover:shadow-[0_16px_35px_rgba(25,52,38,.09)] sm:p-6">
                <div className="mb-4 flex items-center justify-between"><span className="font-sans text-2xl text-[#335d47] dark:text-emerald-300">{number}</span><span className="flex size-9 items-center justify-center rounded-lg bg-[#f3ede2] dark:bg-secondary text-[#335d47] dark:text-emerald-300 transition-colors group-hover:bg-[#e4eee2] dark:group-hover:bg-emerald-950/70"><Icon size={17} /></span></div>
                <h3 className="text-sm font-semibold text-[#113426] dark:text-foreground">{title}</h3>
                <p className="mt-2 text-xs leading-5 text-[#73786f] dark:text-muted-foreground">{description}</p>
                <span className="mt-auto inline-flex items-center gap-1.5 pt-5 text-[10px] font-medium text-[#587060] dark:text-emerald-300"><NoteIcon size={12} />{note}</span>
              </article>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
