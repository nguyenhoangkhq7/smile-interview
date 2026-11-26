import { Eye } from 'lucide-react';
import { dateLabel, modeLabel, statusLabels, statusStyle } from './sessionDisplay';
import type { InterviewPage } from './types';

export default function InterviewSessionList({ data, onPage, onSelect }: {
  data: InterviewPage;
  onPage: (page: number) => void;
  onSelect: (id: string) => void;
}) {
  const last = Math.max(1, Math.ceil(data.total / data.size));
  const firstRow = data.total ? (data.page - 1) * data.size + 1 : 0;

  return (
    <section className="overflow-hidden rounded-xl bg-white shadow-xs">
      <div className="flex items-center gap-2 px-5 py-4">
        <h2 className="font-semibold">Danh sách phiên phỏng vấn</h2>
        <span className="rounded-full bg-[#edf0ff] px-2 py-0.5 text-xs tabular-nums">{data.total.toLocaleString('vi-VN')}</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[780px] text-left text-sm">
          <thead className="bg-[#f1f3ff] text-xs text-[#5c4039]">
            <tr>{['Ứng viên / Mã phiên', 'Vị trí', 'Trạng thái', 'Chế độ', 'Ngày tạo', 'Chi tiết'].map((heading) =>
              <th key={heading} scope="col" className="px-5 py-3 font-semibold">{heading}</th>)}</tr>
          </thead>
          <tbody className="divide-y divide-[#edf0ff]">
            {data.sessions.map((session) => (
              <tr key={session.id} className="hover:bg-[#f8f9ff]">
                <td className="px-5 py-3">
                  <button type="button" onClick={() => onSelect(session.id)} className="font-semibold text-[#141b2c] hover:underline">
                    {session.candidateName ?? 'Ứng viên không còn hồ sơ'}
                  </button>
                  <div className="max-w-44 truncate font-mono text-xs text-[#5c4039]" title={session.id}>{session.id}</div>
                </td>
                <td className="px-5 py-3">{session.roleTitle ?? '—'}</td>
                <td className="px-5 py-3"><span className={statusStyle(session.status) + ' rounded-full px-2 py-1 text-xs font-medium'}>
                  {statusLabels[session.status]}
                </span></td>
                <td className="px-5 py-3">{modeLabel(session.mode)}</td>
                <td className="whitespace-nowrap px-5 py-3">{dateLabel(session.createdAt)}</td>
                <td className="px-5 py-3">
                  <button type="button" onClick={() => onSelect(session.id)} aria-label={'Xem phiên ' + session.id}
                    className="flex items-center gap-1 rounded-md px-2 py-1 text-[#186392] hover:bg-[#edf0ff]">
                    <Eye className="size-4" /> Xem
                  </button>
                </td>
              </tr>
            ))}
            {!data.sessions.length && <tr><td colSpan={6} className="px-5 py-9 text-center text-[#5c4039]">Không tìm thấy phiên phù hợp.</td></tr>}
          </tbody>
        </table>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[#edf0ff] px-5 py-3 text-sm">
        <span>{firstRow}–{firstRow ? firstRow + data.sessions.length - 1 : 0} / {data.total.toLocaleString('vi-VN')} phiên</span>
        {last > 1 && <nav aria-label="Phân trang phiên phỏng vấn" className="flex items-center gap-3">
          <button type="button" disabled={data.page <= 1} onClick={() => onPage(data.page - 1)}
            className="rounded-lg bg-[#edf0ff] px-3 py-1.5 disabled:opacity-40">Trước</button>
          <span>Trang {data.page} / {last}</span>
          <button type="button" disabled={data.page >= last} onClick={() => onPage(data.page + 1)}
            className="rounded-lg bg-[#edf0ff] px-3 py-1.5 disabled:opacity-40">Sau</button>
        </nav>}
      </div>
    </section>
  );
}
