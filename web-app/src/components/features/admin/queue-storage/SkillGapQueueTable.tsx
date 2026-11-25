'use client';

import React from 'react';
import {
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  Eye,
  ListVideo,
  RotateCcw,
  Unplug,
} from 'lucide-react';
import { SkillGapJobItem } from './types';

interface SkillGapQueueTableProps {
  jobs: SkillGapJobItem[];
  totalJobsCount: number;
  retryingJobIds: Set<string>;
  onRetryJob: (jobId: string) => void;
  onReleaseLease: (jobId: string) => void;
  onPrioritizeJob: (jobId: string) => void;
  onInspectJob: (job: SkillGapJobItem) => void;
}

export default function SkillGapQueueTable({
  jobs,
  totalJobsCount,
  retryingJobIds,
  onRetryJob,
  onReleaseLease,
  onPrioritizeJob,
  onInspectJob,
}: SkillGapQueueTableProps) {
  return (
    <div className="overflow-hidden rounded-xl bg-white shadow-xs">
      {/* Header Bar */}
      <div className="flex items-center gap-2 bg-white p-4">
        <ListVideo className="size-4.5 text-[#ad2c00]" />
        <h2 className="text-base font-semibold text-[#141b2c]">
          Danh sách tiến trình phân tích (Skill Gap Queue)
        </h2>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left">
          <thead>
            <tr className="bg-[#f1f3ff] text-[11px] font-semibold uppercase tracking-wider text-[#5c4039]">
              <th className="px-4 py-3">Mã Job</th>
              <th className="px-4 py-3">Ứng viên / Vị trí</th>
              <th className="px-4 py-3">Trạng thái</th>
              <th className="px-4 py-3 text-center">Lần thử</th>
              <th className="px-4 py-3">Tạo lúc</th>
              <th className="px-4 py-3 text-right">Thao tác</th>
            </tr>
          </thead>

          <tbody className="divide-y divide-[#f1f3ff] text-xs">
            {jobs.map((job) => {
              const isRetrying = retryingJobIds.has(job.id);
              const isRunning = job.status === 'RUNNING';
              const isFailed = job.status === 'FAILED';
              const isSucceeded = job.status === 'SUCCEEDED';

              return (
                <tr
                  key={job.id}
                  className={`transition-colors duration-300 ${
                    isRunning
                      ? 'bg-[#cce5ff]/15 hover:bg-[#f1f3ff]/70'
                      : 'hover:bg-[#f1f3ff]/70'
                  }`}
                >
                  <td
                    className={`px-4 py-3.5 font-mono text-xs font-semibold ${
                      isFailed
                        ? 'text-[#ad2c00]'
                        : isRunning
                          ? 'text-[#186392]'
                          : 'text-[#141b2c]'
                    }`}
                  >
                    {job.id}
                  </td>

                  <td className="px-4 py-3.5">
                    <div className="text-sm font-semibold text-[#141b2c]">
                      {job.candidateName}
                    </div>
                    <div className="text-xs text-[#5c4039]">{job.roleTitle}</div>
                  </td>

                  <td className="px-4 py-3.5">
                    <div className="inline-flex flex-col">
                      {isFailed && (
                        <>
                          <span className="inline-flex w-fit items-center gap-1.5 rounded-md bg-[#ffdad6] px-2.5 py-0.5 text-[11px] font-semibold text-[#93000a]">
                            <span className="size-1.5 rounded-full bg-[#ba1a1a]" />
                            FAILED
                          </span>
                          <span className="mt-1 font-mono text-[11px] text-[#ba1a1a]">
                            {job.statusDetail}
                          </span>
                        </>
                      )}

                      {isRunning && (
                        <>
                          <span className="inline-flex w-fit items-center gap-1.5 rounded-md bg-[#8ccafe] px-2.5 py-0.5 text-[11px] font-semibold text-[#005581]">
                            <span className="size-1.5 animate-ping rounded-full bg-[#186392]" />
                            RUNNING
                          </span>
                          <div className="mt-1.5 h-1 w-28 overflow-hidden rounded-full bg-[#e0e8ff]">
                            <div className="h-full w-2/3 animate-pulse rounded-full bg-[#186392]" />
                          </div>
                        </>
                      )}

                      {isSucceeded && (
                        <span className="inline-flex w-fit items-center gap-1.5 rounded-md bg-[#1f8642] px-2.5 py-0.5 text-[11px] font-semibold text-[#f7fff3]">
                          <span className="size-1.5 rounded-full bg-[#f7fff3]" />
                          SUCCEEDED
                        </span>
                      )}

                      {job.status === 'PENDING' && (
                        <span className="inline-flex w-fit items-center gap-1.5 rounded-md bg-[#e0e8ff] px-2.5 py-0.5 text-[11px] font-semibold text-[#141b2c]">
                          <span className="size-1.5 rounded-full bg-[#5c4039]" />
                          PENDING
                        </span>
                      )}
                    </div>
                  </td>

                  <td className="px-4 py-3.5 text-center">
                    <span
                      className={`rounded px-2 py-0.5 font-mono text-xs ${
                        isFailed
                          ? 'bg-[#ffdad6]/50 font-bold text-[#ba1a1a]'
                          : 'bg-[#e0e8ff] text-[#141b2c]'
                      }`}
                    >
                      {job.attemptsUsed}/{job.maxAttempts}
                    </span>
                  </td>

                  <td className="px-4 py-3.5 font-mono text-xs text-[#5c4039]">
                    {job.createdAt}
                  </td>

                  <td className="px-4 py-3.5 text-right">
                    {isFailed && (
                      <button
                        type="button"
                        onClick={() => onRetryJob(job.id)}
                        disabled={isRetrying}
                        className="inline-flex items-center gap-1 rounded bg-[#ad2c00] px-2.5 py-1.5 text-xs font-medium text-white shadow-2xs transition-colors hover:bg-[#d83900] disabled:opacity-60 cursor-pointer"
                      >
                        <RotateCcw className={`size-3.5 ${isRetrying ? 'animate-spin' : ''}`} />
                        <span>Thử lại</span>
                      </button>
                    )}

                    {isRunning && (
                      <button
                        type="button"
                        onClick={() => onReleaseLease(job.id)}
                        className="inline-flex items-center gap-1 rounded bg-[#f1f3ff] px-2.5 py-1.5 text-xs font-medium text-[#186392] transition-colors hover:bg-[#e0e8ff] cursor-pointer"
                      >
                        <Unplug className="size-3.5" />
                        <span>Giải phóng</span>
                      </button>
                    )}

                    {isSucceeded && (
                      <button
                        type="button"
                        onClick={() => onInspectJob(job)}
                        className="inline-flex items-center gap-1 rounded bg-[#f1f3ff] px-2.5 py-1.5 text-xs font-medium text-[#141b2c] transition-colors hover:bg-[#e0e8ff] cursor-pointer"
                      >
                        <Eye className="size-3.5" />
                        <span>Chi tiết</span>
                      </button>
                    )}

                    {job.status === 'PENDING' && (
                      <button
                        type="button"
                        onClick={() => onPrioritizeJob(job.id)}
                        className="inline-flex items-center gap-1 rounded bg-[#f1f3ff] px-2.5 py-1.5 text-xs font-medium text-[#ad2c00] transition-colors hover:bg-[#e0e8ff] cursor-pointer"
                      >
                        <AlertCircle className="size-3.5" />
                        <span>Ưu tiên</span>
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex flex-col items-center justify-between gap-2 bg-[#f1f3ff]/50 px-4 py-3.5 sm:flex-row">
        <div className="text-xs text-[#5c4039]">
          Hiển thị <span className="font-semibold text-[#141b2c]">1 - {jobs.length}</span> /{' '}
          <span className="font-semibold text-[#141b2c]">
            {totalJobsCount.toLocaleString('en-US')}
          </span>{' '}
          jobs
        </div>

        <div className="flex items-center gap-1">
          <button
            type="button"
            disabled
            aria-label="Trang trước"
            className="rounded bg-white p-1 text-[#5c4039] opacity-40"
          >
            <ChevronLeft className="size-4" />
          </button>
          <span className="rounded bg-[#ad2c00] px-2 py-0.5 font-mono text-xs text-white">1</span>
          <button
            type="button"
            className="rounded bg-white px-2 py-0.5 font-mono text-xs text-[#141b2c] hover:bg-[#e0e8ff] cursor-pointer"
          >
            2
          </button>
          <button
            type="button"
            className="rounded bg-white px-2 py-0.5 font-mono text-xs text-[#141b2c] hover:bg-[#e0e8ff] cursor-pointer"
          >
            3
          </button>
          <span className="px-1 text-xs text-[#5c4039]">...</span>
          <button
            type="button"
            className="rounded bg-white px-2 py-0.5 font-mono text-xs text-[#141b2c] hover:bg-[#e0e8ff] cursor-pointer"
          >
            355
          </button>
          <button
            type="button"
            aria-label="Trang tiếp"
            className="rounded bg-white p-1 text-[#5c4039] hover:text-[#141b2c] cursor-pointer"
          >
            <ChevronRight className="size-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
