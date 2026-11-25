'use client';

import { useState } from 'react';
import AiPolicyView from '../ai-policy/AiPolicyView';
import AuditLogsView from '../audit-logs/AuditLogsView';
import AdminBreadcrumbBar from '../layout/AdminBreadcrumbBar';
import AdminSidebar from '../layout/AdminSidebar';
import QueueStorageView from '../queue-storage/QueueStorageView';
import SessionInspectorView from '../sessions/SessionInspectorView';
import type { AdminSectionKey, TimeRangeKey } from '../types';
import UserManagementView from '../users/UserManagementView';
import AdminOverviewPanel from './AdminOverviewPanel';

export default function AdminDashboardView() {
  const [activeSection, setActiveSection] = useState<AdminSectionKey>('tong-quan');
  const [selectedRange, setSelectedRange] = useState<TimeRangeKey>('30d');
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  return (
    <div className="flex min-h-[calc(100vh-4.25rem)] w-full bg-[#f9f9ff] dark:bg-background text-[#141b2c] dark:text-foreground antialiased">
      <AdminSidebar
        activeSection={activeSection}
        onSelectSection={setActiveSection}
        mobileOpen={mobileSidebarOpen}
        onCloseMobile={() => setMobileSidebarOpen(false)}
      />
      <div className="flex min-w-0 flex-1 flex-col">
        <AdminBreadcrumbBar
          activeSection={activeSection}
          onOpenMobileSidebar={() => setMobileSidebarOpen(true)}
        />
        <div className="mx-auto w-full max-w-7xl flex-1 p-4 sm:p-8">
          {activeSection === 'tong-quan' && (
            <AdminOverviewPanel range={selectedRange} onSelectRange={setSelectedRange} />
          )}
          {activeSection === 'nguoi-dung' && <UserManagementView />}
          {activeSection === 'phien-phong-van' && <SessionInspectorView />}
          {activeSection === 'hang-doi-va-luu-tru' && <QueueStorageView />}
          {activeSection === 'ai-va-chinh-sach' && <AiPolicyView />}
          {activeSection === 'nhat-ky-quan-tri' && <AuditLogsView />}
        </div>
      </div>
    </div>
  );
}
