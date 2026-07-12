'use client';

import { useState } from 'react';
import { adminService, JobCategoryDto, CreateJobCategoryPayload } from '@/services/adminService';
import { toast } from './Toast';
import Modal from './Modal';
import RuleDashboardSection from './rule-dashboard/RuleDashboardSection';
import ActionIconButton from './rule-dashboard/ActionIconButton';

interface Props {
  categories: JobCategoryDto[];
  onRefresh: () => void;
}

const emptyForm: CreateJobCategoryPayload = { name: '', parent_id: null };

export default function JobCategoryTable({ categories, onRefresh }: Props) {
  const [modalOpen, setModalOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<JobCategoryDto | null>(null);
  const [form, setForm] = useState<CreateJobCategoryPayload>(emptyForm);
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const openCreate = () => {
    setEditTarget(null);
    setForm(emptyForm);
    setModalOpen(true);
  };

  const openEdit = (cat: JobCategoryDto) => {
    setEditTarget(cat);
    setForm({ name: cat.name, parent_id: cat.parent_id });
    setModalOpen(true);
  };

  const handleSave = async () => {
    if (!form.name.trim()) { toast.error('Tên danh mục không được để trống'); return; }
    setSaving(true);
    try {
      if (editTarget) {
        await adminService.updateJobCategory(editTarget.id, form);
        toast.success('Cập nhật danh mục thành công!');
      } else {
        await adminService.createJobCategory(form);
        toast.success('Tạo danh mục thành công!');
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
    if (!confirm('Xóa danh mục này? Các mapping liên quan sẽ bị xóa theo.')) return;
    setDeletingId(id);
    try {
      await adminService.deleteJobCategory(id);
      toast.success('Đã xóa danh mục.');
      safeOnRefresh();
    } catch {
      toast.error('Không thể xóa danh mục này.');
    } finally {
      setDeletingId(null);
    }
  };

  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;
  const totalPages = Math.ceil(categories.length / itemsPerPage) || 1;
  const displayedCategories = categories.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  );

  const handlePrevPage = () => {
    setCurrentPage((p) => Math.max(1, p - 1));
  };

  const handleNextPage = () => {
    setCurrentPage((p) => Math.min(totalPages, p + 1));
  };

  // Reset page when category list length changes
  const safeOnRefresh = () => {
    setCurrentPage(1);
    onRefresh();
  };

  return (
    <RuleDashboardSection
      title="Danh mục công việc"
      count={categories.length}
      countLabel="mục"
      action={(
        <button
          onClick={openCreate}
          className="inline-flex items-center gap-2 rounded-xl border border-amber-400/25 bg-amber-400/10 px-3.5 py-2 text-sm font-medium text-amber-200 transition-colors hover:border-amber-400/50 hover:bg-amber-400/15 hover:text-white"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M12 5v14M5 12h14" /></svg>
          Thêm
        </button>
      )}
    >
      <div className="overflow-x-auto border-t border-white/6 bg-slate-950/35">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-700/70 bg-white/[0.03]">
              <th className="w-20 px-5 py-4 text-left text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">ID</th>
              <th className="px-5 py-4 text-left text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Tên</th>
              <th className="px-5 py-4 text-left text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Danh mục cha</th>
              <th className="w-28 px-5 py-4 text-right text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Hành động</th>
            </tr>
          </thead>
          <tbody>
            {displayedCategories.length === 0 && (
              <tr><td colSpan={4} className="px-5 py-10 text-center text-slate-500">Chưa có danh mục nào.</td></tr>
            )}
            {displayedCategories.map((cat) => (
              <tr key={cat.id} className="border-b border-slate-700/60 transition-colors hover:bg-white/[0.03]">
                <td className="px-5 py-4 align-middle font-mono text-xs tabular-nums text-slate-500">{cat.id}</td>
                <td className="px-5 py-4 align-middle font-medium text-slate-100">{cat.name}</td>
                <td className="px-5 py-4 align-middle text-slate-400">{cat.parent_name ?? <span className="italic text-slate-600">Root</span>}</td>
                <td className="px-5 py-4 align-middle">
                  <div className="flex items-center justify-end gap-2">
                    <ActionIconButton
                      label="Sửa danh mục"
                      variant="neutral"
                      onClick={() => openEdit(cat)}
                      icon={(
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" /><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" /></svg>
                      )}
                    />
                    <ActionIconButton
                      label="Xóa danh mục"
                      variant="danger"
                      onClick={() => handleDelete(cat.id)}
                      disabled={deletingId === cat.id}
                      icon={(
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3 6 5 6 21 6" /><path d="M19 6l-1 14H6L5 6" /><path d="M10 11v6M14 11v6" /><path d="M9 6V4h6v2" /></svg>
                      )}
                    />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination controls */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between px-1 pt-4">
          <span className="text-xs text-slate-500">
            Trang {currentPage} / {totalPages} (tổng {categories.length} mục)
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={handlePrevPage}
              disabled={currentPage === 1}
              className="rounded-lg border border-slate-700/80 bg-white/[0.02] px-3 py-1.5 text-xs font-medium text-slate-400 transition-colors hover:border-slate-500 hover:bg-white/[0.05] hover:text-white disabled:opacity-40 disabled:hover:border-slate-700/80 disabled:hover:bg-white/[0.02] disabled:hover:text-slate-400"
            >
              Trước
            </button>
            <button
              onClick={handleNextPage}
              disabled={currentPage === totalPages}
              className="rounded-lg border border-slate-700/80 bg-white/[0.02] px-3 py-1.5 text-xs font-medium text-slate-400 transition-colors hover:border-slate-500 hover:bg-white/[0.05] hover:text-white disabled:opacity-40 disabled:hover:border-slate-700/80 disabled:hover:bg-white/[0.02] disabled:hover:text-slate-400"
            >
              Sau
            </button>
          </div>
        </div>
      )}

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editTarget ? 'Sửa danh mục' : 'Thêm danh mục'}>
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-slate-400 mb-1.5">Tên danh mục <span className="text-red-400">*</span></label>
            <input
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500/30 transition-colors"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="VD: BACKEND"
            />
          </div>
          <div>
            <label className="block text-sm text-slate-400 mb-1.5">Danh mục cha</label>
            <select
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-orange-500 transition-colors"
              value={form.parent_id ?? ''}
              onChange={(e) => setForm({ ...form, parent_id: e.target.value ? Number(e.target.value) : null })}
            >
              <option value="">— Root (không có cha) —</option>
              {categories.filter((c) => c.id !== editTarget?.id).map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
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
    </RuleDashboardSection>
  );
}
