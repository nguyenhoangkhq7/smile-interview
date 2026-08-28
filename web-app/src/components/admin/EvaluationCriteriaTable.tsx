'use client';

import { useMemo, useState } from 'react';
import { Folder, FileText, ChevronRight, Search, Plus, Info } from 'lucide-react';
import {
  adminService,
  EvaluationCriteriaDto,
  CreateEvaluationCriteriaPayload,
  JobCategoryDto,
  CreateJobCategoryPayload,
  CategoryCriteriaMappingDto,
} from '@/services/adminService';
import { toast } from './Toast';
import Modal from './Modal';
import RuleDashboardSection from './rule-dashboard/RuleDashboardSection';
import ActionIconButton from './rule-dashboard/ActionIconButton';
import TreeInsertorButton from './TreeInsertorButton';

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

const emptyCriteriaForm: CreateEvaluationCriteriaPayload = {
  name: '',
  category: null,
  question_type: null,
  prompt_instruction: '',
};

const emptyCategoryForm: CreateJobCategoryPayload = {
  code: '',
  name: '',
  parent_id: null,
};

// ─── Level Badge Styling ──────────────────────────────────────────────────────
const LEVEL_STYLES: Record<string, { bg: string; text: string; border: string }> = {
  INTERN: { bg: 'bg-slate-800/80', text: 'text-slate-300', border: 'border-slate-700/60' },
  FRESHER: { bg: 'bg-sky-950/60', text: 'text-sky-300', border: 'border-sky-800/50' },
  JUNIOR: { bg: 'bg-teal-950/60', text: 'text-teal-300', border: 'border-teal-800/50' },
  MID: { bg: 'bg-violet-950/60', text: 'text-violet-300', border: 'border-violet-800/50' },
  SENIOR: { bg: 'bg-amber-950/60', text: 'text-amber-300', border: 'border-amber-800/50' },
  LEAD: { bg: 'bg-rose-950/60', text: 'text-rose-300', border: 'border-rose-800/50' },
  ALL: { bg: 'bg-orange-950/60', text: 'text-orange-300', border: 'border-orange-800/50' },
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

export function generateCategoryCode(name: string): string {
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

// ─── Build ancestry path for a category ───────────────────────────────────────
function buildAncestorPath(
  categoryId: number,
  allCategories: JobCategoryDto[]
): JobCategoryDto[] {
  const byId = new Map(allCategories.map((c) => [c.id, c]));
  const path: JobCategoryDto[] = [];
  let current = byId.get(categoryId);
  while (current) {
    path.unshift(current);
    current = current.parent_id ? byId.get(current.parent_id) : undefined;
  }
  return path;
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

// ─── Ancestor criteria resolver helper ──────────────────────────────────────
function getInheritedCriteriaForCategory(
  category: JobCategoryDto,
  allCategories: JobCategoryDto[],
  allCriteria: EvaluationCriteriaDto[],
  allMappings: CategoryCriteriaMappingDto[]
): Array<{ ancestor: JobCategoryDto; criteriaList: EvaluationCriteriaDto[] }> {
  const fullPath = buildAncestorPath(category.id, allCategories);
  // Exclude current category itself to keep strictly ancestors
  const ancestors = fullPath.slice(0, fullPath.length - 1);
  if (ancestors.length === 0) return [];

  const criteriaById = new Map(allCriteria.map((c) => [c.id, c]));
  const result: Array<{ ancestor: JobCategoryDto; criteriaList: EvaluationCriteriaDto[] }> = [];

  ancestors.forEach((ancestor) => {
    const ancestorCriteriaSet = new Set<number>();
    const ancestorCriteriaList: EvaluationCriteriaDto[] = [];

    // 1. Match via CategoryCriteriaMapping
    allMappings.forEach((m) => {
      if (m.category_id === ancestor.id) {
        const crit = criteriaById.get(m.criteria_id);
        if (crit && !ancestorCriteriaSet.has(crit.id)) {
          ancestorCriteriaSet.add(crit.id);
          ancestorCriteriaList.push(crit);
        }
      }
    });

    // 2. Direct string category match fallback
    allCriteria.forEach((crit) => {
      if (ancestorCriteriaSet.has(crit.id)) return;
      if (!crit.category) return;
      const catStr = crit.category.toLowerCase().trim();
      if (
        catStr === ancestor.code.toLowerCase().trim() ||
        catStr === ancestor.name.toLowerCase().trim()
      ) {
        ancestorCriteriaSet.add(crit.id);
        ancestorCriteriaList.push(crit);
      }
    });

    if (ancestorCriteriaList.length > 0) {
      result.push({
        ancestor,
        criteriaList: ancestorCriteriaList.sort((a, b) => a.name.localeCompare(b.name)),
      });
    }
  });

  return result;
}

// ─── Flatten all criteria within node & all descendants ──────────────────────
interface CategoryCriteriaFlatGroup {
  category: JobCategoryDto;
  isDirect: boolean;
  depth: number;
  criteriaList: EvaluationCriteriaDto[];
}

function flattenCategoryCriteriaGroups(
  rootNode: CategoryTreeNodeData,
  currentDepth = 0
): CategoryCriteriaFlatGroup[] {
  const groups: CategoryCriteriaFlatGroup[] = [];

  if (rootNode.criteriaList.length > 0) {
    groups.push({
      category: rootNode.category,
      isDirect: currentDepth === 0,
      depth: currentDepth,
      criteriaList: rootNode.criteriaList,
    });
  }

  rootNode.children.forEach((child) => {
    groups.push(...flattenCategoryCriteriaGroups(child, currentDepth + 1));
  });

  return groups;
}

// ─── Modal: All Criteria of a Category (Direct + All Sub-Categories) ─────────
interface CategoryAllCriteriaModalProps {
  node: CategoryTreeNodeData | null;
  allCategories: JobCategoryDto[];
  onClose: () => void;
  onViewPrompt: (crit: EvaluationCriteriaDto) => void;
  onEditCriteria: (crit: EvaluationCriteriaDto) => void;
  onDeleteCriteria: (id: number) => void;
  deletingId: number | null;
}

function CategoryAllCriteriaModal({
  node,
  allCategories,
  onClose,
  onViewPrompt,
  onEditCriteria,
  onDeleteCriteria,
  deletingId,
}: CategoryAllCriteriaModalProps) {
  const [search, setSearch] = useState('');

  const groups = useMemo(() => {
    if (!node) return [];
    return flattenCategoryCriteriaGroups(node);
  }, [node]);

  const totalCount = useMemo(() => {
    return groups.reduce((acc, g) => acc + g.criteriaList.length, 0);
  }, [groups]);

  const filteredGroups = useMemo(() => {
    if (!search.trim()) return groups;
    const query = search.toLowerCase().trim();

    return groups
      .map((g) => {
        const catMatches = formatCategoryLabel(g.category.name).toLowerCase().includes(query);
        const matchingCriteria = g.criteriaList.filter(
          (c) =>
            c.name.toLowerCase().includes(query) ||
            c.prompt_instruction?.toLowerCase().includes(query) ||
            c.mapped_levels?.some((lvl) => lvl.toLowerCase().includes(query)) ||
            c.id.toString().includes(query)
        );

        if (catMatches) {
          return g;
        }
        if (matchingCriteria.length > 0) {
          return {
            ...g,
            criteriaList: matchingCriteria,
          };
        }
        return null;
      })
      .filter((g): g is CategoryCriteriaFlatGroup => g !== null);
  }, [groups, search]);

  const filteredTotalCount = useMemo(() => {
    return filteredGroups.reduce((acc, g) => acc + g.criteriaList.length, 0);
  }, [filteredGroups]);

  if (!node) return null;

  return (
    <Modal
      open={Boolean(node)}
      onClose={onClose}
      title={`Tất cả tiêu chí: ${formatCategoryLabel(node.category.name)}`}
      size="xl"
    >
      <div className="space-y-4">
        {/* Top Header Information */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-slate-900/60 p-3.5 rounded-xl border border-slate-800">
          <div className="flex items-center gap-2 flex-wrap min-w-0 flex-1">
            <span className="text-xs font-semibold text-slate-400 shrink-0">Danh mục:</span>
            <HierarchyBreadcrumb category={node.category} allCategories={allCategories} />
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <span className="rounded-full bg-teal-950/80 border border-teal-500/30 px-3 py-1 text-xs font-bold text-teal-300">
              Tổng cộng {totalCount} tiêu chí
            </span>
          </div>
        </div>

        {/* Quick Search */}
        <div className="relative">
          <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={`Tìm nhanh trong ${totalCount} tiêu chí của ${formatCategoryLabel(node.category.name)}...`}
            className="w-full rounded-xl border border-slate-800 bg-slate-950/70 pl-10 pr-16 py-2.5 text-xs text-slate-200 placeholder-slate-500 focus:border-teal-500 focus:bg-slate-900 focus:outline-none focus:ring-1 focus:ring-teal-500 transition-colors"
          />
          {search && (
            <button
              onClick={() => setSearch('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-slate-400 hover:text-white transition-colors"
            >
              Xóa tìm
            </button>
          )}
        </div>

        {/* List of Criteria grouped by category */}
        {filteredGroups.length === 0 ? (
          <div className="py-10 text-center text-slate-400 bg-slate-950/40 rounded-xl border border-slate-800">
            <p className="text-sm font-medium">Không tìm thấy tiêu chí nào phù hợp với từ khóa &quot;{search}&quot;.</p>
            <p className="text-xs text-slate-500 mt-1">Hãy thử tìm theo tên, ID, cấp bậc hoặc từ khóa prompt.</p>
          </div>
        ) : (
          <div className="space-y-4 max-h-[58vh] overflow-y-auto pr-1.5 scrollbar-thin">
            {filteredGroups.map((g) => (
              <div key={g.category.id} className="space-y-2 rounded-xl border border-slate-800/80 bg-slate-900/30 p-3.5">
                {/* Group Header */}
                <div className="flex items-center justify-between gap-2 border-b border-slate-800/80 pb-2">
                  <div className="flex items-center gap-2 flex-wrap">
                    <Folder size={15} className={g.isDirect ? 'text-teal-400' : 'text-orange-400'} />
                    <h4 className="text-xs font-bold uppercase tracking-wider text-slate-200">
                      {g.isDirect ? (
                        <span className="text-teal-300">Tiêu chí trực tiếp của {formatCategoryLabel(g.category.name)}</span>
                      ) : (
                        <span>Danh mục con: {formatCategoryLabel(g.category.name)}</span>
                      )}
                    </h4>
                    <span className="rounded-full bg-slate-800 border border-slate-700/60 px-2 py-0.2 text-[10px] font-semibold text-slate-300">
                      {g.criteriaList.length} tiêu chí
                    </span>
                  </div>
                  {g.isDirect && (
                    <span className="text-[10px] font-medium text-teal-400/90 bg-teal-950/60 border border-teal-800/40 px-2 py-0.5 rounded-full">
                      Dùng chung / Kế thừa
                    </span>
                  )}
                </div>

                {/* Criteria Cards */}
                <div className="space-y-2 pt-1">
                  {g.criteriaList.map((crit) => (
                    <div
                      key={crit.id}
                      className="group flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3 rounded-lg border border-slate-800/60 bg-slate-950/60 hover:bg-slate-900/90 hover:border-slate-700 transition-all"
                    >
                      {/* Left info */}
                      <div className="flex items-start gap-2.5 min-w-0 flex-1">
                        <FileText size={15} className="text-teal-400 shrink-0 mt-0.5" />
                        <div className="min-w-0 flex-1 space-y-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-mono text-[11px] text-slate-500">#{crit.id}</span>
                            <h5 className="text-xs sm:text-sm font-semibold text-slate-100">{crit.name}</h5>
                            {crit.question_type && (
                              <span className="rounded bg-slate-800/90 px-1.5 py-0.2 text-[10px] text-slate-400 border border-slate-700/50">
                                {crit.question_type}
                              </span>
                            )}
                          </div>
                          {crit.prompt_instruction && (
                            <p className="line-clamp-2 text-xs text-slate-400 font-mono leading-relaxed">
                              {crit.prompt_instruction}
                            </p>
                          )}
                          <button
                            type="button"
                            onClick={() => onViewPrompt(crit)}
                            className="inline-flex items-center gap-1 text-[11px] font-semibold text-teal-400 hover:text-teal-300 transition-colors"
                          >
                            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                              <path d="M15 3h6v6" /><path d="M10 14 21 3" /><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                            </svg>
                            Xem Full Prompt
                          </button>
                        </div>
                      </div>

                      {/* Right actions */}
                      <div className="flex items-center justify-between sm:justify-end gap-3 shrink-0 pt-2 sm:pt-0 border-t sm:border-t-0 border-slate-800/40">
                        <MappedLevelsBadges levels={crit.mapped_levels} />
                        <div className="flex items-center gap-1 pl-2 border-l border-slate-800">
                          <ActionIconButton
                            label="Sửa"
                            onClick={() => {
                              onEditCriteria(crit);
                            }}
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
              </div>
            ))}
          </div>
        )}

        <div className="flex items-center justify-between pt-2 border-t border-slate-800">
          <span className="text-xs text-slate-500">
            Đang hiển thị {filteredTotalCount} / {totalCount} tiêu chí
          </span>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-slate-700 bg-slate-800 px-4 py-2 text-sm text-slate-300 hover:text-white transition-colors"
          >
            Đóng
          </button>
        </div>
      </div>
    </Modal>
  );
}

// ─── YouTube Comment Thread Style Curved Connector Line ──────────────────────
function CurvedTreeConnector({ isLast }: { isLast: boolean }) {
  return (
    <div className="absolute -left-6 top-0 bottom-0 w-6 pointer-events-none select-none">
      {/* Continuous vertical line if NOT the last item */}
      {!isLast && (
        <div className="absolute left-[3px] top-0 bottom-0 w-[1.5px] bg-slate-700/60 group-hover/node:bg-orange-500/40 transition-colors" />
      )}
      {/* Curved YouTube comment elbow connector */}
      <svg
        className="absolute left-[3px] top-0 w-6 h-7 text-slate-700/70 group-hover/row:text-orange-400 group-hover/crit:text-teal-400 transition-colors"
        fill="none"
        viewBox="0 0 24 28"
      >
        <path
          d="M 0 0 V 14 C 0 21, 6 27, 24 27"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
      </svg>
    </div>
  );
}

// ─── Tree Node Component ──────────────────────────────────────────────────────
function CategoryCriteriaTreeNode({
  node,
  depth,
  expandedIds,
  onToggle,
  onEditCriteria,
  onDeleteCriteria,
  onViewPrompt,
  onAddCriteriaForCat,
  onAddSiblingCat,
  onViewInherited,
  onViewCategoryCriteria,
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
  onAddCriteriaForCat: (cat: JobCategoryDto) => void;
  onAddSiblingCat: (cat: JobCategoryDto) => void;
  onViewInherited: (cat: JobCategoryDto) => void;
  onViewCategoryCriteria: (node: CategoryTreeNodeData) => void;
  deletingId: number | null;
  showEmptyCategories: boolean;
}) {
  const isExpanded = expandedIds.has(node.category.id);
  const [isCriteriaSectionExpanded, setIsCriteriaSectionExpanded] = useState(true);
  const totalCriteriaCount = useMemo(() => getTotalCriteriaInNode(node), [node]);

  const visibleChildrenCategories = useMemo(() => {
    if (showEmptyCategories) return node.children;
    return node.children.filter((child) => getTotalCriteriaInNode(child) > 0);
  }, [node.children, showEmptyCategories]);

  if (!showEmptyCategories && totalCriteriaCount === 0) {
    return null;
  }

  const isTopLevel = depth === 0;

  // Synthetic "Unassigned" node never gets the insertor button
  const isVirtualNode = node.category.id === -1;

  const headerBgClass = isTopLevel
    ? 'border border-slate-800 bg-slate-900/80 hover:bg-slate-800/60 px-4 py-3.5 rounded-xl'
    : 'border-b border-slate-800/60 hover:bg-slate-800/40 px-3 py-2.5 rounded-lg';

  return (
    <div className="space-y-1">
      {/* Category Header Row Wrapper - Scoped relative group/node for hover isolation */}
      <div className="relative group/node">
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
          className={`group/row flex items-center justify-between cursor-pointer select-none transition-all ${headerBgClass}`}
        >
          {/* Left: chevron + icon + name + count button + Inherited button */}
          <div className="flex items-center gap-2.5 min-w-0 flex-1 flex-wrap">
            <ChevronRight
              size={16}
              className={`text-slate-400 shrink-0 transition-transform duration-200 ${isExpanded ? 'rotate-90 text-orange-400' : ''
                }`}
            />
            <Folder
              size={isTopLevel ? 18 : 16}
              className={isTopLevel ? 'text-orange-400 shrink-0' : 'text-slate-400 shrink-0'}
            />
            <span
              className={`truncate text-sm font-semibold tracking-wide ${isTopLevel ? 'text-white font-bold' : 'text-slate-200'
                }`}
            >
              {formatCategoryLabel(node.category.name)}
            </span>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onViewCategoryCriteria(node);
              }}
              title={`Nhấn để xem toàn bộ ${totalCriteriaCount} tiêu chí của ${formatCategoryLabel(node.category.name)}`}
              className="inline-flex items-center gap-1 rounded-full bg-slate-800/90 hover:bg-teal-950/80 border border-slate-700/70 hover:border-teal-500/60 px-2.5 py-0.5 text-[10px] font-semibold text-teal-300 hover:text-teal-200 transition-all cursor-pointer select-none group/badge shadow-sm hover:shadow-[0_0_8px_rgba(20,184,166,0.25)] focus:outline-none focus:ring-1 focus:ring-teal-400/40"
            >
              <span>{totalCriteriaCount} tiêu chí</span>
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="text-teal-400/70 group-hover/badge:text-teal-300 group-hover/badge:translate-x-0.5 transition-all">
                <path d="m9 18 6-6-6-6" />
              </svg>
            </button>
            {node.category.parent_id != null && (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onViewInherited(node.category);
                }}
                title={`Xem các tiêu chí kế thừa từ danh mục cha của ${formatCategoryLabel(node.category.name)}`}
                className="inline-flex items-center gap-1 rounded-full bg-slate-800/90 hover:bg-slate-700 border border-slate-700/80 px-2 py-0.5 text-[10px] font-medium text-sky-300 hover:text-sky-200 transition-colors"
              >
                <Info size={11} className="text-sky-400 shrink-0" />
                <span>Xem tiêu chí kế thừa</span>
              </button>
            )}
          </div>

          {/* Right: contextual "+ Tiêu chí" CTA */}
          <div className="flex items-center gap-3 shrink-0">
            {!isVirtualNode && (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onAddCriteriaForCat(node.category);
                }}
                title={`Thêm tiêu chí vào ${formatCategoryLabel(node.category.name)}`}
                aria-label={`Thêm tiêu chí vào ${formatCategoryLabel(node.category.name)}`}
                className="
                  opacity-0 group-hover/row:opacity-100 transition-opacity duration-150
                  inline-flex items-center gap-1.5 rounded-lg
                  border border-teal-500/30 bg-teal-500/10 px-2.5 py-1
                  text-[11px] font-semibold text-teal-300
                  hover:border-teal-400/50 hover:bg-teal-500/20 hover:text-teal-200
                  transition-colors
                "
              >
                <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                  <path d="M12 5v14M5 12h14" />
                </svg>
                Tiêu chí
              </button>
            )}
          </div>
        </div>

        {/* FL Studio Seamless Bézier Tab */}
        {!isVirtualNode && (
          <TreeInsertorButton onClick={() => onAddSiblingCat(node.category)} />
        )}
      </div>

      {/* Expanded Content with YouTube Comment Thread Curved Connectors */}
      {isExpanded && (
        <div className="relative ml-6 space-y-3 pt-1.5 pb-1">
          {/* Section 1: Sub-categories */}
          {visibleChildrenCategories.length > 0 && (
            <div className="space-y-2">
              {visibleChildrenCategories.map((childNode, idx) => {
                const isLast = idx === visibleChildrenCategories.length - 1 && node.criteriaList.length === 0;
                return (
                  <div key={childNode.category.id} className="relative">
                    <CurvedTreeConnector isLast={isLast} />
                    <CategoryCriteriaTreeNode
                      node={childNode}
                      depth={depth + 1}
                      expandedIds={expandedIds}
                      onToggle={onToggle}
                      onEditCriteria={onEditCriteria}
                      onDeleteCriteria={onDeleteCriteria}
                      onViewPrompt={onViewPrompt}
                      onAddCriteriaForCat={onAddCriteriaForCat}
                      onAddSiblingCat={onAddSiblingCat}
                      onViewInherited={onViewInherited}
                      onViewCategoryCriteria={onViewCategoryCriteria}
                      deletingId={deletingId}
                      showEmptyCategories={showEmptyCategories}
                    />
                  </div>
                );
              })}
            </div>
          )}

          {/* Section 2: Criteria Items (Collapsable & Styled Banner) */}
          {node.criteriaList.length > 0 && (
            <div className="space-y-2 pt-1 relative">
              <CurvedTreeConnector isLast={false} />
              <div
                role="button"
                tabIndex={0}
                onClick={() => setIsCriteriaSectionExpanded(!isCriteriaSectionExpanded)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    setIsCriteriaSectionExpanded(!isCriteriaSectionExpanded);
                  }
                }}
                className="group flex flex-wrap items-center justify-between gap-2 p-2.5 rounded-xl border border-teal-500/30 bg-teal-950/30 hover:bg-teal-950/60 transition-all cursor-pointer select-none"
              >
                <div className="flex items-center gap-2">
                  <ChevronRight
                    size={15}
                    className={`text-teal-400 shrink-0 transition-transform duration-200 ${
                      isCriteriaSectionExpanded ? 'rotate-90 text-teal-300' : ''
                    }`}
                  />
                  <FileText size={15} className="text-teal-400 shrink-0" />
                  <span className="text-xs font-bold uppercase tracking-wider text-teal-300">
                    {isTopLevel ? 'Tiêu chí nền tảng dùng chung' : 'Tiêu chí trực tiếp của danh mục'} ({node.criteriaList.length})
                  </span>
                </div>
                {visibleChildrenCategories.length > 0 && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-teal-900/60 border border-teal-700/50 px-2 py-0.5 text-[10px] font-semibold text-teal-200">
                    <span>✨ Tất cả danh mục con tự động kế thừa</span>
                  </span>
                )}
              </div>

              {isCriteriaSectionExpanded && (
                <div className="space-y-2 pt-1">
                  {node.criteriaList.map((crit, idx) => {
                    const isLast = idx === node.criteriaList.length - 1;
                    return (
                      <div key={crit.id} className="relative">
                        <CurvedTreeConnector isLast={isLast} />
                        <div className="group/crit flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3 rounded-lg border border-slate-800/60 bg-slate-950/40 hover:bg-slate-900/90 hover:border-slate-700 transition-all">
                          {/* Left: Criteria Title & Prompt */}
                          <div className="flex items-start gap-2.5 min-w-0 flex-1">
                            <FileText size={15} className="text-teal-400 shrink-0 mt-0.5" />
                            <div className="min-w-0 flex-1 space-y-0.5">
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className="font-mono text-[11px] text-slate-500">#{crit.id}</span>
                                <h5 className="text-xs sm:text-sm font-semibold text-slate-100 truncate">
                                  {crit.name}
                                </h5>
                                {visibleChildrenCategories.length > 0 && (
                                  <span className="text-[10px] font-medium text-teal-400/90 bg-teal-950/60 border border-teal-800/40 px-1.5 py-0.2 rounded">
                                    Dùng chung
                                  </span>
                                )}
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
                                  <path d="M15 3h6v6" /><path d="M10 14 21 3" /><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
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
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Hierarchy Path Breadcrumb ────────────────────────────────────────────────
function HierarchyBreadcrumb({
  category,
  allCategories,
}: {
  category: JobCategoryDto;
  allCategories: JobCategoryDto[];
}) {
  const path = useMemo(
    () => buildAncestorPath(category.id, allCategories),
    [category.id, allCategories]
  );

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {path.map((cat, idx) => (
        <span key={cat.id} className="flex items-center gap-1.5">
          {idx > 0 && (
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="text-slate-600">
              <path d="m9 18 6-6-6-6" />
            </svg>
          )}
          <span
            className={`rounded-md border px-2 py-0.5 text-[11px] font-semibold ${idx === path.length - 1
                ? 'border-orange-500/40 bg-orange-500/10 text-orange-300'
                : 'border-slate-700/60 bg-slate-800/50 text-slate-400'
              }`}
          >
            {formatCategoryLabel(cat.name)}
          </span>
        </span>
      ))}
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────
export default function EvaluationCriteriaTable({ criteria, categories = [], mappings = [], onRefresh }: Props) {
  // ── Criteria modal state ──────────────────────────────────────────────────
  const [criteriaModalOpen, setCriteriaModalOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<EvaluationCriteriaDto | null>(null);
  const [criteriaForm, setCriteriaForm] = useState<CreateEvaluationCriteriaPayload>(emptyCriteriaForm);
  const [selectedLevels, setSelectedLevels] = useState<Set<string>>(new Set(['ALL']));
  const [addCriteriaForCat, setAddCriteriaForCat] = useState<JobCategoryDto | null>(null);
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  // ── Category sibling-insertion modal state ────────────────────────────────
  const [catModalOpen, setCatModalOpen] = useState(false);
  const [catForm, setCatForm] = useState<CreateJobCategoryPayload>(emptyCategoryForm);
  const [isCatCodeManual, setIsCatCodeManual] = useState(false);
  const [siblingContextCat, setSiblingContextCat] = useState<JobCategoryDto | null>(null);
  const [savingCat, setSavingCat] = useState(false);

  // ── View prompt & View inherited criteria modals & View all category criteria ──
  const [viewCriteria, setViewCriteria] = useState<EvaluationCriteriaDto | null>(null);
  const [inheritedTargetCat, setInheritedTargetCat] = useState<JobCategoryDto | null>(null);
  const [viewCategoryNode, setViewCategoryNode] = useState<CategoryTreeNodeData | null>(null);

  // ── Search & filter ───────────────────────────────────────────────────────
  const [searchQuery, setSearchQuery] = useState('');
  const [showEmptyCategories, setShowEmptyCategories] = useState(false);

  // ── Tree construction ─────────────────────────────────────────────────────
  const treeRoots = useMemo(
    () => buildCategoryCriteriaTree(categories, criteria, mappings),
    [categories, criteria, mappings]
  );

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

  // ── Search Filter ─────────────────────────────────────────────────────────
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

  // ── Criteria CRUD ─────────────────────────────────────────────────────────
  const openCreateCriteria = () => {
    setEditTarget(null);
    setAddCriteriaForCat(null);
    setCriteriaForm(emptyCriteriaForm);
    setSelectedLevels(new Set(['ALL']));
    setCriteriaModalOpen(true);
  };

  const openCreateCriteriaForCat = (cat: JobCategoryDto) => {
    setEditTarget(null);
    setAddCriteriaForCat(cat);
    setCriteriaForm({ ...emptyCriteriaForm, category: cat.code });
    setSelectedLevels(new Set(['ALL']));
    setCriteriaModalOpen(true);
  };

  const openEditCriteria = (crit: EvaluationCriteriaDto) => {
    setEditTarget(crit);
    setAddCriteriaForCat(null);
    setCriteriaForm({
      name: crit.name,
      category: crit.category,
      question_type: crit.question_type,
      prompt_instruction: crit.prompt_instruction,
    });
    setSelectedLevels(new Set(crit.mapped_levels && crit.mapped_levels.length > 0 ? crit.mapped_levels : ['ALL']));
    setCriteriaModalOpen(true);
  };

  const handleSaveCriteria = async () => {
    if (!criteriaForm.name.trim()) {
      toast.error('Tên tiêu chí không được để trống');
      return;
    }
    if (!criteriaForm.prompt_instruction?.trim()) {
      toast.error('Prompt instruction không được để trống');
      return;
    }
    setSaving(true);
    try {
      let savedCrit: EvaluationCriteriaDto;
      if (editTarget) {
        savedCrit = await adminService.updateEvaluationCriteria(editTarget.id, criteriaForm);
        toast.success('Cập nhật tiêu chí thành công!');
      } else {
        savedCrit = await adminService.createEvaluationCriteria(criteriaForm);
        toast.success('Tạo tiêu chí thành công!');
      }

      // Sync category mapping & selected levels (add new levels, remove unselected old levels)
      const targetCat = addCriteriaForCat
        ? addCriteriaForCat
        : editTarget && editTarget.category
        ? categories.find(
            (c) =>
              c.code.toLowerCase() === editTarget.category?.toLowerCase() ||
              c.name.toLowerCase() === editTarget.category?.toLowerCase()
          )
        : null;

      if (targetCat && savedCrit) {
        const existingLevels = new Set(editTarget?.mapped_levels || []);
        const newLevels = selectedLevels;

        // 1. Add newly selected levels
        for (const lvl of Array.from(newLevels)) {
          if (!existingLevels.has(lvl)) {
            try {
              await adminService.createCategoryMapping({
                category_id: targetCat.id,
                criteria_id: savedCrit.id,
                level: lvl,
                weight_percentage: 10,
              });
            } catch {
              // Already mapped
            }
          }
        }

        // 2. Delete unselected levels
        for (const lvl of Array.from(existingLevels)) {
          if (!newLevels.has(lvl)) {
            try {
              await adminService.deleteCategoryMapping(targetCat.id, savedCrit.id, lvl);
            } catch {
              // Already deleted
            }
          }
        }
      }

      setCriteriaModalOpen(false);
      onRefresh();
    } catch {
      toast.error('Có lỗi xảy ra. Vui lòng thử lại.');
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteCriteria = async (id: number) => {
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

  // ── Sibling Category CRUD ─────────────────────────────────────────────────
  const openAddSiblingCat = (cat: JobCategoryDto) => {
    // A "sibling" shares the same parentId as the hovered category
    setSiblingContextCat(cat);
    setCatForm({ ...emptyCategoryForm, parent_id: cat.parent_id });
    setIsCatCodeManual(false);
    setCatModalOpen(true);
  };

  const handleSaveCategory = async () => {
    if (!catForm.code.trim()) { toast.error('Mã danh mục (code) không được để trống'); return; }
    if (!catForm.name.trim()) { toast.error('Tên danh mục không được để trống'); return; }
    setSavingCat(true);
    try {
      await adminService.createJobCategory(catForm);
      toast.success('Tạo danh mục thành công!');
      setCatModalOpen(false);
      onRefresh();
    } catch {
      toast.error('Có lỗi xảy ra. Vui lòng thử lại.');
    } finally {
      setSavingCat(false);
    }
  };

  // ── Derived sibling context label ─────────────────────────────────────────
  const siblingParentLabel = useMemo(() => {
    if (!siblingContextCat) return null;
    if (!siblingContextCat.parent_id) return 'Root (cấp cao nhất)';
    const parent = categories.find((c) => c.id === siblingContextCat.parent_id);
    return parent ? formatCategoryLabel(parent.name) : null;
  }, [siblingContextCat, categories]);

  return (
    <RuleDashboardSection
      title="Tiêu chí đánh giá"
      count={criteria.length}
      countLabel="tiêu chí"
      description="Các tiêu chí đánh giá năng lực được sắp xếp gọn gàng theo cây danh mục. Hover vào danh mục để thêm sibling hoặc tiêu chí bên trong."
      action={
        <button
          onClick={openCreateCriteria}
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

      {/* Tree Content — extra padding-bottom so the last node's insertor button doesn't clip */}
      <div className="p-4 pb-8 space-y-4 bg-slate-950/20 min-h-[300px]">
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
              onEditCriteria={openEditCriteria}
              onDeleteCriteria={handleDeleteCriteria}
              onViewPrompt={setViewCriteria}
              onAddCriteriaForCat={openCreateCriteriaForCat}
              onAddSiblingCat={openAddSiblingCat}
              onViewInherited={setInheritedTargetCat}
              onViewCategoryCriteria={setViewCategoryNode}
              deletingId={deletingId}
              showEmptyCategories={showEmptyCategories}
            />
          ))
        )}
      </div>

      {/* ── Modal: Create / Edit Criteria ─────────────────────────────────── */}
      <Modal
        open={criteriaModalOpen}
        onClose={() => setCriteriaModalOpen(false)}
        title={editTarget ? 'Sửa tiêu chí' : 'Thêm tiêu chí'}
        size="lg"
      >
        <div className="space-y-4">

          {/* Contextual banner — shown when adding criteria from within a specific category */}
          {!editTarget && addCriteriaForCat && (
            <div className="rounded-xl border border-orange-500/30 bg-orange-500/8 p-4 space-y-2">
              <div className="flex items-center gap-2">
                {/* Folder icon */}
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-orange-500/30 bg-orange-500/15">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-orange-400">
                    <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
                  </svg>
                </div>
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-widest text-orange-400/70">
                    Đang thêm tiêu chí cho
                  </p>
                  <p className="text-sm font-bold text-white">
                    {formatCategoryLabel(addCriteriaForCat.name)}
                  </p>
                </div>
              </div>
              {/* Hierarchy breadcrumb */}
              <div className="pt-1">
                <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500 mb-1.5">
                  Cấp bậc danh mục
                </p>
                <HierarchyBreadcrumb
                  category={addCriteriaForCat}
                  allCategories={categories}
                />
              </div>
            </div>
          )}

          <div>
            <label className="block text-sm text-slate-400 mb-1.5">
              Tên tiêu chí <span className="text-red-400">*</span>
            </label>
            <input
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500/30 transition-colors"
              value={criteriaForm.name}
              onChange={(e) => setCriteriaForm({ ...criteriaForm, name: e.target.value })}
              placeholder="VD: Object-Oriented Programming (OOP)"
            />
          </div>

          <div>
            <label className="block text-sm text-slate-400 mb-1.5 font-medium">
              Áp dụng cho Cấp bậc (Seniority Levels) <span className="text-slate-500 text-xs font-normal">(bấm chọn cấp bậc)</span>
            </label>
            <div className="flex flex-wrap gap-2 pt-1">
              {LEVEL_ORDER.map((lvl) => {
                const isSelected = selectedLevels.has(lvl);
                return (
                  <button
                    key={lvl}
                    type="button"
                    onClick={() => {
                      const next = new Set(selectedLevels);
                      if (lvl === 'ALL') {
                        next.clear();
                        next.add('ALL');
                      } else {
                        next.delete('ALL');
                        if (next.has(lvl)) {
                          next.delete(lvl);
                        } else {
                          next.add(lvl);
                        }
                        if (next.size === 0) {
                          next.add('ALL');
                        }
                      }
                      setSelectedLevels(next);
                    }}
                    className={`px-3 py-1.5 rounded-lg text-xs font-bold border transition-all ${
                      isSelected
                        ? 'border-orange-500 bg-orange-500/20 text-orange-300 shadow-[0_0_12px_rgba(249,115,22,0.3)]'
                        : 'border-slate-800 bg-slate-900/60 text-slate-500 hover:border-slate-700 hover:text-slate-300'
                    }`}
                  >
                    {lvl}
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <label className="block text-sm text-slate-400 mb-1.5">
              Prompt Instruction <span className="text-red-400">*</span>
              <span className="text-slate-500 ml-2 text-xs">(được tiêm trực tiếp vào LLM)</span>
            </label>
            <textarea
              rows={10}
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm font-mono focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500/30 transition-colors resize-y"
              value={criteriaForm.prompt_instruction ?? ''}
              onChange={(e) => setCriteriaForm({ ...criteriaForm, prompt_instruction: e.target.value })}
              placeholder={'Evaluate understanding of OOP principles (Encapsulation, Inheritance, Polymorphism, Abstraction)...'}
            />
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button
              onClick={() => setCriteriaModalOpen(false)}
              className="px-4 py-2 text-sm text-slate-400 hover:text-white border border-slate-700 hover:border-slate-600 rounded-lg transition-colors"
            >
              Hủy
            </button>
            <button
              onClick={handleSaveCriteria}
              disabled={saving}
              className="px-4 py-2 text-sm font-medium bg-orange-600 hover:bg-orange-500 disabled:opacity-50 text-white rounded-lg transition-colors"
            >
              {saving ? 'Đang lưu...' : 'Lưu'}
            </button>
          </div>
        </div>
      </Modal>

      {/* ── Modal: Add Sibling Category (FL Studio + button) ──────────────── */}
      <Modal
        open={catModalOpen}
        onClose={() => setCatModalOpen(false)}
        title="Thêm danh mục cùng cấp"
        size="md"
      >
        <div className="space-y-4">

          {/* Context banner showing what sibling of what */}
          {siblingContextCat && (
            <div className="rounded-xl border border-slate-700/60 bg-slate-800/40 p-4 space-y-2">
              <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">
                Sẽ thêm danh mục cùng cấp với
              </p>
              <div className="flex items-center gap-2">
                <span className="rounded-lg border border-orange-500/30 bg-orange-500/10 px-3 py-1.5 text-sm font-bold text-orange-300">
                  {formatCategoryLabel(siblingContextCat.name)}
                </span>
                {siblingParentLabel && (
                  <>
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="text-slate-600">
                      <path d="m9 18 6-6-6-6" />
                    </svg>
                    <span className="text-xs text-slate-400">
                      Dưới: <span className="font-semibold text-slate-300">{siblingParentLabel}</span>
                    </span>
                  </>
                )}
              </div>
            </div>
          )}

          {/* Category Name FIRST */}
          <div>
            <label className="block text-sm text-slate-400 mb-1.5">
              Tên danh mục <span className="text-red-400">*</span>
            </label>
            <input
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500/30 transition-colors"
              value={catForm.name}
              onChange={(e) => {
                const newName = e.target.value;
                setCatForm((prev) => ({
                  ...prev,
                  name: newName,
                  code: isCatCodeManual ? prev.code : generateCategoryCode(newName),
                }));
              }}
              placeholder="VD: DevOps & Infrastructure"
            />
          </div>

          {/* Category Code SECOND with Auto-slug Hint */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="block text-sm text-slate-400">
                Mã danh mục (code) <span className="text-red-400">*</span>
              </label>
              {!isCatCodeManual && catForm.code && (
                <span className="text-[10px] font-semibold text-orange-400/90 bg-orange-500/10 border border-orange-500/20 px-2 py-0.5 rounded">
                  ✨ Tự động tạo
                </span>
              )}
            </div>
            <input
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500/30 transition-colors font-mono uppercase"
              value={catForm.code}
              onChange={(e) => {
                setIsCatCodeManual(true);
                setCatForm({
                  ...catForm,
                  code: e.target.value.toUpperCase().replace(/[^A-Z0-9_]/g, ''),
                });
              }}
              placeholder="VD: DEVOPS_INFRASTRUCTURE"
            />
            <p className="mt-1 text-[11px] text-slate-500 leading-normal">
              Mã dùng cho hệ thống Rule Engine. Tự động sinh từ Tên danh mục (chỉ gồm chữ in hoa, số và gạch dưới <code className="text-slate-400">_</code>).
            </p>
          </div>

          <div>
            <label className="block text-sm text-slate-400 mb-1.5">Danh mục cha</label>
            <select
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-orange-500 transition-colors"
              value={catForm.parent_id ?? ''}
              onChange={(e) => setCatForm({ ...catForm, parent_id: e.target.value ? Number(e.target.value) : null })}
            >
              <option value="">— Root (không có cha) —</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>{formatCategoryLabel(c.name)}</option>
              ))}
            </select>
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button
              onClick={() => setCatModalOpen(false)}
              className="px-4 py-2 text-sm text-slate-400 hover:text-white border border-slate-700 hover:border-slate-600 rounded-lg transition-colors"
            >
              Hủy
            </button>
            <button
              onClick={handleSaveCategory}
              disabled={savingCat}
              className="px-4 py-2 text-sm font-medium bg-orange-600 hover:bg-orange-500 disabled:opacity-50 text-white rounded-lg transition-colors"
            >
              {savingCat ? 'Đang lưu...' : 'Tạo danh mục'}
            </button>
          </div>
        </div>
      </Modal>

      {/* ── Modal: Detailed Prompt View ────────────────────────────────────── */}
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

      {/* ── Modal / Sheet: Inherited Criteria View ─────────────────────── */}
      {inheritedTargetCat && (
        <Modal
          open={Boolean(inheritedTargetCat)}
          onClose={() => setInheritedTargetCat(null)}
          title={`Tiêu chí kế thừa của ${formatCategoryLabel(inheritedTargetCat.name)}`}
          size="lg"
        >
          <div className="space-y-4">
            {/* Ancestor Hierarchy Path */}
            <div className="flex items-center gap-1.5 flex-wrap text-xs text-slate-400 bg-slate-900/60 p-3 rounded-lg border border-slate-800">
              <span className="font-semibold text-slate-300">Đường dẫn phân cấp:</span>
              <HierarchyBreadcrumb category={inheritedTargetCat} allCategories={categories} />
            </div>

            {/* Information Alert */}
            <div className="flex items-start gap-2.5 rounded-lg border border-sky-500/20 bg-sky-500/10 p-3.5 text-xs text-sky-300">
              <Info size={16} className="shrink-0 mt-0.5 text-sky-400" />
              <div className="space-y-1 leading-relaxed">
                <p className="font-semibold text-sky-200">
                  Sửa các tiêu chí này tại danh mục gốc tương ứng.
                </p>
                <p className="text-sky-300/80">
                  Khi đánh giá ứng viên cho danh mục <strong>{formatCategoryLabel(inheritedTargetCat.name)}</strong>, hệ thống Rule Engine và LLM sẽ tự động kế thừa tất cả các tiêu chí từ danh mục gốc và các danh mục cấp trên.
                </p>
              </div>
            </div>

            {/* Inherited Criteria List */}
            {(() => {
              const inheritedGroups = getInheritedCriteriaForCategory(
                inheritedTargetCat,
                categories,
                criteria,
                mappings
              );

              if (inheritedGroups.length === 0) {
                return (
                  <div className="py-8 text-center text-slate-400 bg-slate-950/40 rounded-xl border border-slate-800">
                    <p className="text-sm font-medium">Chưa có tiêu chí nào ở các danh mục cha.</p>
                    <p className="text-xs text-slate-500 mt-1">Các danh mục cấp trên chưa được gán tiêu chí đánh giá.</p>
                  </div>
                );
              }

              return (
                <div className="space-y-4 max-h-[60vh] overflow-y-auto pr-1">
                  {inheritedGroups.map(({ ancestor, criteriaList }) => (
                    <div key={ancestor.id} className="space-y-2">
                      <div className="flex items-center gap-2 border-b border-slate-800 pb-1.5">
                        <Folder size={14} className="text-orange-400" />
                        <h4 className="text-xs font-bold uppercase tracking-wider text-orange-300">
                          Kế thừa từ: {formatCategoryLabel(ancestor.name)} ({criteriaList.length} tiêu chí)
                        </h4>
                      </div>
                      <div className="space-y-1.5">
                        {criteriaList.map((crit) => (
                          <div
                            key={crit.id}
                            className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-3 rounded-lg border border-slate-800/80 bg-slate-950/60"
                          >
                            <div className="space-y-1 min-w-0 flex-1">
                              <div className="flex items-center gap-2">
                                <span className="font-mono text-[11px] text-slate-500">#{crit.id}</span>
                                <h5 className="text-xs sm:text-sm font-semibold text-slate-100">{crit.name}</h5>
                              </div>
                              <p className="line-clamp-1 text-xs text-slate-400 font-mono">
                                {crit.prompt_instruction}
                              </p>
                            </div>
                            <div className="shrink-0">
                              <MappedLevelsBadges levels={crit.mapped_levels} />
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              );
            })()}

            <div className="flex justify-end pt-2">
              <button
                type="button"
                onClick={() => setInheritedTargetCat(null)}
                className="rounded-lg border border-slate-700 bg-slate-800 px-4 py-2 text-sm text-slate-300 hover:text-white transition-colors"
              >
                Đóng
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* ── Modal: View All Category Criteria (Direct + All Sub-Categories) ─── */}
      {viewCategoryNode && (
        <CategoryAllCriteriaModal
          node={viewCategoryNode}
          allCategories={categories}
          onClose={() => setViewCategoryNode(null)}
          onViewPrompt={setViewCriteria}
          onEditCriteria={(crit) => {
            setViewCategoryNode(null);
            openEditCriteria(crit);
          }}
          onDeleteCriteria={handleDeleteCriteria}
          deletingId={deletingId}
        />
      )}
    </RuleDashboardSection>
  );
}
