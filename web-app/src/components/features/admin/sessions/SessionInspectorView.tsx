'use client';

import React, { useRef, useState } from 'react';
import { ActionToast } from '../users/UserModals';
import EvaluationSummaryColumn from './EvaluationSummaryColumn';
import FocusedSessionBanner from './FocusedSessionBanner';
import InspectionPipelineStepper from './InspectionPipelineStepper';
import { DEFAULT_INSPECTED_SESSION } from './mockSessionsData';
import SessionsFilterBar from './SessionsFilterBar';
import SessionsHeader from './SessionsHeader';
import TranscriptInspectorColumn from './TranscriptInspectorColumn';
import { SessionFilterTabKey } from './types';

export default function SessionInspectorView() {
  const [activeFilterTab, setActiveFilterTab] = useState<SessionFilterTabKey>('completed');
  const [sessionSearch, setSessionSearch] = useState<string>('#SESS-2025-0891');
  const [activeStageId, setActiveStageId] = useState<number>(4);
  const [selectedTurnId, setSelectedTurnId] = useState<string>('T3');
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const session = DEFAULT_INSPECTED_SESSION;

  const triggerToast = (msg: string) => {
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    setToastMessage(msg);
    toastTimerRef.current = setTimeout(() => {
      setToastMessage(null);
    }, 3000);
  };

  return (
    <div className="flex w-full flex-col gap-5 pb-8">
      {/* 1. Clean Top Header */}
      <SessionsHeader />

      {/* 2. Filter Tabs & Search Bar */}
      <SessionsFilterBar
        activeFilterTab={activeFilterTab}
        onSelectFilterTab={setActiveFilterTab}
        sessionSearch={sessionSearch}
        onSessionSearchChange={setSessionSearch}
      />

      {/* 3. Focused Session Card Banner */}
      <FocusedSessionBanner
        session={session}
        onExportPdf={() =>
          triggerToast(`Đang tải xuống Báo cáo năng lực PDF cho phiên ${session.sessionId}`)
        }
      />

      {/* 4. Compact 5-Stage Pipeline Stepper */}
      <InspectionPipelineStepper
        stages={session.pipelineStages}
        activeStageId={activeStageId}
        onSelectStage={setActiveStageId}
      />

      {/* 5. Main Two-Column Workspace (8:4) */}
      <div className="grid grid-cols-1 items-start gap-5 lg:grid-cols-12">
        <TranscriptInspectorColumn
          turns={session.turns}
          selectedTurnId={selectedTurnId}
          onSelectTurn={setSelectedTurnId}
        />

        <EvaluationSummaryColumn session={session} />
      </div>

      <ActionToast message={toastMessage} />
    </div>
  );
}
