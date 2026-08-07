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

function generateCategoryCode(name: string): string {
  return name
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/đ/g, 'd')
    .replace(/Đ/g, 'D')
    .toUpperCase()
    .replace(/[^A-Z0-9\s_]/g, '')
    .trim()
    .replace(/\s+/g, '_');
}

const emptyForm: CreateJobCategoryPayload = { code: '', name: '', parent_id: null };

export default function JobCategoryTable({ categories, onRefresh }: Props) {
  const [modalOpen, setModalOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<JobCategoryDto | null>(null);
  const [form, setForm] = useState<CreateJobCategoryPayload>(emptyForm);
  const [isCodeManual, setIsCodeManual] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const openCreate = () => {
    setEditTarget(null);
    setForm(emptyForm);
    setIsCodeManual(false);
    setModalOpen(true);
  };

  const openEdit = (cat: JobCategoryDto) => {
    setEditTarget(cat);
    setForm({ code: cat.code, name: cat.name, parent_id: cat.parent_id });
    setIsCodeManual(true);
    setModalOpen(true);
  };

  const handleSave = async () => {
    if (!form.code.trim()) { toast.error('Mã danh mục (code) không được để trống'); return; }
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
            <tr className="border-b border-slate-800 bg-white/[0.03]">
              <th className="min-w-[80px] px-6 py-4 text-left text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">ID</th>
              <th className="px-6 py-4 text-left text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Code</th>
              <th className="px-6 py-4 text-left text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Tên</th>
              <th className="px-6 py-4 text-left text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Danh mục cha</th>
              <th className="w-28 px-6 py-4 text-right text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Hành động</th>
            </tr>
          </thead>
          <tbody>
            {displayedCategories.length === 0 && (
              <tr><td colSpan={4} className="px-6 py-10 text-center text-slate-400">Chưa có danh mục nào.</td></tr>
            )}
             {displayedCategories.map((cat) => (
              <tr key={cat.id} className="border-b border-slate-800 transition-colors hover:bg-white/[0.03]">
                <td className="px-6 py-4 align-middle font-mono text-xs text-slate-500 whitespace-nowrap">{cat.id}</td>
                 <td className="px-6 py-4 align-middle font-mono text-xs text-teal-400 whitespace-nowrap">{cat.code}</td>
                <td className="px-6 py-4 align-middle text-sm text-slate-200 font-medium">{cat.name}</td>
                <td className="px-6 py-4 align-middle text-sm text-slate-400">{categories.find(c => c.id === cat.parent_id)?.name ?? <span className="italic text-slate-500">Root</span>}</td>
                <td className="px-6 py-4 align-middle">
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

      {/* Pagination controls inside card with top border and padded container */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between border-t border-white/6 px-6 py-5 bg-slate-950/20">
          <span className="text-xs text-slate-400 font-medium">
            Trang {currentPage} / {totalPages} (tổng {categories.length} mục)
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

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editTarget ? 'Sửa danh mục' : 'Thêm danh mục'}>
        <div className="space-y-4">
          {/* Category Name FIRST */}
          <div>
            <label className="block text-sm text-slate-400 mb-1.5">Tên danh mục <span className="text-red-400">*</span></label>
            <input
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500/30 transition-colors"
              value={form.name}
              onChange={(e) => {
                const newName = e.target.value;
                setForm((prev) => ({
                  ...prev,
                  name: newName,
                  code: isCodeManual ? prev.code : generateCategoryCode(newName),
                }));
              }}
              placeholder="VD: Backend Development"
            />
          </div>

          {/* Category Code SECOND with Auto-slug Hint */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="block text-sm text-slate-400">
                Mã danh mục (code) <span className="text-red-400">*</span>
              </label>
              {!isCodeManual && form.code && (
                <span className="text-[10px] font-semibold text-amber-400/90 bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 rounded">
                  ✨ Tự động tạo
                </span>
              )}
            </div>
            <input
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500/30 transition-colors font-mono uppercase"
              value={form.code}
              onChange={(e) => {
                setIsCodeManual(true);
                setForm({ ...form, code: e.target.value.toUpperCase().replace(/[^A-Z0-9_]/g, '') });
              }}
              placeholder="VD: BACKEND_DEVELOPMENT"
            />
            <p className="mt-1 text-[11px] text-slate-500 leading-normal">
              Mã dùng cho hệ thống Rule Engine. Tự động sinh từ Tên danh mục (chỉ gồm chữ in hoa, số và gạch dưới <code className="text-slate-400">_</code>).
            </p>
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
