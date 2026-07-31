'use client';

import { useMemo, useState } from 'react';
import { Folder, FileText, ChevronRight, Search, Plus, Filter } from 'lucide-react';
import {
  adminService,
  EvaluationCriteriaDto,
  CreateEvaluationCriteriaPayload,
  JobCategoryDto,
  CategoryCriteriaMappingDto,
} from '@/services/adminService';
import { toast } from './Toast';
import Modal from './Modal';
import RuleDashboardSection from './rule-dashboard/RuleDashboardSection';
import ActionIconButton from './rule-dashboard/ActionIconButton';

interface Props {
  criteria: EvaluationCriteriaDto[];
  categories?: JobCategoryDto[];
  mappings?: CategoryCriteriaMappingDto[];
  onRefresh: () => void;
}

interface CategoryTreeNodeData {
  category: JobCategoryDto;
  children: CategoryTreeNodeData[];
  criteriaList: EvaluationCriteriaDto[];
}

const emptyForm: CreateEvaluationCriteriaPayload = {
  name: '',
  category: null,
  question_type: null,
  prompt_instruction: '',
};

// ─── Level Badge Styling ──────────────────────────────────────────────────────
const LEVEL_STYLES: Record<string, { bg: string; text: string; border: string }> = {
  INTERN:   { bg: 'bg-slate-800/80',   text: 'text-slate-300',  border: 'border-slate-700/60' },
  FRESHER:  { bg: 'bg-sky-950/60',     text: 'text-sky-300',    border: 'border-sky-800/50'   },
  JUNIOR:   { bg: 'bg-teal-950/60',    text: 'text-teal-300',   border: 'border-teal-800/50'  },
  MID:      { bg: 'bg-violet-950/60',  text: 'text-violet-300', border: 'border-violet-800/50'},
  SENIOR:   { bg: 'bg-amber-950/60',   text: 'text-amber-300',  border: 'border-amber-800/50' },
  LEAD:     { bg: 'bg-rose-950/60',    text: 'text-rose-300',   border: 'border-rose-800/50'  },
  ALL:      { bg: 'bg-orange-950/60',  text: 'text-orange-300', border: 'border-orange-800/50'},
};

const LEVEL_ORDER = ['INTERN', 'FRESHER', 'JUNIOR', 'MID', 'SENIOR', 'LEAD', 'ALL'];

function LevelBadge({ level }: { level: string }) {
  const style = LEVEL_STYLES[level.toUpperCase()] ?? {
    bg: 'bg-slate-800/60',
    text: 'text-slate-400',
    border: 'border-slate-700/40',
  };
  return (
    <span
      className={`inline-flex items-center rounded-md border px-2 py-0.5 text-[10px] font-semibold tracking-wide ${style.bg} ${style.text} ${style.border}`}
    >
      {level}
    </span>
  );
}

function MappedLevelsBadges({ levels }: { levels?: string[] }) {
  if (!levels || levels.length === 0) {
    return <span className="text-[11px] italic text-slate-500">Chưa áp dụng</span>;
  }
  const sorted = [...levels].sort(
    (a, b) => LEVEL_ORDER.indexOf(a.toUpperCase()) - LEVEL_ORDER.indexOf(b.toUpperCase())
  );
  return (
    <div className="flex flex-wrap gap-1">
      {sorted.map((lvl) => (
        <LevelBadge key={lvl} level={lvl} />
      ))}
    </div>
  );
}

function formatCategoryLabel(text: string | null | undefined): string {
  if (!text) return '';
  return text
    .replace(/_/g, ' ')
    .toLowerCase()
    .split(' ')
    .filter(Boolean)
    .map((word) => {
      if (word === 'qa') return 'QA';
      if (word === 'js') return 'JS';
      if (word === 'id') return 'ID';
      if (word === 'cv') return 'CV';
      if (word === 'jd') return 'JD';
      if (word === 'nestjs') return 'NestJS';
      if (word === 'mongodb') return 'MongoDB';
      if (word === 'mysql') return 'MySQL';
      if (word === 'postgresql') return 'PostgreSQL';
      if (word === 'api') return 'API';
      return word.charAt(0).toUpperCase() + word.slice(1);
    })
    .join(' ');
}

// ─── Build Tree Helper ────────────────────────────────────────────────────────
function buildCategoryCriteriaTree(
  categories: JobCategoryDto[] = [],
  criteria: EvaluationCriteriaDto[] = [],
  mappings: CategoryCriteriaMappingDto[] = []
): CategoryTreeNodeData[] {
  const categoryNodes = new Map<number, CategoryTreeNodeData>();
  const criteriaById = new Map(criteria.map((item) => [item.id, item]));
  const assignedCriteriaIds = new Set<number>();

  categories.forEach((cat) => {
    categoryNodes.set(cat.id, {
      category: cat,
      children: [],
      criteriaList: [],
    });
  });

  const roots: CategoryTreeNodeData[] = [];

  categories.forEach((cat) => {
    const node = categoryNodes.get(cat.id);
    if (!node) return;

    if (cat.parent_id && categoryNodes.has(cat.parent_id)) {
      categoryNodes.get(cat.parent_id)!.children.push(node);
    } else {
      roots.push(node);
    }
  });

  // 1. Group criteria by CategoryCriteriaMapping
  mappings.forEach((m) => {
    const catNode = categoryNodes.get(m.category_id);
    const crit = criteriaById.get(m.criteria_id);
    if (catNode && crit) {
      if (!catNode.criteriaList.some((existing) => existing.id === crit.id)) {
        catNode.criteriaList.push(crit);
      }
      assignedCriteriaIds.add(crit.id);
    }
  });

  // 2. Group unassigned criteria by criteria.category field string matching
  criteria.forEach((crit) => {
    if (assignedCriteriaIds.has(crit.id)) return;
    if (!crit.category) return;

    const catStr = crit.category.toLowerCase().trim();
    for (const catNode of Array.from(categoryNodes.values())) {
      const codeMatch = catNode.category.code.toLowerCase().trim() === catStr;
      const nameMatch = catNode.category.name.toLowerCase().trim() === catStr;
      if (codeMatch || nameMatch) {
        if (!catNode.criteriaList.some((existing) => existing.id === crit.id)) {
          catNode.criteriaList.push(crit);
        }
        assignedCriteriaIds.add(crit.id);
        break;
      }
    }
  });

  // 3. Fallback: group remaining unassigned criteria under a synthetic root
  const unassigned = criteria.filter((crit) => !assignedCriteriaIds.has(crit.id));
  if (unassigned.length > 0) {
    roots.push({
      category: { id: -1, code: 'UNASSIGNED', name: 'Chưa phân loại', parent_id: null },
      children: [],
      criteriaList: unassigned.sort((a, b) => a.name.localeCompare(b.name)),
    });
  }

  // 4. Recursive sort
  const sortTree = (nodes: CategoryTreeNodeData[]) => {
    nodes.sort((a, b) => formatCategoryLabel(a.category.name).localeCompare(formatCategoryLabel(b.category.name)));
    nodes.forEach((node) => {
      node.criteriaList.sort((a, b) => a.name.localeCompare(b.name));
      sortTree(node.children);
    });
  };

  sortTree(roots);
  return roots;
}

function getTotalCriteriaInNode(node: CategoryTreeNodeData): number {
  let count = node.criteriaList.length;
  for (const child of node.children) {
    count += getTotalCriteriaInNode(child);
  }
  return count;
}

// ─── Sleek Tree Node Component ────────────────────────────────────────────────
function CategoryCriteriaTreeNode({
  node,
  depth,
  expandedIds,
  onToggle,
  onEditCriteria,
  onDeleteCriteria,
  onViewPrompt,
  deletingId,
  showEmptyCategories,
}: {
  node: CategoryTreeNodeData;
  depth: number;
  expandedIds: Set<number>;
  onToggle: (categoryId: number) => void;
  onEditCriteria: (crit: EvaluationCriteriaDto) => void;
  onDeleteCriteria: (id: number) => void;
  onViewPrompt: (crit: EvaluationCriteriaDto) => void;
  deletingId: number | null;
  showEmptyCategories: boolean;
}) {
  const isExpanded = expandedIds.has(node.category.id);
  const totalCriteriaCount = useMemo(() => getTotalCriteriaInNode(node), [node]);

  // Filter children categories if hide empty is active
  const visibleChildrenCategories = useMemo(() => {
    if (showEmptyCategories) return node.children;
    return node.children.filter((child) => getTotalCriteriaInNode(child) > 0);
  }, [node.children, showEmptyCategories]);

  // Don't render empty category node if hide empty is active
  if (!showEmptyCategories && totalCriteriaCount === 0) {
    return null;
  }

  const isTopLevel = depth === 0;

  const headerBgClass = isTopLevel
    ? 'border border-slate-800 bg-slate-900/80 hover:bg-slate-800/60 px-4 py-3.5 rounded-xl'
    : 'border-b border-slate-800/60 hover:bg-slate-800/40 px-3 py-2.5 rounded-lg';

  return (
    <div className="space-y-1">
      {/* Category Header Row */}
      <div
        role="button"
        tabIndex={0}
        onClick={() => onToggle(node.category.id)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            onToggle(node.category.id);
          }
        }}
        className={`group flex items-center justify-between cursor-pointer select-none transition-all ${headerBgClass}`}
      >
        <div className="flex items-center gap-2.5 min-w-0">
          <ChevronRight
            size={16}
            className={`text-slate-400 shrink-0 transition-transform duration-200 ${
              isExpanded ? 'rotate-90 text-orange-400' : ''
            }`}
          />
          <Folder
            size={isTopLevel ? 18 : 16}
            className={isTopLevel ? 'text-orange-400 shrink-0' : 'text-slate-400 shrink-0'}
          />
          <span
            className={`truncate text-sm font-semibold tracking-wide ${
              isTopLevel ? 'text-white font-bold' : 'text-slate-200'
            }`}
          >
            {formatCategoryLabel(node.category.name)}
          </span>
          <span className="rounded-full bg-slate-800 border border-slate-700/60 px-2 py-0.5 text-[10px] font-semibold text-teal-300">
            {totalCriteriaCount} tiêu chí
          </span>
        </div>

        {visibleChildrenCategories.length > 0 && (
          <span className="text-[11px] text-slate-500 font-mono">
            {visibleChildrenCategories.length} danh mục con
          </span>
        )}
      </div>

      {/* Expanded Content: Sub-categories and Criteria Items */}
      {isExpanded && (
        <div className="pl-4 sm:pl-6 space-y-2 border-l border-slate-800/80 my-1">
          {/* Sub-categories */}
          {visibleChildrenCategories.map((childNode) => (
            <CategoryCriteriaTreeNode
              key={childNode.category.id}
              node={childNode}
              depth={depth + 1}
              expandedIds={expandedIds}
              onToggle={onToggle}
              onEditCriteria={onEditCriteria}
              onDeleteCriteria={onDeleteCriteria}
              onViewPrompt={onViewPrompt}
              deletingId={deletingId}
              showEmptyCategories={showEmptyCategories}
            />
          ))}

          {/* Criteria Items inside this Category */}
          {node.criteriaList.length > 0 && (
            <div className="space-y-1 pt-1">
              {node.criteriaList.map((crit) => (
                <div
                  key={crit.id}
                  className="group flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3 rounded-lg border border-slate-800/60 bg-slate-950/40 hover:bg-slate-900/90 hover:border-slate-700 transition-all"
                >
                  {/* Left: Criteria Title & Prompt */}
                  <div className="flex items-start gap-2.5 min-w-0 flex-1">
                    <FileText size={15} className="text-teal-400 shrink-0 mt-0.5" />
                    <div className="min-w-0 flex-1 space-y-0.5">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-[11px] text-slate-500">#{crit.id}</span>
                        <h5 className="text-xs sm:text-sm font-semibold text-slate-100 truncate">
                          {crit.name}
                        </h5>
                      </div>
                      <p className="line-clamp-1 text-xs text-slate-400 font-mono leading-relaxed">
                        {crit.prompt_instruction}
                      </p>
                      <button
                        type="button"
                        onClick={() => onViewPrompt(crit)}
                        className="inline-flex items-center gap-1 text-[11px] font-semibold text-teal-400 hover:text-teal-300 transition-colors"
                      >
                        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                          <path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
                        </svg>
                        Xem Prompt
                      </button>
                    </div>
                  </div>

                  {/* Right: Badges & Actions */}
                  <div className="flex items-center justify-between sm:justify-end gap-3 shrink-0 pt-2 sm:pt-0 border-t sm:border-t-0 border-slate-800/40">
                    <MappedLevelsBadges levels={crit.mapped_levels} />
                    <div className="flex items-center gap-1 pl-2 border-l border-slate-800">
                      <ActionIconButton
                        label="Sửa"
                        onClick={() => onEditCriteria(crit)}
                        icon={<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" /><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" /></svg>}
                      />
                      <ActionIconButton
                        label="Xóa"
                        variant="danger"
                        onClick={() => onDeleteCriteria(crit.id)}
                        disabled={deletingId === crit.id}
                        icon={<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3 6 5 6 21 6" /><path d="M19 6l-1 14H6L5 6" /><path d="M10 11v6M14 11v6" /><path d="M9 6V4h6v2" /></svg>}
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────
export default function EvaluationCriteriaTable({ criteria, categories = [], mappings = [], onRefresh }: Props) {
  const [modalOpen, setModalOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<EvaluationCriteriaDto | null>(null);
  const [form, setForm] = useState<CreateEvaluationCriteriaPayload>(emptyForm);
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [viewCriteria, setViewCriteria] = useState<EvaluationCriteriaDto | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [showEmptyCategories, setShowEmptyCategories] = useState(false);

  // 1. Build full tree
  const treeRoots = useMemo(
    () => buildCategoryCriteriaTree(categories, criteria, mappings),
    [categories, criteria, mappings]
  );

  // Collect top-level category IDs only (or non-empty root category IDs) for initial default expand
  const rootCategoryIds = useMemo(() => {
    return treeRoots
      .filter((r) => getTotalCriteriaInNode(r) > 0)
      .map((r) => r.category.id);
  }, [treeRoots]);

  const allCategoryIds = useMemo(() => {
    const ids: number[] = [];
    const collect = (nodes: CategoryTreeNodeData[]) => {
      nodes.forEach((n) => {
        ids.push(n.category.id);
        collect(n.children);
      });
    };
    collect(treeRoots);
    return ids;
  }, [treeRoots]);

  // Expanded nodes state (defaults to expanding root categories that contain criteria)
  const [expandedIds, setExpandedIds] = useState<Set<number>>(() => new Set(rootCategoryIds));

  const handleToggleCategory = (catId: number) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(catId)) next.delete(catId);
      else next.add(catId);
      return next;
    });
  };

  const handleExpandAll = () => setExpandedIds(new Set(allCategoryIds));
  const handleCollapseAll = () => setExpandedIds(new Set());

  // Search Filter
  const filteredTreeRoots = useMemo(() => {
    if (!searchQuery.trim()) return treeRoots;
    const queryLower = searchQuery.toLowerCase().trim();

    const filterNode = (node: CategoryTreeNodeData): CategoryTreeNodeData | null => {
      const catMatches = formatCategoryLabel(node.category.name).toLowerCase().includes(queryLower);
      const matchingCriteria = node.criteriaList.filter(
        (c) =>
          c.name.toLowerCase().includes(queryLower) ||
          c.prompt_instruction?.toLowerCase().includes(queryLower) ||
          c.mapped_levels?.some((lvl) => lvl.toLowerCase().includes(queryLower))
      );

      const matchingChildren = node.children
        .map(filterNode)
        .filter((c): c is CategoryTreeNodeData => c !== null);

      if (catMatches || matchingCriteria.length > 0 || matchingChildren.length > 0) {
        return {
          ...node,
          children: matchingChildren,
          criteriaList: catMatches ? node.criteriaList : matchingCriteria,
        };
      }
      return null;
    };

    return treeRoots.map(filterNode).filter((n): n is CategoryTreeNodeData => n !== null);
  }, [treeRoots, searchQuery]);

  const openCreate = () => {
    setEditTarget(null);
    setForm(emptyForm);
    setModalOpen(true);
  };

  const openEdit = (crit: EvaluationCriteriaDto) => {
    setEditTarget(crit);
    setForm({
      name: crit.name,
      category: crit.category,
      question_type: crit.question_type,
      prompt_instruction: crit.prompt_instruction,
    });
    setModalOpen(true);
  };

  const handleSave = async () => {
    if (!form.name.trim()) {
      toast.error('Tên tiêu chí không được để trống');
      return;
    }
    if (!form.prompt_instruction?.trim()) {
      toast.error('Prompt instruction không được để trống');
      return;
    }
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
      description="Các tiêu chí đánh giá năng lực được sắp xếp gọn gàng theo cây danh mục. Click vào danh mục để xem các tiêu chí bên trong."
      action={
        <button
          onClick={openCreate}
          className="inline-flex items-center gap-2 rounded-xl border border-orange-500/25 bg-orange-500/10 px-3.5 py-2 text-sm font-semibold text-orange-300 transition-colors hover:border-orange-500/50 hover:bg-orange-500/15 hover:text-white"
        >
          <Plus size={15} />
          Thêm tiêu chí
        </button>
      }
    >
      {/* Control Toolbar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4 border-b border-slate-800 bg-slate-950/60 p-4">
        {/* Search */}
        <div className="relative flex-1 max-w-md">
          <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Tìm kiếm tiêu chí, prompt, cấp bậc..."
            className="w-full rounded-xl border border-slate-800 bg-slate-900 pl-9 pr-4 py-2 text-xs text-white placeholder-slate-500 focus:border-orange-500/60 focus:outline-none focus:ring-1 focus:ring-orange-500/30 transition-all"
          />
        </div>

        {/* Filter Toggle & Expand Controls */}
        <div className="flex flex-wrap items-center gap-3 justify-end">
          <label className="inline-flex items-center gap-2 text-xs text-slate-400 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={showEmptyCategories}
              onChange={(e) => setShowEmptyCategories(e.target.checked)}
              className="rounded border-slate-700 bg-slate-900 text-orange-500 focus:ring-orange-500/30"
            />
            <span>Hiện danh mục trống (0 tiêu chí)</span>
          </label>

          <div className="h-4 w-px bg-slate-800 hidden sm:block" />

          <button
            onClick={handleExpandAll}
            className="rounded-lg border border-slate-800 bg-slate-900 px-3 py-1.5 text-xs font-semibold text-slate-300 hover:border-slate-700 hover:text-white transition-all"
          >
            Mở tất cả
          </button>
          <button
            onClick={handleCollapseAll}
            className="rounded-lg border border-slate-800 bg-slate-900 px-3 py-1.5 text-xs font-semibold text-slate-300 hover:border-slate-700 hover:text-white transition-all"
          >
            Thu gọn tất cả
          </button>
        </div>
      </div>

      {/* Tree Content */}
      <div className="p-4 space-y-3 bg-slate-950/20 min-h-[300px]">
        {filteredTreeRoots.length === 0 ? (
          <div className="py-16 text-center text-slate-400 space-y-2">
            <p className="text-sm font-medium">Không tìm thấy tiêu chí đánh giá nào.</p>
            <p className="text-xs text-slate-500">Thử thay đổi từ khóa tìm kiếm hoặc bấm &quot;Thêm tiêu chí&quot;.</p>
          </div>
        ) : (
          filteredTreeRoots.map((rootNode) => (
            <CategoryCriteriaTreeNode
              key={rootNode.category.id}
              node={rootNode}
              depth={0}
              expandedIds={expandedIds}
              onToggle={handleToggleCategory}
              onEditCriteria={openEdit}
              onDeleteCriteria={handleDelete}
              onViewPrompt={setViewCriteria}
              deletingId={deletingId}
              showEmptyCategories={showEmptyCategories}
            />
          ))
        )}
      </div>

      {/* Modal Create / Edit */}
      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editTarget ? 'Sửa tiêu chí' : 'Thêm tiêu chí'} size="lg">
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-slate-400 mb-1.5">
              Tên tiêu chí <span className="text-red-400">*</span>
            </label>
            <input
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500/30 transition-colors"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="VD: Object-Oriented Programming (OOP)"
            />
          </div>
          <div>
            <label className="block text-sm text-slate-400 mb-1.5">
              Prompt Instruction <span className="text-red-400">*</span>
              <span className="text-slate-500 ml-2 text-xs">(được tiêm trực tiếp vào LLM)</span>
            </label>
            <textarea
              rows={10}
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm font-mono focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500/30 transition-colors resize-y"
              value={form.prompt_instruction ?? ''}
              onChange={(e) => setForm({ ...form, prompt_instruction: e.target.value })}
              placeholder={'Evaluate understanding of OOP principles (Encapsulation, Inheritance, Polymorphism, Abstraction)...'}
            />
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button
              onClick={() => setModalOpen(false)}
              className="px-4 py-2 text-sm text-slate-400 hover:text-white border border-slate-700 hover:border-slate-600 rounded-lg transition-colors"
            >
              Hủy
            </button>
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

      {/* Modal Detailed Prompt View */}
      {viewCriteria && (
        <Modal
          open={Boolean(viewCriteria)}
          onClose={() => setViewCriteria(null)}
          title={`Chi tiết Prompt Instruction - ${viewCriteria.name}`}
          size="lg"
        >
          <div className="space-y-4">
            <div className="rounded-xl border border-slate-700/60 bg-slate-900/50 p-4">
              <h4 className="text-xs uppercase tracking-wider text-slate-500 font-semibold mb-1">Tên tiêu chí</h4>
              <p className="text-sm font-medium text-white">{viewCriteria.name}</p>
            </div>
            {viewCriteria.mapped_levels && viewCriteria.mapped_levels.length > 0 && (
              <div className="rounded-xl border border-slate-700/60 bg-slate-900/50 p-4">
                <h4 className="text-xs uppercase tracking-wider text-slate-500 font-semibold mb-2">Áp dụng cho cấp bậc</h4>
                <MappedLevelsBadges levels={viewCriteria.mapped_levels} />
              </div>
            )}
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
