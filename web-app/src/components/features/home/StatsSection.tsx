import { CountUp, Reveal } from './HomeMotion';

const stats = [
  { value: 15000, suffix: '+', label: 'Hồ sơ ứng viên', note: 'CV & Portfolio được phân tích chuyên sâu' },
  { value: 4800, suffix: '+', label: 'Buổi phỏng vấn', note: 'Phiên mock interview giọng nói đã hoàn thành' },
  { value: 89.4, suffix: '%', label: 'Tỷ lệ tiến bộ', note: 'Cải thiện phản xạ sau 3 buổi luyện tập' },
  { value: 4.9, suffix: ' / 5.0', label: 'Mức độ hài lòng', note: 'Đánh giá từ các ứng viên đã trải nghiệm' },
];

export function StatsSection() {
  return (
    <section aria-label="Kết quả từ cộng đồng" className="bg-[#f7f2e8] dark:bg-muted/40 py-10 sm:py-12">
      <div className="mx-auto grid max-w-6xl grid-cols-2 gap-x-7 gap-y-9 px-5 sm:px-8 lg:grid-cols-4">
        {stats.map((stat, index) => (
          <Reveal key={stat.label} delay={index * 80}>
            <div className="font-sans text-[2rem] leading-none tracking-normal text-[#113426] dark:text-foreground sm:text-[2.4rem]"><CountUp value={stat.value} suffix={stat.suffix} /></div>
            <h2 className="mt-2 text-sm font-semibold text-[#3e5949] dark:text-foreground">{stat.label}</h2>
            <p className="mt-1 max-w-[240px] text-xs leading-5 text-[#73786f] dark:text-muted-foreground">{stat.note}</p>
          </Reveal>
        ))}
      </div>
    </section>
  );
}
