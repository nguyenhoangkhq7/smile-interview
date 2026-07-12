'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import axiosClient from '@/lib/axiosClient';
import {
  CategoryCriteriaMappingDto,
  CreateMappingPayload,
  EvaluationCriteriaDto,
  JobCategoryDto,
} from '@/services/adminService';
import { toast } from './Toast';
import Modal from './Modal';
import RuleDashboardSection from './rule-dashboard/RuleDashboardSection';
import ActionIconButton from './rule-dashboard/ActionIconButton';

type SeniorityLevel = 'ALL' | 'INTERN' | 'FRESHER' | 'JUNIOR' | 'MID' | 'SENIOR' | 'LEAD';

const SENIORITY_LEVELS: SeniorityLevel[] = ['ALL', 'INTERN', 'FRESHER', 'JUNIOR', 'MID', 'SENIOR', 'LEAD'];

const SENIORITY_LABELS: Record<SeniorityLevel, string> = {
  ALL: 'All',
  INTERN: 'Intern',
  FRESHER: 'Fresher',
  JUNIOR: 'Junior',
  MID: 'Mid',
  SENIOR: 'Senior',
  LEAD: 'Lead',
};

interface Props {
  mappings: CategoryCriteriaMappingDto[];
  categories: JobCategoryDto[];
  criteria: EvaluationCriteriaDto[];
  onRefresh: () => void;
}

interface MappingLeafNode {
  criteria: EvaluationCriteriaDto;
  mappingsByLevel: Partial<Record<SeniorityLevel, CategoryCriteriaMappingDto>>;
}

interface CategoryTreeNodeData {
  category: JobCategoryDto;
  children: CategoryTreeNodeData[];
  mappedCriteria: MappingLeafNode[];
}

interface MappingEditorState {
  mode: 'create' | 'edit';
  job_category_id: number;
  criteria_id: number;
  seniority_level: SeniorityLevel;
  weight_percentage: number;
}

interface CategoryOption {
  value: number;
  label: string;
}

const emptyEditorState: MappingEditorState = {
  mode: 'create',
  job_category_id: 0,
  criteria_id: 0,
  seniority_level: 'ALL',
  weight_percentage: 10,
};

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

function buildCategoryTree(
  categories: JobCategoryDto[],
  criteria: EvaluationCriteriaDto[],
  mappings: CategoryCriteriaMappingDto[]
): CategoryTreeNodeData[] {
  const categoryNodes = new Map<number, CategoryTreeNodeData>();
  const criteriaById = new Map(criteria.map((item) => [item.id, item]));

  categories.forEach((category) => {
    categoryNodes.set(category.id, {
      category,
      children: [],
      mappedCriteria: [],
    });
  });

  const roots: CategoryTreeNodeData[] = [];

  categories.forEach((category) => {
    const node = categoryNodes.get(category.id);
    if (!node) return;

    if (category.parent_id && categoryNodes.has(category.parent_id)) {
      categoryNodes.get(category.parent_id)!.children.push(node);
    } else {
      roots.push(node);
    }
  });

  const mappedCriteriaByCategory = new Map<number, Map<number, MappingLeafNode>>();

  mappings.forEach((mapping) => {
    const categoryNode = categoryNodes.get(mapping.job_category_id);
    const criteriaItem = criteriaById.get(mapping.criteria_id);
    if (!categoryNode || !criteriaItem) return;

    let categoryMap = mappedCriteriaByCategory.get(mapping.job_category_id);
    if (!categoryMap) {
      categoryMap = new Map();
      mappedCriteriaByCategory.set(mapping.job_category_id, categoryMap);
    }

    let leafNode = categoryMap.get(mapping.criteria_id);
    if (!leafNode) {
      leafNode = {
        criteria: criteriaItem,
        mappingsByLevel: {},
      };
      categoryMap.set(mapping.criteria_id, leafNode);
    }

    leafNode.mappingsByLevel[mapping.seniority_level as SeniorityLevel] = mapping;
  });

  const sortTree = (nodes: CategoryTreeNodeData[]) => {
    nodes.sort((left, right) => formatCategoryLabel(left.category.name).localeCompare(formatCategoryLabel(right.category.name)));
    nodes.forEach((node) => {
      node.children.sort((left, right) => formatCategoryLabel(left.category.name).localeCompare(formatCategoryLabel(right.category.name)));
      node.mappedCriteria = Array.from(mappedCriteriaByCategory.get(node.category.id)?.values() ?? [])
        .sort((left, right) => left.criteria.criteria_name.localeCompare(right.criteria.criteria_name));
      sortTree(node.children);
    });
  };

  sortTree(roots);
  return roots;
}

function collectCategoryOptions(nodes: CategoryTreeNodeData[], parentPath: string[] = []): CategoryOption[] {
  const options: CategoryOption[] = [];

  nodes.forEach((node) => {
    const nextPath = [...parentPath, formatCategoryLabel(node.category.name)];
    options.push({
      value: node.category.id,
      label: nextPath.join(' / '),
    });
    options.push(...collectCategoryOptions(node.children, nextPath));
  });

  return options;
}

function findMappingForLevel(
  mappings: CategoryCriteriaMappingDto[],
  jobCategoryId: number,
  criteriaId: number,
  seniorityLevel: SeniorityLevel
) {
  return mappings.find(
    (mapping) =>
      mapping.job_category_id === jobCategoryId &&
      mapping.criteria_id === criteriaId &&
      mapping.seniority_level === seniorityLevel
  ) ?? null;
}

function LevelTabs({
  value,
  onChange,
}: {
  value: SeniorityLevel;
  onChange: (nextValue: SeniorityLevel) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {SENIORITY_LEVELS.map((level) => {
        const isActive = value === level;
        return (
          <button
            key={level}
            type="button"
            onClick={() => onChange(level)}
            className={`inline-flex items-center gap-2 rounded-full border px-3.5 py-2 text-xs font-semibold tracking-wide transition-all duration-200 ${
              isActive
                ? 'border-teal-400 bg-teal-500 text-slate-950 shadow-[0_4px_16px_rgba(20,184,166,0.3)] ring-1 ring-teal-400/25'
                : 'border-slate-700/80 bg-white/[0.03] text-slate-400 hover:border-slate-500 hover:bg-white/[0.05] hover:text-white'
            }`}
          >
            <span className={`h-1.5 w-1.5 rounded-full ${isActive ? 'bg-slate-950' : 'bg-slate-600'}`} />
            {SENIORITY_LABELS[level]}
          </button>
        );
      })}
    </div>
  );
}

interface CriteriaBadgePopoverProps {
  criteriaCount: number;
  mappedCriteria: MappingLeafNode[];
}

function CriteriaBadgePopover({ criteriaCount, mappedCriteria }: CriteriaBadgePopoverProps) {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;

    const handleOutsideClick = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('click', handleOutsideClick);
    return () => {
      document.removeEventListener('click', handleOutsideClick);
    };
  }, [isOpen]);

  const togglePopover = (e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    setIsOpen((prev) => !prev);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.stopPropagation();
      e.preventDefault();
      setIsOpen((prev) => !prev);
    }
  };

  return (
    <div className="relative inline-block text-left" ref={containerRef}>
      <span
        role="button"
        tabIndex={0}
        onClick={togglePopover}
        onKeyDown={handleKeyDown}
        className={`rounded-full border px-1.5 py-0.5 text-[9px] font-medium uppercase tracking-[0.1em] cursor-pointer select-none transition-all duration-200 focus:outline-none ${
          isOpen
            ? 'border-teal-400 bg-teal-950/40 text-teal-300 ring-1 ring-teal-400/20'
            : 'border-slate-800 bg-slate-950/40 text-slate-500 hover:border-teal-500/50 hover:bg-teal-950/30 hover:text-teal-300 focus:border-teal-500/50 focus:bg-teal-950/30 focus:text-teal-300'
        }`}
      >
        {criteriaCount} criteria
      </span>

      {isOpen && (
        <div
          onClick={(e) => e.stopPropagation()}
          className="absolute left-0 mt-2.5 w-64 origin-top-left rounded-xl border border-slate-700/80 bg-slate-900 px-4 py-3.5 shadow-2xl shadow-black/85 z-50 animate-in fade-in slide-in-from-top-1 duration-150"
        >
          <div className="flex items-center justify-between border-b border-slate-800 pb-2 mb-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
              Criteria ({criteriaCount})
            </span>
          </div>

          {mappedCriteria.length === 0 ? (
            <div className="text-xs italic text-slate-500 py-1">
              Chưa có tiêu chí nào.
            </div>
          ) : (
            <div className="max-h-48 overflow-y-auto space-y-1.5 pr-1 scrollbar-thin">
              {mappedCriteria.map((leaf) => (
                <div
                  key={leaf.criteria.id}
                  className="flex items-start gap-2 py-0.5 text-xs text-slate-200 hover:text-white transition-colors"
                >
                  <span className="text-teal-400/80 select-none">•</span>
                  <span className="font-medium truncate" title={leaf.criteria.criteria_name}>
                    {leaf.criteria.criteria_name}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function CategoryTreeNode({
  node,
  depth,
  selectedLevel,
  expandedIds,
  onToggle,
  onEditLeaf,
  onDeleteLeaf,
}: {
  node: CategoryTreeNodeData;
  depth: number;
  selectedLevel: SeniorityLevel;
  expandedIds: Set<number>;
  onToggle: (categoryId: number) => void;
  onEditLeaf: (categoryId: number, criteriaId: number, seniorityLevel: SeniorityLevel) => void;
  onDeleteLeaf: (categoryId: number, criteriaId: number, seniorityLevel: SeniorityLevel) => void;
}) {
  const isExpanded = expandedIds.has(node.category.id);
  const selectedLeaves = node.mappedCriteria;

  return (
    <div className="relative">
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
        className="group flex w-full cursor-pointer items-center justify-between rounded-2xl border border-slate-700/70 bg-white/[0.025] px-4 py-4 text-left transition-all hover:border-slate-500/70 hover:bg-white/[0.04] focus:outline-none focus:ring-2 focus:ring-teal-500/20"
      >
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-teal-400/20 bg-gradient-to-br from-teal-500/15 to-cyan-500/10 text-teal-200 shadow-[0_0_0_1px_rgba(20,184,166,0.08)]">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 7h6l2 2h10v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z" />
            </svg>
          </div>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="truncate text-sm font-bold text-white sm:text-base">
                {formatCategoryLabel(node.category.name)}
              </span>
              <span className="rounded-full border border-slate-800 bg-slate-950/40 px-1.5 py-0.5 text-[9px] font-medium uppercase tracking-[0.1em] text-slate-500">
                {node.children.length} child{node.children.length === 1 ? '' : 'ren'}
              </span>
              <CriteriaBadgePopover
                criteriaCount={selectedLeaves.length}
                mappedCriteria={selectedLeaves}
              />
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 text-slate-400 transition-colors group-hover:text-slate-200">
          {!!node.children.length && (
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.25"
              className={`transition-transform duration-200 ${isExpanded ? 'rotate-90 text-teal-300' : 'rotate-0'}`}
            >
              <path d="m9 18 6-6-6-6" />
            </svg>
          )}
        </div>
      </div>

      {isExpanded && (
        <div
          className="ml-3 border-l border-slate-700/50 space-y-4 py-4 relative"
          style={{ paddingLeft: `${depth === 0 ? 1.5 : 2}rem` }}
        >
          {node.children.map((child) => (
            <CategoryTreeNode
              key={child.category.id}
              node={child}
              depth={depth + 1}
              selectedLevel={selectedLevel}
              expandedIds={expandedIds}
              onToggle={onToggle}
              onEditLeaf={onEditLeaf}
              onDeleteLeaf={onDeleteLeaf}
            />
          ))}

          <div className="space-y-3">
            {selectedLeaves.length === 0 ? (
              <div className="rounded-xl border border-dashed border-slate-700/70 bg-slate-950/35 px-4 py-4 text-sm text-slate-500">
                No mapped criteria for this category.
              </div>
            ) : (
              selectedLeaves.map((leaf) => {
                const selectedMapping = leaf.mappingsByLevel[selectedLevel] ?? null;
                const isSet = Boolean(selectedMapping);
                const mappingWeight = selectedMapping?.weight_percentage ?? 0;

                return (
                  <div
                    key={`${node.category.id}-${leaf.criteria.id}`}
                    className={`flex items-center justify-between gap-4 rounded-xl border px-4 py-3.5 transition-all duration-200 ${
                      isSet
                        ? 'border-teal-400/15 bg-teal-500/[0.04] shadow-[0_4px_16px_rgba(20,184,166,0.04)] hover:bg-teal-500/[0.08] hover:border-teal-400/30'
                        : 'border-slate-800 bg-slate-950/40 hover:bg-slate-800/50 hover:border-slate-700'
                    }`}
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        {/* HiOutlineDocumentText Document Icon */}
                        <svg
                          width="14"
                          height="14"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2.25"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          className="text-slate-400 shrink-0"
                        >
                          <path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z" />
                          <path d="M14 2v4a2 2 0 0 0 2 2h4" />
                          <path d="M10 9H8" />
                          <path d="M16 13H8" />
                          <path d="M16 17H8" />
                        </svg>
                        <p className="text-sm font-medium text-slate-100">{leaf.criteria.criteria_name}</p>
                        <span className={`rounded-full border px-1.5 py-0.5 text-[9px] font-medium uppercase tracking-[0.1em] ${
                          isSet
                            ? 'border-teal-400/20 bg-teal-500/10 text-teal-200'
                            : 'border-slate-800 bg-slate-900/50 text-slate-500'
                        }`}>
                          {SENIORITY_LABELS[selectedLevel]}
                        </span>
                      </div>
                      <p className="mt-1 pl-5 text-xs text-slate-500">
                        {isSet ? 'Mapping is configured for this level.' : 'No mapping configured for this level.'}
                      </p>
                    </div>

                    <div className="flex items-center gap-4 shrink-0">
                      <div className="min-w-[80px] text-right">
                        <p className={`text-[16px] font-bold tabular-nums tracking-tight ${isSet ? 'text-brand-green-mid' : 'text-slate-500'}`}>
                          {isSet ? `${mappingWeight}%` : '0%'}
                        </p>
                        <p className={`text-[10px] uppercase tracking-wider font-semibold ${isSet ? 'text-brand-green-mid/70' : 'text-slate-500/60'}`}>
                          {isSet ? 'Active' : 'Not Set'}
                        </p>
                      </div>

                      <div className="flex items-center gap-1.5">
                        <ActionIconButton
                          label={isSet ? 'Sửa trọng số' : 'Thêm trọng số'}
                          variant="accent"
                          onClick={() => onEditLeaf(node.category.id, leaf.criteria.id, selectedLevel)}
                          icon={(
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                            </svg>
                          )}
                        />

                        <ActionIconButton
                          label="Xóa mapping"
                          variant="danger"
                          disabled={!selectedMapping}
                          onClick={() => onDeleteLeaf(node.category.id, leaf.criteria.id, selectedLevel)}
                          icon={(
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                              <polyline points="3 6 5 6 21 6" />
                              <path d="M19 6l-1 14H6L5 6" />
                              <path d="M10 11v6M14 11v6" />
                              <path d="M9 6V4h6v2" />
                            </svg>
                          )}
                        />
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function MappingEditorModal({
  open,
  draft,
  saving,
  categories,
  criteria,
  selectedLevel,
  onClose,
  onSave,
  onChange,
  categoryOptions,
}: {
  open: boolean;
  draft: MappingEditorState;
  saving: boolean;
  categories: JobCategoryDto[];
  criteria: EvaluationCriteriaDto[];
  selectedLevel: SeniorityLevel;
  onClose: () => void;
  onSave: () => void;
  onChange: (nextDraft: MappingEditorState) => void;
  categoryOptions: CategoryOption[];
}) {
  const selectedCategoryLabel = categoryOptions.find((option) => option.value === draft.job_category_id)?.label ?? 'Select category';
  const selectedCriteriaLabel = criteria.find((item) => item.id === draft.criteria_id)?.criteria_name ?? 'Select criteria';

  return (
    <Modal open={open} onClose={onClose} title={draft.mode === 'edit' ? 'Sửa trọng số' : 'Thêm mapping'} size="md">
      <div className="space-y-5">
        <div className="rounded-2xl border border-slate-700/70 bg-white/[0.03] px-4 py-4">
          <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Seniority level</p>
          <p className="mt-1 text-sm font-medium text-white">{SENIORITY_LABELS[selectedLevel]}</p>
        </div>

        {draft.mode === 'create' ? (
          <div className="grid grid-cols-1 gap-4">
            <div>
              <label className="mb-1.5 block text-sm text-slate-400">Danh mục</label>
              <select
                className="w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-3 text-sm text-white focus:border-teal-400 focus:outline-none"
                value={draft.job_category_id}
                onChange={(event) => onChange({ ...draft, job_category_id: Number(event.target.value) })}
              >
                {categoryOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="mb-1.5 block text-sm text-slate-400">Tiêu chí</label>
              <select
                className="w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-3 text-sm text-white focus:border-teal-400 focus:outline-none"
                value={draft.criteria_id}
                onChange={(event) => onChange({ ...draft, criteria_id: Number(event.target.value) })}
              >
                {criteria.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.criteria_name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="mb-1.5 block text-sm text-slate-400">Cấp bậc</label>
              <select
                className="w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-3 text-sm text-white focus:border-teal-400 focus:outline-none"
                value={draft.seniority_level}
                onChange={(event) => onChange({ ...draft, seniority_level: event.target.value as SeniorityLevel })}
              >
                {SENIORITY_LEVELS.map((level) => (
                  <option key={level} value={level}>
                    {SENIORITY_LABELS[level]}
                  </option>
                ))}
              </select>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="rounded-xl border border-slate-700/70 bg-white/[0.03] px-4 py-4">
              <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Category</p>
              <p className="mt-1 text-sm font-medium text-white">{selectedCategoryLabel}</p>
            </div>
            <div className="rounded-xl border border-slate-700/70 bg-white/[0.03] px-4 py-4">
              <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Criteria</p>
              <p className="mt-1 text-sm font-medium text-white">{selectedCriteriaLabel}</p>
            </div>
          </div>
        )}

        <div>
          <label className="mb-1.5 block text-sm text-slate-400">Trọng số (%)</label>
          <input
            type="number"
            min={0}
            max={100}
            step={1}
            className="w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-3 text-sm font-mono tabular-nums text-white focus:border-teal-400 focus:outline-none"
            value={draft.weight_percentage}
            onChange={(event) => onChange({ ...draft, weight_percentage: Number(event.target.value) })}
          />
        </div>

        <div className="flex items-center justify-end gap-3 pt-1">
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl border border-slate-700/80 bg-white/[0.02] px-4 py-2.5 text-sm text-slate-400 transition-colors hover:border-slate-500 hover:bg-white/[0.05] hover:text-white"
          >
            Hủy
          </button>
          <button
            type="button"
            onClick={onSave}
            disabled={saving}
            className="rounded-xl border border-teal-400/25 bg-teal-400/10 px-4 py-2.5 text-sm font-medium text-teal-200 transition-colors hover:border-teal-400/50 hover:bg-teal-400/15 hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
          >
            {saving ? 'Đang lưu...' : 'Lưu'}
          </button>
        </div>
      </div>
    </Modal>
  );
}

export default function WeightMappingTable({ mappings, categories, criteria, onRefresh }: Props) {
  const [selectedLevel, setSelectedLevel] = useState<SeniorityLevel>('ALL');
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());
  const [editorOpen, setEditorOpen] = useState(false);
  const [editorState, setEditorState] = useState<MappingEditorState>(emptyEditorState);
  const [saving, setSaving] = useState(false);

  const treeData = useMemo(() => buildCategoryTree(categories, criteria, mappings), [categories, criteria, mappings]);
  const categoryOptions = useMemo(() => collectCategoryOptions(treeData), [treeData]);
  const visibleMappingCount = useMemo(
    () => mappings.filter((mapping) => mapping.seniority_level === selectedLevel).length,
    [mappings, selectedLevel]
  );

  useEffect(() => {
    if (treeData.length === 0) return;
    setExpandedIds((previous) => {
      if (previous.size > 0) return previous;
      return new Set(treeData.map((node) => node.category.id));
    });
  }, [treeData]);

  const openCreateModal = () => {
    if (categoryOptions.length === 0 || criteria.length === 0) {
      toast.error('Thiếu dữ liệu danh mục hoặc tiêu chí để tạo mapping.');
      return;
    }

    setEditorState({
      mode: 'create',
      job_category_id: categoryOptions[0].value,
      criteria_id: criteria[0].id,
      seniority_level: selectedLevel,
      weight_percentage: 10,
    });
    setEditorOpen(true);
  };

  const openLeafEditor = (jobCategoryId: number, criteriaId: number, seniorityLevel: SeniorityLevel) => {
    const existingMapping = findMappingForLevel(mappings, jobCategoryId, criteriaId, seniorityLevel);

    setEditorState({
      mode: existingMapping ? 'edit' : 'create',
      job_category_id: jobCategoryId,
      criteria_id: criteriaId,
      seniority_level: seniorityLevel,
      weight_percentage: existingMapping?.weight_percentage ?? 10,
    });
    setEditorOpen(true);
  };

  const closeEditor = () => {
    setEditorOpen(false);
    setSaving(false);
  };

  const handleDeleteMapping = async (jobCategoryId: number, criteriaId: number, seniorityLevel: SeniorityLevel) => {
    const existingMapping = findMappingForLevel(mappings, jobCategoryId, criteriaId, seniorityLevel);
    if (!existingMapping) return;

    if (!confirm('Xóa mapping này?')) return;

    try {
      await axiosClient.delete(`/api/admin/category-criteria-mappings/${jobCategoryId}/${criteriaId}/${seniorityLevel}`);
      toast.success('Đã xóa mapping.');
      onRefresh();
    } catch {
      toast.error('Không thể xóa mapping này.');
    }
  };

  const handleSave = async () => {
    if (editorState.job_category_id === 0 || editorState.criteria_id === 0) {
      toast.error('Vui lòng chọn danh mục và tiêu chí.');
      return;
    }

    setSaving(true);
    try {
      const existingMapping = findMappingForLevel(
        mappings,
        editorState.job_category_id,
        editorState.criteria_id,
        editorState.seniority_level
      );

      const payload: CreateMappingPayload = {
        job_category_id: editorState.job_category_id,
        criteria_id: editorState.criteria_id,
        seniority_level: editorState.seniority_level,
        weight_percentage: editorState.weight_percentage,
      };

      if (existingMapping) {
        await axiosClient.put(
          `/api/admin/category-criteria-mappings/${editorState.job_category_id}/${editorState.criteria_id}/${editorState.seniority_level}`,
          { weight_percentage: editorState.weight_percentage }
        );
        toast.success('Cập nhật trọng số thành công!');
      } else {
        await axiosClient.post('/api/admin/category-criteria-mappings', payload);
        toast.success('Tạo mapping thành công!');
      }

      setEditorOpen(false);
      onRefresh();
    } catch {
      toast.error('Có lỗi xảy ra. Vui lòng thử lại.');
    } finally {
      setSaving(false);
    }
  };

  const toggleCategory = (categoryId: number) => {
    setExpandedIds((previous) => {
      const next = new Set(previous);
      if (next.has(categoryId)) {
        next.delete(categoryId);
      } else {
        next.add(categoryId);
      }
      return next;
    });
  };

  return (
    <RuleDashboardSection
      title="Trọng số tiêu chí"
      count={mappings.length}
      countLabel="mapping"
      description="Cấu trúc cây theo hệ thống danh mục. Chọn seniority level để xem và chỉnh trọng số của từng mapping tương ứng."
      action={(
        <button
          onClick={openCreateModal}
          disabled={categoryOptions.length === 0 || criteria.length === 0}
          className="inline-flex items-center gap-2 rounded-xl border border-teal-500/25 bg-teal-500/10 px-3.5 py-2 text-sm font-semibold text-teal-300 transition-colors hover:border-teal-500/50 hover:bg-teal-500/15 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <path d="M12 5v14M5 12h14" />
          </svg>
          Thêm mapping
        </button>
      )}
    >
      <div className="border-t border-white/6 bg-slate-950/35 px-5 py-5 lg:px-7 lg:py-6">
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Seniority level</p>
              <p className="mt-1 text-sm text-slate-400">
                {visibleMappingCount} mapping{visibleMappingCount === 1 ? '' : 's'} for {SENIORITY_LABELS[selectedLevel]}
              </p>
            </div>
            <LevelTabs value={selectedLevel} onChange={setSelectedLevel} />
          </div>

          <div className="rounded-3xl border border-white/6 bg-slate-950/60 p-4 shadow-[0_16px_60px_rgba(2,6,23,0.18)] lg:p-5">
            {treeData.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-slate-700/70 bg-white/[0.02] px-6 py-12 text-center text-slate-500">
                No category tree data available.
              </div>
            ) : (
              <div className="space-y-4">
                {treeData.map((rootNode) => (
                  <CategoryTreeNode
                    key={rootNode.category.id}
                    node={rootNode}
                    depth={0}
                    selectedLevel={selectedLevel}
                    expandedIds={expandedIds}
                    onToggle={toggleCategory}
                    onEditLeaf={openLeafEditor}
                    onDeleteLeaf={handleDeleteMapping}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      <MappingEditorModal
        open={editorOpen}
        draft={editorState}
        saving={saving}
        categories={categories}
        criteria={criteria}
        selectedLevel={editorState.seniority_level}
        onClose={closeEditor}
        onSave={handleSave}
        onChange={setEditorState}
        categoryOptions={categoryOptions}
      />
    </RuleDashboardSection>
  );
}
