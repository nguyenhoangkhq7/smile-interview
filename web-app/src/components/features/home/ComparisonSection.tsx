import { Activity, CalendarClock, CircleDollarSign, CloudUpload, HeartCrack, Link2Off, ListChecks, Route, ShieldCheck, Sparkles, TrendingUp } from 'lucide-react';
import { Reveal } from './HomeMotion';

const traditional = [
  { icon: CircleDollarSign, title: 'Chi phí đắt đỏ', description: '500.000đ – 1.500.000đ cho mỗi buổi hẹn mentor.' },
  { icon: HeartCrack, title: 'Phản hồi cảm tính', description: 'Nhận xét chung chung, khó đo lường tiến độ.' },
  { icon: CalendarClock, title: 'Khó sắp xếp lịch', description: 'Mất nhiều ngày trao đổi để tìm khung giờ phù hợp.' },
  { icon: Link2Off, title: 'Học tập rời rạc', description: 'Thiếu dữ liệu theo dõi và kế hoạch sau buổi gặp.' },
];
const platform = [
  { icon: Activity, title: 'Linh hoạt 24/7', description: 'Luyện tập bất kỳ lúc nào, bao nhiêu lần tùy thích.' },
  { icon: TrendingUp, title: 'Đo lường khoa học', description: 'Phân tích độ sâu kỹ thuật và cấu trúc lập luận.' },
  { icon: Route, title: 'Lộ trình tự động', description: 'Chuyển hóa lỗ hổng kiến thức thành thẻ ôn tập.' },
  { icon: ShieldCheck, title: 'Tối ưu chi phí', description: 'Luyện tập chuyên sâu với mức đầu tư phù hợp.' },
];

export function ComparisonSection() {
  return (
    <section id="lo-trinh" className="scroll-mt-20 bg-[#fef9ee] dark:bg-background py-20 sm:py-24">
      <div className="mx-auto max-w-6xl px-5 sm:px-8">
        <Reveal className="mx-auto mb-12 max-w-2xl text-center"><p className="text-[10px] font-semibold uppercase tracking-[.18em] text-[#647a68] dark:text-muted-foreground">So sánh phương pháp</p><h2 className="mt-2 font-sans text-3xl leading-tight text-[#113426] dark:text-foreground sm:text-4xl">Một cách chuẩn bị thông minh hơn cho sự nghiệp</h2><p className="mt-4 text-sm leading-6 text-[#68726b] dark:text-muted-foreground">Đặt hiệu quả và sự tự chủ của bạn lên hàng đầu với phương thức chuẩn bị gọn nhẹ.</p></Reveal>
        <div className="grid gap-5 md:grid-cols-2 lg:gap-7">
          <Reveal><article className="h-full rounded-lg bg-[#f3ede2] dark:bg-secondary p-6 sm:p-8"><div className="mb-7 flex items-center justify-between"><div><p className="text-[10px] font-semibold uppercase tracking-widest text-[#74786f] dark:text-muted-foreground">Phương pháp cũ</p><h3 className="mt-1 font-sans text-xl text-[#3b423c] dark:text-foreground">Chuẩn bị truyền thống</h3></div><CloudUpload size={22} className="text-[#77796f] dark:text-muted-foreground" /></div><ul className="space-y-5">{traditional.map(({ icon: Icon, title, description }) => <li key={title} className="flex gap-3"><Icon size={18} className="mt-0.5 shrink-0 text-[#74786f] dark:text-muted-foreground" /><div><h4 className="text-sm font-semibold text-[#41463f] dark:text-foreground">{title}</h4><p className="mt-1 text-xs leading-5 text-[#77796f] dark:text-muted-foreground">{description}</p></div></li>)}</ul><p className="mt-7 border-t border-[#e2dbce] dark:border-border pt-4 text-[10px] italic text-[#77796f] dark:text-muted-foreground">Dễ tạo cảm giác áp lực và trì hoãn luyện tập.</p></article></Reveal>
          <Reveal delay={120}><article className="relative h-full overflow-hidden rounded-lg border border-[#e9ece2] dark:border-border bg-white dark:bg-card p-6 shadow-[0_12px_35px_rgba(32,47,35,.07)] sm:p-8"><div aria-hidden className="absolute -right-14 -top-14 size-36 rounded-full bg-[#e8f1e6] dark:bg-emerald-950/70" /><div className="relative mb-7 flex items-center justify-between"><div><p className="text-[10px] font-semibold uppercase tracking-widest text-[#587060] dark:text-emerald-300">Phương pháp tinh giản</p><h3 className="mt-1 font-sans text-xl text-[#113426] dark:text-foreground">Smile Interview Platform</h3></div><span className="rounded-lg bg-[#e5efe2] dark:bg-emerald-950/70 p-2.5 text-[#436555] dark:text-emerald-300"><ShieldCheck size={19} /></span></div><ul className="relative space-y-5">{platform.map(({ icon: Icon, title, description }) => <li key={title} className="flex gap-3"><Icon size={18} className="mt-0.5 shrink-0 text-[#587060] dark:text-emerald-300" /><div><h4 className="text-sm font-semibold text-[#244533] dark:text-foreground">{title}</h4><p className="mt-1 text-xs leading-5 text-[#68726b] dark:text-muted-foreground">{description}</p></div></li>)}</ul><div className="relative mt-7 flex items-center justify-between border-t border-[#eee9df] dark:border-border pt-4 text-[10px] font-medium text-[#587060] dark:text-emerald-300"><span className="flex items-center gap-1.5"><ListChecks size={13} />Học tập có lộ trình</span><Sparkles size={15} /></div></article></Reveal>
        </div>
      </div>
    </section>
  );
}
