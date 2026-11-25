'use client';

import React, { useMemo, useRef, useState } from 'react';
import { ActionToast } from '../users/UserModals';
import {
  INITIAL_QUEUE_KPI_STATS,
  INITIAL_SKILL_GAP_JOBS,
  INITIAL_STORAGE_OVERVIEW,
} from './mockQueueStorageData';
import QueueFilterActionBar from './QueueFilterActionBar';
import QueueKpiBento from './QueueKpiBento';
import QueueStorageHeader from './QueueStorageHeader';
import SkillGapQueueTable from './SkillGapQueueTable';
import StorageAllocationSection from './StorageAllocationSection';
import { QueueJobStatus, SkillGapJobItem } from './types';

export default function QueueStorageView() {
  const [kpiStats, setKpiStats] = useState(INITIAL_QUEUE_KPI_STATS);
  const [jobs, setJobs] = useState<SkillGapJobItem[]>(INITIAL_SKILL_GAP_JOBS);
  const [storage, setStorage] = useState(INITIAL_STORAGE_OVERVIEW);

  const [jobSearch, setJobSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<'' | QueueJobStatus>('');

  const [retryingJobIds, setRetryingJobIds] = useState<Set<string>>(new Set());
  const [isBulkRetrying, setIsBulkRetrying] = useState(false);
  const [isCleaningOrphans, setIsCleaningOrphans] = useState(false);

  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const triggerToast = (msg: string) => {
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    setToastMessage(msg);
    toastTimerRef.current = setTimeout(() => {
      setToastMessage(null);
    }, 3000);
  };

  const filteredJobs = useMemo(() => {
    const query = jobSearch.trim().toLowerCase();
    return jobs.filter((job) => {
      if (statusFilter && job.status !== statusFilter) return false;
      if (query) {
        const matchId = job.id.toLowerCase().includes(query);
        const matchName = job.candidateName.toLowerCase().includes(query);
        const matchRole = job.roleTitle.toLowerCase().includes(query);
        if (!matchId && !matchName && !matchRole) return false;
      }
      return true;
    });
  }, [jobs, jobSearch, statusFilter]);

  const handleRetryJob = (jobId: string) => {
    setRetryingJobIds((prev) => new Set(prev).add(jobId));
    triggerToast(`Đang thử lại tiến trình ${jobId}...`);

    setTimeout(() => {
      setJobs((prev) =>
        prev.map((j) =>
          j.id === jobId
            ? {
                ...j,
                status: 'RUNNING',
                statusDetail: 'Đang xử lý lại...',
                attemptsUsed: 1,
              }
            : j
        )
      );
      setKpiStats((prev) => ({
        ...prev,
        failedCount: Math.max(0, prev.failedCount - 1),
        runningCount: prev.runningCount + 1,
      }));
    }, 350);

    setTimeout(() => {
      setJobs((prev) =>
        prev.map((j) =>
          j.id === jobId
            ? {
                ...j,
                status: 'SUCCEEDED',
                statusDetail: 'Hoàn tất',
              }
            : j
        )
      );
      setKpiStats((prev) => ({
        ...prev,
        runningCount: Math.max(0, prev.runningCount - 1),
        succeededCount: prev.succeededCount + 1,
      }));
      setRetryingJobIds((prev) => {
        const next = new Set(prev);
        next.delete(jobId);
        return next;
      });
      triggerToast(`Tiến trình ${jobId} đã xử lý hoàn tất!`);
    }, 1500);
  };

  const handleReleaseLease = (jobId: string) => {
    setJobs((prev) =>
      prev.map((j) =>
        j.id === jobId
          ? {
              ...j,
              status: 'PENDING',
              statusDetail: 'Chờ worker mới',
            }
          : j
      )
    );
    setKpiStats((prev) => ({
      ...prev,
      runningCount: Math.max(0, prev.runningCount - 1),
      pendingCount: prev.pendingCount + 1,
    }));
    triggerToast(`Đã giải phóng ${jobId} về trạng thái PENDING.`);
  };

  const handlePrioritizeJob = (jobId: string) => {
    triggerToast(`Đã ưu tiên chạy ${jobId}!`);
    setJobs((prev) =>
      prev.map((j) =>
        j.id === jobId
          ? {
              ...j,
              status: 'RUNNING',
              attemptsUsed: 1,
            }
          : j
      )
    );
    setKpiStats((prev) => ({
      ...prev,
      pendingCount: Math.max(0, prev.pendingCount - 1),
      runningCount: prev.runningCount + 1,
    }));
  };

  const handleRetryAllFailed = () => {
    setIsBulkRetrying(true);
    const failedJob = jobs.find((j) => j.status === 'FAILED');
    if (failedJob) {
      handleRetryJob(failedJob.id);
    } else {
      triggerToast('Đang thử lại các tiến trình lỗi...');
    }
    setTimeout(() => {
      setIsBulkRetrying(false);
    }, 1200);
  };

  const handleCleanOrphans = () => {
    setIsCleaningOrphans(true);
    triggerToast(`Đang dọn dẹp ${storage.orphanedFilesCount} tệp mồ côi...`);
    setTimeout(() => {
      setIsCleaningOrphans(false);
      setStorage((prev) => ({
        ...prev,
        totalUsedGb: Number((prev.totalUsedGb - 0.2).toFixed(1)),
        usedPercentage: Number((prev.usedPercentage - 0.1).toFixed(1)),
        orphanedFilesCount: 0,
        orphanedFilesSizeMb: 0,
      }));
      triggerToast('Đã dọn dẹp xong 186 MB tệp mồ côi!');
    }, 1300);
  };

  return (
    <div className="flex w-full flex-col gap-5 pb-8">
      <QueueStorageHeader />

      <QueueKpiBento stats={kpiStats} />

      <QueueFilterActionBar
        jobSearch={jobSearch}
        onJobSearchChange={setJobSearch}
        statusFilter={statusFilter}
        onStatusFilterChange={setStatusFilter}
        failedJobsCount={kpiStats.failedCount}
        onRetryAllFailed={handleRetryAllFailed}
        isBulkRetrying={isBulkRetrying}
      />

      <SkillGapQueueTable
        jobs={filteredJobs}
        totalJobsCount={14210}
        retryingJobIds={retryingJobIds}
        onRetryJob={handleRetryJob}
        onReleaseLease={handleReleaseLease}
        onPrioritizeJob={handlePrioritizeJob}
        onInspectJob={(job) =>
          triggerToast(`Đã xem chi tiết tiến trình ${job.id} (${job.candidateName})`)
        }
      />

      <StorageAllocationSection
        storage={storage}
        isCleaningOrphans={isCleaningOrphans}
        onCleanOrphans={handleCleanOrphans}
      />

      <ActionToast message={toastMessage} />
    </div>
  );
}
