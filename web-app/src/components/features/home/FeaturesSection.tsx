import { Check, CheckCircle2, Lightbulb, ListChecks } from 'lucide-react';
import { Reveal } from './HomeMotion';
import type { ReactNode } from 'react';

function SectionHeading({ eyebrow, title, description }: { eyebrow: string; title: string; description: string }) {
  return <Reveal className="mx-auto mb-14 max-w-2xl text-center"><p className="text-[10px] font-semibold uppercase tracking-[.18em] text-[#647a68]">{eyebrow}</p><h2 className="mt-2 font-sans text-3xl leading-tight tracking-[-0.01em] text-[#113426] sm:text-4xl">{title}</h2><p className="mt-4 text-sm leading-6 text-[#68726b]">{description}</p></Reveal>;
}

function FeatureCopy({ index, title, children, bullets }: { index: string; title: string; children: string; bullets: string[] }) {
  return <div><p className="text-[10px] font-semibold uppercase tracking-[.16em] text-[#70321b]">Tính năng {index}</p><h3 className="mt-2 font-sans text-2xl leading-snug text-[#113426]">{title}</h3><p className="mt-3 text-sm leading-6 text-[#68726b]">{children}</p><ul className="mt-4 space-y-2">{bullets.map((bullet) => <li key={bullet} className="flex items-start gap-2 text-xs leading-5 text-[#43564a]"><CheckCircle2 size={15} className="mt-0.5 shrink-0 text-[#587060]" />{bullet}</li>)}</ul></div>;
}

function Panel({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`rounded-lg border border-[#eee9df] bg-white p-5 shadow-[0_10px_30px_rgba(32,47,35,.05)] sm:p-6 ${className}`}>{children}</div>;
}

export function FeaturesSection() {
  return (
    <section id="tinh-nang" className="scroll-mt-20 bg-[#f7f2e8] py-20 sm:py-24">
      <div className="mx-auto max-w-6xl px-5 sm:px-8">
        <SectionHeading eyebrow="Trải nghiệm tương hỗ thông minh" title="Mọi công cụ cần thiết cho hành trình bứt phá sự nghiệp" description="Công nghệ AI đóng vai trò người dẫn dắt thầm lặng, đặt nội lực và sự đĩnh đạc của bạn làm trung tâm của mọi cuộc trao đổi." />
        <div className="space-y-20 sm:space-y-24">
          <div className="grid items-center gap-9 lg:grid-cols-12 lg:gap-14">
            <Reveal className="lg:col-span-5"><FeatureCopy index="01" title="Phỏng vấn đối thoại giọng nói thời gian thực" bullets={['Độ trễ thấp, trò chuyện tự nhiên như qua điện thoại', 'Câu hỏi đào sâu theo phong cách lãnh đạo']}>AI đặt câu hỏi tiếp nối và phản hồi theo từng ý tứ, giúp bạn rèn phản xạ, nhịp thở và sự rành mạch trước áp lực.</FeatureCopy></Reveal>
            <Reveal className="lg:col-span-7" delay={100}><Panel>
              <div className="mb-4 flex items-center justify-between gap-2"><div className="flex items-center gap-2 text-sm font-semibold text-[#244533]"><span className="size-2.5 rounded-full bg-[#587060]" />Phòng phỏng vấn mô phỏng • VP Engineering</div><span className="text-[10px] text-[#7b8178]">08:42</span></div>
              <div className="mb-4 flex h-20 items-center justify-center gap-1 rounded-md bg-[#f3ede2] text-[#436555]">{[4,8,14,10,6,12,16,9,4,11,7,13,5].map((height, i) => <span key={i} className="w-1.5 rounded-full bg-current" style={{ height: `${height * 3}px`, animation: `wave 1.2s ease-in-out ${i * 70}ms infinite alternate` }} />)}</div>
              <div className="space-y-2 text-xs leading-5"><div className="rounded-md bg-[#f8f3e8] p-3"><span className="text-[9px] font-semibold uppercase tracking-wide text-[#587060]">Người phỏng vấn (AI Coach)</span><p className="mt-1 text-[#34453a]">“Khi kiến trúc microservice gặp sự cố nghẽn mạng ở tầng gateway, bạn và đội ngũ SRE đã ưu tiên những chỉ số nào đầu tiên?”</p></div><div className="rounded-md bg-[#fef9ee] p-3"><span className="text-[9px] font-semibold uppercase tracking-wide text-[#727970]">Ứng viên (Giọng nói trực tiếp)</span><p className="mt-1 text-[#34453a]">“Tôi lập tức kiểm tra tỷ lệ lỗi HTTP 5xx cùng p99 latency trên Prometheus dashboard...”</p></div></div>
            </Panel></Reveal>
          </div>

          <div className="grid items-center gap-9 lg:grid-cols-12 lg:gap-14">
            <Reveal className="order-2 lg:col-span-7 lg:order-1"><Panel>
              <div className="mb-6 flex items-start justify-between gap-3"><div><h4 className="text-sm font-semibold text-[#244533]">Báo cáo Năng lực & Khả năng Trúng tuyển</h4><p className="mt-1 text-[11px] text-[#7b8178]">Phân tích phiên phỏng vấn gần nhất</p></div><span className="rounded-md bg-[#dcebdc] px-3 py-1.5 font-sans text-lg text-[#244533]">88 / 100</span></div>
              <div className="space-y-4">{[['Kiến thức chuyên môn cốt lõi', 91], ['Cấu trúc câu trả lời (Khung STAR)', 85], ['Tốc độ & Độ mạch lạc', 94]].map(([label, score]) => <div key={label}><div className="mb-1.5 flex justify-between text-[11px] text-[#49564d]"><span>{label}</span><b className="text-[#244533]">{score}%</b></div><div className="h-1.5 rounded-full bg-[#eee9df]"><div className="h-full rounded-full bg-[#587060]" style={{ width: `${score}%` }} /></div></div>)}</div>
              <div className="mt-5 flex gap-2 rounded-md bg-[#f8f3e8] p-3 text-xs leading-5 text-[#536257]"><Lightbulb size={16} className="mt-0.5 shrink-0 text-[#8a5a32]" /><p><b>Gợi ý cải thiện:</b> Lượng hóa kết quả sau mỗi quyết định để câu trả lời thuyết phục hơn.</p></div>
            </Panel></Reveal>
            <Reveal className="order-1 lg:col-span-5 lg:order-2" delay={100}><FeatureCopy index="02" title="Đánh giá kiến thức chuyên môn & kỹ năng toàn diện" bullets={['Đo lường cấu trúc mở bài – giải pháp – kết quả', 'Bảng điểm chấm theo tiêu chí tuyển dụng quốc tế']}>Hệ thống phân tích độ sâu kỹ thuật, khả năng cấu trúc giải pháp và kỹ năng ứng biến, đồng thời chỉ rõ những điểm cần bổ sung.</FeatureCopy></Reveal>
          </div>

          <div className="grid items-center gap-9 lg:grid-cols-12 lg:gap-14">
            <Reveal className="lg:col-span-5"><FeatureCopy index="03" title="Tự động xây dựng lộ trình ôn tập cá nhân hóa" bullets={['Chia nhỏ nhiệm vụ ôn luyện thành thẻ công việc', 'Theo dõi tiến độ theo thời gian thực']}>Biến kết quả phỏng vấn thành danh sách việc có thể hành động ngay, chia theo ngày để bạn tập trung vào đúng điểm cần cải thiện.</FeatureCopy></Reveal>
            <Reveal className="lg:col-span-7" delay={100}><Panel>
              <div className="mb-5 flex items-center justify-between gap-2"><span className="flex items-center gap-2 text-sm font-semibold text-[#244533]"><ListChecks size={17} />Kế hoạch cải thiện 7 ngày</span><span className="rounded-full bg-[#e5efe2] px-2.5 py-1 text-[10px] text-[#436555]">Hoàn thành: 29%</span></div>
              <div className="space-y-2 text-xs">{[['Ôn tập khái niệm Database Sharding & Replication', 'Ngày 1', true], ['Viết lại kịch bản STAR: Xử lý mâu thuẫn kỹ thuật', 'Hôm nay', false], ['Luyện tập vòng 2: Mock interview System Design', 'Ngày 4', false]].map(([task, day, done]) => <div key={task as string} className="flex items-center gap-3 rounded-md bg-[#f8f3e8] p-3"><span className={`flex size-4 shrink-0 items-center justify-center rounded-sm ${done ? 'bg-[#436555] text-white' : 'bg-[#e9e4da] text-transparent'}`}><Check size={12} /></span><span className={`flex-1 leading-5 ${done ? 'text-[#7b8178] line-through' : 'text-[#34453a]'}`}>{task}</span><span className="shrink-0 text-[10px] text-[#6f776d]">{day}</span></div>)}</div>
            </Panel></Reveal>
          </div>

          <div className="grid items-center gap-9 lg:grid-cols-12 lg:gap-14">
            <Reveal className="order-2 lg:col-span-7 lg:order-1"><Panel>
              <div className="mb-5 flex items-center justify-between"><span className="text-sm font-semibold text-[#244533]">Mẫu chuẩn STAR từ Tech Lead</span><span className="rounded-full bg-[#e5efe2] px-2.5 py-1 text-[10px] text-[#436555]">Khuyên dùng</span></div>
              <div className="space-y-2 text-xs leading-5">{[['S · TÌNH HUỐNG', 'Đội ngũ tiếp nhận hệ thống legacy bị rò rỉ bộ nhớ, khiến hệ thống sập vào khung giờ cao điểm.'], ['A · HÀNH ĐỘNG', 'Tôi triển khai Heap Dump Profiler, khoanh vùng dịch vụ thanh toán và tổ chức code review khẩn.'], ['R · KẾT QUẢ ĐẠT ĐƯỢC', 'Hệ thống duy trì 99.98% uptime suốt đợt khuyến mãi.']].map(([label, body], index) => <div key={label} className="rounded-md bg-[#f8f3e8] p-3"><span className={`inline-block rounded px-2 py-0.5 text-[9px] font-semibold ${index === 2 ? 'bg-[#dcebdc] text-[#436555]' : 'bg-[#eee9df] text-[#647067]'}`}>{label}</span><p className="mt-1 text-[#48564c]">“{body}”</p></div>)}</div>
            </Panel></Reveal>
            <Reveal className="order-1 lg:col-span-5 lg:order-2" delay={100}><FeatureCopy index="04" title="Tham khảo câu trả lời mẫu chuẩn STAR & Tech Lead" bullets={['Hơn 500 tình huống mẫu đa dạng lĩnh vực', 'Ghi chú từ vựng đắt giá cho từng ngành nghề']}>Hiểu cách chuyên gia phân bổ trọng số: bối cảnh ngắn gọn, hành động quyết liệt và kết quả đo đếm được — thay vì học thuộc câu trả lời.</FeatureCopy></Reveal>
          </div>
        </div>
      </div>
    </section>
  );
}
