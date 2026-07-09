'use client';

import { useState } from 'react';
import {
  adminService,
  CategoryCriteriaMappingDto,
  CreateMappingPayload,
  JobCategoryDto,
  EvaluationCriteriaDto,
} from '@/services/adminService';
import { toast } from './Toast';
import Modal from './Modal';

interface Props {
  mappings: CategoryCriteriaMappingDto[];
  categories: JobCategoryDto[];
  criteria: EvaluationCriteriaDto[];
  onRefresh: () => void;
}

const SENIORITY_LEVELS = ['ALL', 'INTERN', 'FRESHER', 'JUNIOR', 'MID', 'SENIOR', 'LEAD'];

const emptyForm: CreateMappingPayload = {
  job_category_id: 0,
  criteria_id: 0,
  seniority_level: 'ALL',
  weight_percentage: 10,
};

export default function WeightMappingTable({ mappings, categories, criteria, onRefresh }: Props) {
  const [modalOpen, setModalOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<CategoryCriteriaMappingDto | null>(null);
  const [form, setForm] = useState<CreateMappingPayload>(emptyForm);
  const [saving, setSaving] = useState(false);

  const openCreate = () => {
    setEditTarget(null);
    setForm({ ...emptyForm, job_category_id: categories[0]?.id ?? 0, criteria_id: criteria[0]?.id ?? 0 });
    setModalOpen(true);
  };

  const openEdit = (m: CategoryCriteriaMappingDto) => {
    setEditTarget(m);
    setForm({
      job_category_id: m.job_category_id,
      criteria_id: m.criteria_id,
      seniority_level: m.seniority_level,
      weight_percentage: m.weight_percentage,
    });
    setModalOpen(true);
  };

  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;
  const totalPages = Math.ceil(mappings.length / itemsPerPage) || 1;
  const displayedMappings = mappings.slice(
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
    if (form.job_category_id === 0 || form.criteria_id === 0) { toast.error('Vui lòng chọn danh mục và tiêu chí.'); return; }
    setSaving(true);
    try {
      if (editTarget) {
        await adminService.updateCategoryMapping(
          editTarget.job_category_id, editTarget.criteria_id, editTarget.seniority_level,
          { weight_percentage: form.weight_percentage }
        );
        toast.success('Cập nhật trọng số thành công!');
      } else {
        await adminService.createCategoryMapping(form);
        toast.success('Tạo mapping thành công!');
      }
      setModalOpen(false);
      safeOnRefresh();
    } catch {
      toast.error('Có lỗi xảy ra. Vui lòng thử lại.');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (m: CategoryCriteriaMappingDto) => {
    if (!confirm('Xóa mapping này?')) return;
    try {
      await adminService.deleteCategoryMapping(m.job_category_id, m.criteria_id, m.seniority_level);
      toast.success('Đã xóa mapping.');
      safeOnRefresh();
    } catch {
      toast.error('Không thể xóa mapping này.');
    }
  };

  const weightColor = (w: number) => {
    if (w >= 20) return 'text-orange-400';
    if (w >= 10) return 'text-yellow-400';
    return 'text-slate-400';
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-300">Trọng số tiêu chí ({mappings.length} mapping)</h3>
        <button
          onClick={openCreate}
          disabled={categories.length === 0 || criteria.length === 0}
          className="flex items-center gap-2 px-3 py-1.5 bg-orange-600 hover:bg-orange-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-colors"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M12 5v14M5 12h14" /></svg>
          Thêm
        </button>
      </div>

      <div className="overflow-x-auto rounded-xl border border-slate-800">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-800 bg-slate-800/50">
              <th className="text-left px-4 py-3 text-slate-400 font-medium">Danh mục</th>
              <th className="text-left px-4 py-3 text-slate-400 font-medium">Tiêu chí</th>
              <th className="text-left px-4 py-3 text-slate-400 font-medium">Cấp bậc</th>
              <th className="text-right px-4 py-3 text-slate-400 font-medium">Trọng số (%)</th>
              <th className="text-right px-4 py-3 text-slate-400 font-medium">Hành động</th>
            </tr>
          </thead>
          <tbody>
            {displayedMappings.length === 0 && (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-slate-500">Chưa có mapping nào.</td></tr>
            )}
            {displayedMappings.map((m, i) => (
              <tr key={i} className="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors">
                <td className="px-4 py-3 text-white">{m.job_category_name ?? m.job_category_id}</td>
                <td className="px-4 py-3 text-slate-300">{m.criteria_name ?? m.criteria_id}</td>
                <td className="px-4 py-3">
                  <span className="text-xs px-2 py-0.5 rounded-full bg-slate-700 text-slate-300">{m.seniority_level}</span>
                </td>
                <td className="px-4 py-3 text-right">
                  <span className={`font-bold tabular-nums ${weightColor(m.weight_percentage)}`}>
                    {m.weight_percentage}%
                  </span>
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center justify-end gap-2">
                    <button onClick={() => openEdit(m)} className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-700 transition-colors" title="Sửa">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" /><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" /></svg>
                    </button>
                    <button onClick={() => handleDelete(m)} className="p-1.5 rounded-lg text-slate-400 hover:text-red-400 hover:bg-red-950/40 transition-colors" title="Xóa">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3 6 5 6 21 6" /><path d="M19 6l-1 14H6L5 6" /><path d="M10 11v6M14 11v6" /><path d="M9 6V4h6v2" /></svg>
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination controls */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-3 px-1">
          <span className="text-xs text-slate-500">
            Trang {currentPage} / {totalPages} (tổng {mappings.length} mục)
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

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editTarget ? 'Sửa trọng số' : 'Thêm mapping'}>
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-slate-400 mb-1.5">Danh mục công việc <span className="text-red-400">*</span></label>
            <select
              disabled={!!editTarget}
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-orange-500 disabled:opacity-50 disabled:cursor-not-allowed"
              value={form.job_category_id}
              onChange={(e) => setForm({ ...form, job_category_id: Number(e.target.value) })}
            >
              {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm text-slate-400 mb-1.5">Tiêu chí <span className="text-red-400">*</span></label>
            <select
              disabled={!!editTarget}
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-orange-500 disabled:opacity-50 disabled:cursor-not-allowed"
              value={form.criteria_id}
              onChange={(e) => setForm({ ...form, criteria_id: Number(e.target.value) })}
            >
              {criteria.map((c) => <option key={c.id} value={c.id}>{c.criteria_name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm text-slate-400 mb-1.5">Cấp bậc <span className="text-red-400">*</span></label>
            <select
              disabled={!!editTarget}
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-orange-500 disabled:opacity-50 disabled:cursor-not-allowed"
              value={form.seniority_level}
              onChange={(e) => setForm({ ...form, seniority_level: e.target.value })}
            >
              {SENIORITY_LEVELS.map((l) => <option key={l} value={l}>{l}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm text-slate-400 mb-1.5">Trọng số (%) <span className="text-red-400">*</span></label>
            <input
              type="number"
              min={1} max={100} step={1}
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500/30 tabular-nums"
              value={form.weight_percentage}
              onChange={(e) => setForm({ ...form, weight_percentage: Number(e.target.value) })}
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
