import { Suspense, lazy, useState, useEffect, useCallback, useRef } from 'react';
import type { ReportEntry, DiscussionConfig, SessionData, BlueprintExportFormat } from './types';
import { SCHEMA_VERSION } from './constants';
import { useWebSocket } from './hooks/useWebSocket';
import { useSession } from './hooks/useSession';
import {
  exportAsMarkdown,
  downloadMarkdown,
  printAsPdf,
  captureScreenshot,
  exportBlueprint,
} from './utils/export';
import { Sidebar } from './components/Sidebar/Sidebar';
import { TopBar } from './components/TopBar/TopBar';
import { ProgressBar } from './components/Progress/ProgressBar';
import { AgentStatusPanel } from './components/Progress/AgentStatusPanel';
import { Timeline } from './components/Timeline/Timeline';

import { InputBar } from './components/InputBar/InputBar';
import { Welcome } from './components/Welcome/Welcome';
import { SettingsPanel } from './components/Settings/SettingsPanel';
import { ReportViewer } from './components/Report/ReportViewer';
import { LeaveConfirm } from './components/LeaveConfirm/LeaveConfirm';
import { BrainstormPanel } from './components/Brainstorm/BrainstormPanel';
import {
  BrainstormLoadingPlaceholder,
  BrainstormNotice,
  BrainstormSkipConfirm,
} from './components/Brainstorm/BrainstormStates';
import { TopicConfirmCard } from './components/Brainstorm/TopicConfirmCard';
import { PresetSelector } from './components/Preset/PresetSelector';
import styles from './App.module.css';

type PendingAction =
  | { kind: 'select'; sessionId: string }
  | { kind: 'new' }
  | { kind: 'delete'; sessionId: string };

const PreviewGallery = lazy(() =>
  import('./components/Brainstorm/PreviewGallery').then(module => ({
    default: module.PreviewGallery,
  })),
);

/**
 * Dev-only preview switch. URL 上带 `?preview=brainstorm` 时直接渲染 PreviewGallery，
 * 不挂载 useWebSocket / useSession，避免和后端连接产生干扰。
 */
function usePreviewMode(): string | null {
  if (typeof window === 'undefined') return null;
  const params = new URLSearchParams(window.location.search);
  return params.get('preview');
}

export function App() {
  const previewMode = usePreviewMode();
  if (previewMode === 'brainstorm') {
    return (
      <Suspense fallback={null}>
        <PreviewGallery />
      </Suspense>
    );
  }
  return <MainApp />;
}

function MainApp() {
  const ws = useWebSocket();
  const session = useSession();

  const [reports, setReports] = useState<ReportEntry[]>([]);
  const [showSettings, setShowSettings] = useState(false);
  const [viewingReport, setViewingReport] = useState<ReportEntry | null>(null);
  const [config, setConfig] = useState<DiscussionConfig>({ maxRounds: 3, model: null });
  const [historyData, setHistoryData] = useState<SessionData | null>(null);
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null);
  const [showBrainstormSkipConfirm, setShowBrainstormSkipConfirm] = useState(false);

  const timelineRef = useRef<HTMLDivElement>(null);

  // Fetch reports list
  useEffect(() => {
    fetch('/api/reports')
      .then(res => res.json())
      .then(data => setReports(data.reports ?? []))
      .catch(() => setReports([]));
  }, [ws.savedPath]);

  // Persist session data on change
  useEffect(() => {
    if (ws.currentTopic && ws.messages.length > 0) {
      session.updateSessionData({
        messages: ws.messages,
        phases: ws.phases,
        votingResult: ws.votingResult,
        blueprint: ws.blueprint,
        blueprintWarnings: ws.blueprintWarnings,
        logs: ws.logs,
        savedPath: ws.savedPath,
      });
    }
  }, [
    ws.messages,
    ws.phases,
    ws.votingResult,
    ws.blueprint,
    ws.blueprintWarnings,
    ws.logs,
    ws.savedPath,
  ]);

  // Sync to server when discussion ends
  useEffect(() => {
    if (ws.isReady && session.currentSessionId && !session.isHistoryMode) {
      const data = {
        schemaVersion: SCHEMA_VERSION,
        id: session.currentSessionId,
        topic: ws.currentTopic,
        messages: ws.messages,
        phases: ws.phases,
        votingResult: ws.votingResult,
        blueprint: ws.blueprint,
        blueprintWarnings: ws.blueprintWarnings,
        logs: ws.logs,
        savedPath: ws.savedPath,
        createdAt: Date.now(),
        updatedAt: Date.now(),
      };
      session.syncToServer(data);
    }
  }, [
    ws.isReady,
    session.currentSessionId,
    session.isHistoryMode,
    session.syncToServer,
    ws.currentTopic,
    ws.messages,
    ws.phases,
    ws.votingResult,
    ws.blueprint,
    ws.blueprintWarnings,
    ws.logs,
    ws.savedPath,
  ]);

  const handleStart = useCallback((topic: string) => {
    const sessionId = session.createSession(topic);
    setHistoryData(null);
    ws.startDiscussion(topic, config, sessionId);
  }, [ws, session, config]);

  const handleFollowup = useCallback((message: string) => {
    ws.sendFollowup(message);
  }, [ws]);

  const handleExportMarkdown = useCallback(() => {
    const topic = session.isHistoryMode && historyData ? historyData.topic : ws.currentTopic;
    const messages = session.isHistoryMode && historyData ? historyData.messages : ws.messages;
    const votingResult = session.isHistoryMode && historyData ? historyData.votingResult : ws.votingResult;
    const content = exportAsMarkdown(topic, messages, votingResult);
    downloadMarkdown(content, `${topic || 'discussion'}.md`);
  }, [
    session.isHistoryMode,
    historyData,
    ws.currentTopic,
    ws.messages,
    ws.votingResult,
  ]);

  const handleExportPdf = useCallback(() => {
    printAsPdf();
  }, []);

  const handleExportScreenshot = useCallback(async () => {
    if (timelineRef.current) {
      await captureScreenshot(timelineRef.current);
    }
  }, []);

  const handleSaveReport = useCallback(() => {
    ws.saveReport(ws.currentTopic);
  }, [ws]);

  const handleExportBlueprint = useCallback(async (format: BlueprintExportFormat) => {
    const blueprint = session.isHistoryMode ? historyData?.blueprint : ws.blueprint;
    if (!blueprint) return;
    try {
      await exportBlueprint(blueprint, format);
    } catch (error) {
      alert(`导出失败: ${error instanceof Error ? error.message : '未知错误'}`);
    }
  }, [session.isHistoryMode, historyData?.blueprint, ws.blueprint]);

  // --- Unsaved-work guard ---
  // 当前会话有内容、未保存为报告、且不是历史模式时，"离开" 需要确认
  const hasUnsavedWork = (
    !session.isHistoryMode &&
    ws.currentTopic !== '' &&
    ws.messages.length > 0 &&
    !ws.savedPath
  );

  const performAction = useCallback(async (action: PendingAction) => {
    if (action.kind === 'select') {
      const data = await session.loadHistorySessionAsync(action.sessionId);
      if (data) setHistoryData(data);
    } else if (action.kind === 'new') {
      session.startNewSession();
      setHistoryData(null);
    } else if (action.kind === 'delete') {
      session.deleteSession(action.sessionId);
    }
  }, [session]);

  const requestAction = useCallback((action: PendingAction) => {
    // Delete-current always asks; others only ask when unsaved work exists.
    const isDeletingCurrent = action.kind === 'delete' && action.sessionId === session.currentSessionId;
    if (hasUnsavedWork || isDeletingCurrent) {
      setPendingAction(action);
    } else {
      performAction(action);
    }
  }, [hasUnsavedWork, session.currentSessionId, performAction]);

  const handleSelectSession = useCallback((id: string) => {
    if (id === session.currentSessionId) return;
    requestAction({ kind: 'select', sessionId: id });
  }, [requestAction, session.currentSessionId]);

  const handleNewSession = useCallback(() => {
    requestAction({ kind: 'new' });
  }, [requestAction]);

  const handleDeleteSession = useCallback((id: string) => {
    requestAction({ kind: 'delete', sessionId: id });
  }, [requestAction]);

  // --- Confirm dialog handlers ---
  const handleConfirmSaveAndLeave = useCallback(async () => {
    if (!pendingAction) return;
    // Trigger save; pipeline will emit 'saved' event setting ws.savedPath.
    ws.saveReport(ws.currentTopic);
    // Wait briefly for save to settle, then perform the queued action.
    // (Save is fire-and-forget over WS; small delay is acceptable for UX.)
    const action = pendingAction;
    setPendingAction(null);
    setTimeout(() => performAction(action), 300);
  }, [pendingAction, ws, performAction]);

  const handleConfirmLeaveWithoutSaving = useCallback(() => {
    if (!pendingAction) return;
    const action = pendingAction;
    setPendingAction(null);
    performAction(action);
  }, [pendingAction, performAction]);

  const handleCancelLeave = useCallback(() => {
    setPendingAction(null);
  }, []);

  // Determine what to display
  const isActive = ws.currentPhase !== 'idle' && ws.currentTopic !== '';
  const isViewingHistory = session.isHistoryMode && historyData !== null;
  const showWelcome = !isActive && !isViewingHistory;

  const displayMessages = isViewingHistory ? historyData.messages : ws.messages;
  const displayTopic = isViewingHistory ? historyData.topic : ws.currentTopic;
  const displayVotingResult = isViewingHistory ? historyData.votingResult : ws.votingResult;
  const displayBlueprint = isViewingHistory ? historyData.blueprint ?? null : ws.blueprint;
  const displayBlueprintWarnings = isViewingHistory ? historyData.blueprintWarnings ?? [] : ws.blueprintWarnings;

  // Find thinking agent
  const thinkingAgent = Object.values(ws.agentStates).find(a => a.status === 'thinking')?.name ?? null;
  const showCompletionGuide = (
    isActive &&
    !isViewingHistory &&
    ws.isReady &&
    !ws.error &&
    ws.votingResult !== null
  );

  return (
    <div className={styles.layout}>
      <Sidebar
        sessions={session.sessions}
        currentSessionId={session.currentSessionId}
        reports={reports}
        onSelectSession={handleSelectSession}
        onDeleteSession={handleDeleteSession}
        onNewSession={handleNewSession}
        onSelectReport={setViewingReport}
      />

      <main className={styles.main}>
        {showWelcome ? (
          <Welcome onStart={handleStart} />
        ) : (
          <>
            <TopBar
              topic={displayTopic}
              connectionStatus={ws.connectionStatus}
              isReady={isViewingHistory || ws.isReady}
              onExportMarkdown={handleExportMarkdown}
              onExportPdf={handleExportPdf}
              onExportScreenshot={handleExportScreenshot}
              onToggleSettings={() => setShowSettings(prev => !prev)}
              onSaveReport={handleSaveReport}
              savedPath={isViewingHistory ? historyData.savedPath : ws.savedPath}
            />

            {isActive && !isViewingHistory && (
              <>
                <ProgressBar
                  currentPhase={ws.currentPhase}
                  roundProgress={ws.roundProgress}
                />
                <AgentStatusPanel
                  agents={ws.agents}
                  agentStates={ws.agentStates}
                />
              </>
            )}

            <div ref={timelineRef} style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
              <Timeline
                messages={displayMessages}
                votingResult={displayVotingResult}
                blueprint={displayBlueprint}
                blueprintWarnings={displayBlueprintWarnings}
                onExportBlueprint={handleExportBlueprint}
                thinkingAgent={isViewingHistory ? null : thinkingAgent}
              />
            </div>

            {isActive && !isViewingHistory && ws.brainstormFailure && (
              <BrainstormNotice
                state={ws.brainstormFailure}
                onDismiss={ws.dismissBrainstormFailure}
              />
            )}

            {isActive && !isViewingHistory && ws.pendingTopicRefined && (
              <TopicConfirmCard
                payload={ws.pendingTopicRefined}
                onConfirm={ws.confirmTopic}
                onRefine={ws.refineTopicAgain}
              />
            )}

            {isActive && !isViewingHistory && ws.pendingPreset && (
              <PresetSelector
                recommendation={ws.pendingPreset}
                onConfirm={ws.confirmPreset}
              />
            )}

            {isActive && !isViewingHistory && ws.pendingQuestion && (
              <BrainstormPanel
                question={ws.pendingQuestion}
                submitting={ws.isBrainstormSubmitting}
                onSubmit={ws.submitBrainstormAnswer}
                onSkip={() => setShowBrainstormSkipConfirm(true)}
              />
            )}

            {isActive &&
              !isViewingHistory &&
              ws.currentPhase === 'brainstorming' &&
              ws.isBrainstormSubmitting &&
              !ws.pendingQuestion &&
              !ws.pendingTopicRefined && (
                <BrainstormLoadingPlaceholder />
              )}

            {isActive && !isViewingHistory && ws.isReady && (
              <>
                {showCompletionGuide && (
                  <div className={styles.completionGuide}>
                    <strong>{ws.savedPath ? '方案已保存' : '方案已完成'}</strong>
                    <span>
                      认可方案可使用保存或导出按钮；需要调整时，在下方输入追问，系统会继续组织多 Agent 讨论。
                    </span>
                  </div>
                )}
                <InputBar
                  onSend={handleFollowup}
                  placeholder="输入追问或修改意见…"
                />
              </>
            )}

            {isViewingHistory && (
              <InputBar
                onSend={() => {}}
                disabled
                placeholder="历史会话仅可浏览，无法继续追问"
              />
            )}

            {ws.error && (
              <div className={styles.errorBar}>
                ⚠ {ws.error}
              </div>
            )}
          </>
        )}
      </main>

      {showSettings && (
        <SettingsPanel
          currentConfig={config}
          onApply={setConfig}
          onClose={() => setShowSettings(false)}
        />
      )}

      {viewingReport && (
        <ReportViewer
          report={viewingReport}
          onClose={() => setViewingReport(null)}
        />
      )}

      {pendingAction && (
        <LeaveConfirm
          topic={ws.currentTopic}
          messageCount={ws.messages.length}
          onSaveAndLeave={handleConfirmSaveAndLeave}
          onLeaveWithoutSaving={handleConfirmLeaveWithoutSaving}
          onCancel={handleCancelLeave}
        />
      )}

      <BrainstormSkipConfirm
        open={showBrainstormSkipConfirm}
        onCancel={() => setShowBrainstormSkipConfirm(false)}
        onConfirm={() => {
          setShowBrainstormSkipConfirm(false);
          ws.skipBrainstorm();
        }}
      />
    </div>
  );
}
