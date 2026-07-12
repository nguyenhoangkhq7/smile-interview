'use client';

import { useState } from 'react';
import { adminService, EvaluationCriteriaDto, CreateEvaluationCriteriaPayload } from '@/services/adminService';
import { toast } from './Toast';
import Modal from './Modal';
import RuleDashboardSection from './rule-dashboard/RuleDashboardSection';
import ActionIconButton from './rule-dashboard/ActionIconButton';

interface Props {
  criteria: EvaluationCriteriaDto[];
  onRefresh: () => void;
}

const emptyForm: CreateEvaluationCriteriaPayload = { criteria_name: '', prompt_instruction: '' };

export default function EvaluationCriteriaTable({ criteria, onRefresh }: Props) {
  const [modalOpen, setModalOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<EvaluationCriteriaDto | null>(null);
  const [form, setForm] = useState<CreateEvaluationCriteriaPayload>(emptyForm);
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [viewCriteria, setViewCriteria] = useState<EvaluationCriteriaDto | null>(null);

  const openCreate = () => {
    setEditTarget(null);
    setForm(emptyForm);
    setModalOpen(true);
  };

  const openEdit = (crit: EvaluationCriteriaDto) => {
    setEditTarget(crit);
    setForm({ criteria_name: crit.criteria_name, prompt_instruction: crit.prompt_instruction });
    setModalOpen(true);
  };

  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 8;
  const totalPages = Math.ceil(criteria.length / itemsPerPage) || 1;
  const displayedCriteria = criteria.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  );

  const handlePrevPage = () => {
    setCurrentPage((p) => Math.max(1, p - 1));
  };

  const handleNextPage = () => {
    setCurrentPage((p) => Math.min(totalPages, p + 1));
  };

  const handleSave = async () => {
    if (!form.criteria_name.trim()) { toast.error('Tên tiêu chí không được để trống'); return; }
    if (!form.prompt_instruction.trim()) { toast.error('Prompt instruction không được để trống'); return; }
    setSaving(true);
    try {
      if (editTarget) {
        await adminService.updateEvaluationCriteria(editTarget.id, form);
        toast.success('Cập nhật tiêu chí thành công!');
      } else {
        await adminService.createEvaluationCriteria(form);
        toast.success('Tạo tiêu chí thành công!');
      }
      setModalOpen(false);
      onRefresh();
    } catch {
      toast.error('Có lỗi xảy ra. Vui lòng thử lại.');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Xóa tiêu chí này sẽ ảnh hưởng đến các cấu hình trọng số liên quan. Bạn có chắc chắn?')) return;
    setDeletingId(id);
    try {
      await adminService.deleteEvaluationCriteria(id);
      toast.success('Xóa tiêu chí thành công.');
      onRefresh();
    } catch {
      toast.error('Không thể xóa tiêu chí này.');
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <RuleDashboardSection
      title="Tiêu chí đánh giá"
      count={criteria.length}
      countLabel="tiêu chí"
      description="Các tiêu chí đánh giá năng lực của ứng viên. Mỗi tiêu chí có hướng dẫn prompt chi tiết để hệ thống chấm điểm chính xác."
      action={(
        <button
          onClick={openCreate}
          className="inline-flex items-center gap-2 rounded-xl border border-orange-500/25 bg-orange-500/10 px-3.5 py-2 text-sm font-semibold text-orange-300 transition-colors hover:border-orange-500/50 hover:bg-orange-500/15 hover:text-white"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M12 5v14M5 12h14" /></svg>
          Thêm tiêu chí
        </button>
      )}
    >
      <div className="overflow-x-auto border-t border-white/6 bg-slate-950/35">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-700/70 bg-white/[0.03]">
              <th className="min-w-[80px] px-5 py-4 text-left text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">ID</th>
              <th className="px-5 py-4 text-left text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Tên tiêu chí</th>
              <th className="px-5 py-4 text-left text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Prompt Instruction</th>
              <th className="w-28 px-5 py-4 text-right text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Hành động</th>
            </tr>
          </thead>
          <tbody>
            {displayedCriteria.length === 0 && (
              <tr><td colSpan={4} className="px-5 py-10 text-center text-slate-400">Chưa có tiêu chí nào.</td></tr>
            )}
            {displayedCriteria.map((crit) => {
              return (
                <tr key={crit.id} className="border-b border-slate-700/60 transition-colors hover:bg-white/[0.03]">
                  <td className="px-5 py-4 align-middle font-mono text-xs tabular-nums text-slate-300 whitespace-nowrap">{crit.id}</td>
                  <td className="px-5 py-4 align-middle whitespace-nowrap text-sm text-slate-300 font-medium">{crit.criteria_name}</td>
                  <td className="max-w-2xl px-5 py-4 align-middle">
                    <button
                      type="button"
                      onClick={() => setViewCriteria(crit)}
                      className="text-left w-full hover:text-white group transition-colors focus:outline-none"
                    >
                      <p className="line-clamp-2 text-sm leading-relaxed text-slate-300 group-hover:text-slate-200">
                        {crit.prompt_instruction}
                      </p>
                      <span className="mt-1 inline-flex items-center gap-1 text-[11px] font-semibold text-teal-400 group-hover:text-teal-300">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                          <path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
                        </svg>
                        Xem chi tiết
                      </span>
                    </button>
                  </td>
                  <td className="px-5 py-4 align-middle">
                    <div className="flex items-center justify-end gap-2">
                      <ActionIconButton
                        label="Sửa tiêu chí"
                        onClick={() => openEdit(crit)}
                        icon={(
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" /><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" /></svg>
                        )}
                      />
                      <ActionIconButton
                        label="Xóa tiêu chí"
                        variant="danger"
                        onClick={() => handleDelete(crit.id)}
                        disabled={deletingId === crit.id}
                        icon={(
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3 6 5 6 21 6" /><path d="M19 6l-1 14H6L5 6" /><path d="M10 11v6M14 11v6" /><path d="M9 6V4h6v2" /></svg>
                        )}
                      />
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between px-1 pt-4">
          <span className="text-xs text-slate-300 font-medium">
            Trang {currentPage} / {totalPages} (tổng {criteria.length} mục)
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={handlePrevPage}
              disabled={currentPage === 1}
              className="rounded-lg border border-slate-700 bg-slate-900/60 px-3.5 py-1.5 text-xs font-semibold text-slate-300 hover:border-slate-500 hover:bg-white/[0.08] hover:text-white transition-all disabled:opacity-40 disabled:hover:border-slate-700 disabled:hover:bg-slate-900/60 disabled:hover:text-slate-300 min-h-[32px] min-w-[64px] focus:outline-none focus:ring-1 focus:ring-orange-500/30"
            >
              Trước
            </button>
            <button
              onClick={handleNextPage}
              disabled={currentPage === totalPages}
              className="rounded-lg border border-slate-700 bg-slate-900/60 px-3.5 py-1.5 text-xs font-semibold text-slate-300 hover:border-slate-500 hover:bg-white/[0.08] hover:text-white transition-all disabled:opacity-40 disabled:hover:border-slate-700 disabled:hover:bg-slate-900/60 disabled:hover:text-slate-300 min-h-[32px] min-w-[64px] focus:outline-none focus:ring-1 focus:ring-orange-500/30"
            >
              Sau
            </button>
          </div>
        </div>
      )}

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editTarget ? 'Sửa tiêu chí' : 'Thêm tiêu chí'} size="lg">
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-slate-400 mb-1.5">Tên tiêu chí <span className="text-red-400">*</span></label>
            <input
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500/30 transition-colors"
              value={form.criteria_name}
              onChange={(e) => setForm({ ...form, criteria_name: e.target.value })}
              placeholder="VD: Tech Stack Alignment"
            />
          </div>
          <div>
            <label className="block text-sm text-slate-400 mb-1.5">
              Prompt Instruction <span className="text-red-400">*</span>
              <span className="text-slate-600 ml-2 text-xs">(được tiêm trực tiếp vào LLM)</span>
            </label>
            <textarea
              rows={10}
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm font-mono focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500/30 transition-colors resize-y"
              value={form.prompt_instruction}
              onChange={(e) => setForm({ ...form, prompt_instruction: e.target.value })}
              placeholder={'Tech Stack Alignment:\n- status="matched" if candidate lists ≥ 3 core required technologies from JD...\n- status="weak" if...\n- status="missing" if...'}
            />
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button onClick={() => setModalOpen(false)} className="px-4 py-2 text-sm text-slate-400 hover:text-white border border-slate-700 hover:border-slate-600 rounded-lg transition-colors">Hủy</button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-4 py-2 text-sm font-medium bg-orange-600 hover:bg-orange-500 disabled:opacity-50 text-white rounded-lg transition-colors"
            >
              {saving ? 'Đang lưu...' : 'Lưu'}
            </button>
          </div>
        </div>
      </Modal>

      {viewCriteria && (
        <Modal
          open={Boolean(viewCriteria)}
          onClose={() => setViewCriteria(null)}
          title={`Chi tiết Prompt Instruction - ${viewCriteria.criteria_name}`}
          size="lg"
        >
          <div className="space-y-4">
            <div className="rounded-xl border border-slate-700/60 bg-slate-900/50 p-4">
              <h4 className="text-xs uppercase tracking-wider text-slate-500 font-semibold mb-1">Tên tiêu chí</h4>
              <p className="text-sm font-medium text-white">{viewCriteria.criteria_name}</p>
            </div>
            <div className="rounded-xl border border-slate-700/60 bg-slate-900/50 p-4">
              <h4 className="text-xs uppercase tracking-wider text-slate-500 font-semibold mb-2">Prompt Instruction</h4>
              <pre className="whitespace-pre-wrap font-mono text-sm leading-relaxed text-slate-200 bg-slate-950 p-3.5 rounded-lg border border-slate-800 max-h-[50vh] overflow-y-auto">
                {viewCriteria.prompt_instruction}
              </pre>
            </div>
            <div className="flex justify-end pt-2">
              <button
                type="button"
                onClick={() => setViewCriteria(null)}
                className="rounded-lg border border-slate-700 bg-slate-800 px-4 py-2 text-sm text-slate-300 hover:text-white transition-colors"
              >
                Đóng
              </button>
            </div>
          </div>
        </Modal>
      )}
    </RuleDashboardSection>
  );
}
