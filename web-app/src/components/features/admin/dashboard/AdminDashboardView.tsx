'use client';

import React, { useState } from 'react';
import AiPolicyView from '../ai-policy/AiPolicyView';
import AuditLogsView from '../audit-logs/AuditLogsView';
import { DASHBOARD_DATA_BY_RANGE } from '../data/mockDashboardData';
import AdminBreadcrumbBar from '../layout/AdminBreadcrumbBar';
import AdminSidebar from '../layout/AdminSidebar';
import QueueStorageView from '../queue-storage/QueueStorageView';
import SessionInspectorView from '../sessions/SessionInspectorView';
import { AdminSectionKey, TimeRangeKey } from '../types';
import UserManagementView from '../users/UserManagementView';
import AiEvaluationV2Section from './AiEvaluationV2Section';
import DashboardHeader from './DashboardHeader';
import KpiGrid from './KpiGrid';
import MethodTerminationCard from './MethodTerminationCard';
import SkillGapInsightsSection from './SkillGapInsightsSection';
import VolumeTelemetryChart from './VolumeTelemetryChart';

export default function AdminDashboardView() {
  const [activeSection, setActiveSection] = useState<AdminSectionKey>('tong-quan');
  const [selectedRange, setSelectedRange] = useState<TimeRangeKey>('30d');
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState<boolean>(false);

  const currentData = DASHBOARD_DATA_BY_RANGE[selectedRange];

  return (
    <div className="flex min-h-[calc(100vh-4.25rem)] w-full bg-[#f9f9ff] text-[#141b2c] antialiased">
      {/* Left Navigation Sidebar */}
      <AdminSidebar
        activeSection={activeSection}
        onSelectSection={setActiveSection}
        mobileOpen={mobileSidebarOpen}
        onCloseMobile={() => setMobileSidebarOpen(false)}
      />

      {/* Main Content Area */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Top Breadcrumb Bar */}
        <AdminBreadcrumbBar
          activeSection={activeSection}
          onOpenMobileSidebar={() => setMobileSidebarOpen(true)}
        />

        {/* Workspace Body */}
        <div className="mx-auto w-full max-w-7xl flex-1 p-4 sm:p-8">
          {activeSection === 'nguoi-dung' ? (
            <UserManagementView />
          ) : activeSection === 'phien-phong-van' ? (
            <SessionInspectorView />
          ) : activeSection === 'hang-doi-va-luu-tru' ? (
            <QueueStorageView />
          ) : activeSection === 'ai-va-chinh-sach' ? (
            <AiPolicyView />
          ) : activeSection === 'nhat-ky-quan-tri' ? (
            <AuditLogsView />
          ) : (
            <div className="flex w-full flex-col gap-6 pb-8">
              {/* 1. Page Header & Time Filter Pills */}
              <DashboardHeader
                selectedRange={selectedRange}
                onSelectRange={setSelectedRange}
              />

              {/* 2. KPI Grid (6 Horizontally Aligned Data Tiles) */}
              <KpiGrid metrics={currentData.kpi} />

              {/* 3. Operational Telemetry Analytics (7:5 Grid) */}
              <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
                <VolumeTelemetryChart
                  points={currentData.telemetryPoints}
                  rangeLabel={currentData.rangeLabel}
                />

                <MethodTerminationCard segments={currentData.terminationSegments} />
              </div>

              {/* 4. AI Evaluation Distribution Section */}
              <AiEvaluationV2Section levels={currentData.aiEvalLevels} />

              {/* 5. Skill Gap Insights & Target Role Distribution Section */}
              <SkillGapInsightsSection
                knowledgeGaps={currentData.knowledgeGaps}
                popularRoles={currentData.popularRoles}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
