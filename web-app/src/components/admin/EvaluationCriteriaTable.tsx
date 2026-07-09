'use client';

import { useState } from 'react';
import { adminService, EvaluationCriteriaDto, CreateEvaluationCriteriaPayload } from '@/services/adminService';
import { toast } from './Toast';
import Modal from './Modal';

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
  const [expandedId, setExpandedId] = useState<number | null>(null);

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
  const itemsPerPage = 10;
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

  const safeOnRefresh = () => {
    setCurrentPage(1);
    onRefresh();
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
      safeOnRefresh();
    } catch {
      toast.error('Có lỗi xảy ra. Vui lòng thử lại.');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Xóa tiêu chí này? Các mapping liên quan cũng sẽ bị xóa.')) return;
    setDeletingId(id);
    try {
      await adminService.deleteEvaluationCriteria(id);
      toast.success('Đã xóa tiêu chí.');
      safeOnRefresh();
    } catch {
      toast.error('Không thể xóa tiêu chí này.');
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-300">Tiêu chí đánh giá ({criteria.length})</h3>
        <button
          onClick={openCreate}
          className="flex items-center gap-2 px-3 py-1.5 bg-orange-600 hover:bg-orange-500 text-white text-sm font-medium rounded-lg transition-colors"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M12 5v14M5 12h14" /></svg>
          Thêm
        </button>
      </div>

      <div className="overflow-x-auto rounded-xl border border-slate-800">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-800 bg-slate-800/50">
              <th className="text-left px-4 py-3 text-slate-400 font-medium w-8">ID</th>
              <th className="text-left px-4 py-3 text-slate-400 font-medium">Tên tiêu chí</th>
              <th className="text-left px-4 py-3 text-slate-400 font-medium">Prompt Instruction</th>
              <th className="text-right px-4 py-3 text-slate-400 font-medium">Hành động</th>
            </tr>
          </thead>
          <tbody>
            {displayedCriteria.length === 0 && (
              <tr><td colSpan={4} className="px-4 py-8 text-center text-slate-500">Chưa có tiêu chí nào.</td></tr>
            )}
            {displayedCriteria.map((crit) => {
              const isExpanded = expandedId === crit.id;
              return (
                <tr key={crit.id} className="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors">
                  <td className="px-4 py-3 text-slate-500 font-mono text-xs">{crit.id}</td>
                  <td className="px-4 py-3 text-white font-medium whitespace-nowrap">{crit.criteria_name}</td>
                  <td className="px-4 py-3 text-slate-400 max-w-md">
                    <button
                      onClick={() => setExpandedId(isExpanded ? null : crit.id)}
                      className="text-left w-full"
                    >
                      <p className={`text-xs leading-relaxed ${isExpanded ? '' : 'line-clamp-2'}`}>
                        {crit.prompt_instruction}
                      </p>
                      <span className="text-xs text-orange-400 mt-1 inline-block">{isExpanded ? '▲ Thu gọn' : '▼ Xem thêm'}</span>
                    </button>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-2">
                      <button onClick={() => openEdit(crit)} className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-700 transition-colors" title="Sửa">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" /><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" /></svg>
                      </button>
                      <button
                        onClick={() => handleDelete(crit.id)}
                        disabled={deletingId === crit.id}
                        className="p-1.5 rounded-lg text-slate-400 hover:text-red-400 hover:bg-red-950/40 transition-colors"
                        title="Xóa"
                      >
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3 6 5 6 21 6" /><path d="M19 6l-1 14H6L5 6" /><path d="M10 11v6M14 11v6" /><path d="M9 6V4h6v2" /></svg>
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination controls */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-3 px-1">
          <span className="text-xs text-slate-500">
            Trang {currentPage} / {totalPages} (tổng {criteria.length} mục)
          </span>
          <div className="flex items-center gap-1.5">
            <button
              onClick={handlePrevPage}
              disabled={currentPage === 1}
              className="px-2.5 py-1 text-xs font-medium text-slate-400 hover:text-white border border-slate-800 disabled:opacity-40 disabled:hover:text-slate-400 hover:bg-slate-800 rounded-lg transition-colors"
            >
              Trước
            </button>
            <button
              onClick={handleNextPage}
              disabled={currentPage === totalPages}
              className="px-2.5 py-1 text-xs font-medium text-slate-400 hover:text-white border border-slate-800 disabled:opacity-40 disabled:hover:text-slate-400 hover:bg-slate-800 rounded-lg transition-colors"
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
    </div>
  );
}
