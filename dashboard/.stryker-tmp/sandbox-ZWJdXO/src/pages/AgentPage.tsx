/**
 * AgentPage — AI Agent Monitoring Dashboard
 * ===========================================
 * Replaces the old Kanban board with a comprehensive monitoring dashboard:
 * real-time log streaming, task progress bars, agent status panel,
 * execution timeline, and system metrics.
 */
// @ts-nocheck


import React, { useEffect, useCallback, useState } from 'react';
import AgentMonitorPanel from '../components/Agent/AgentMonitorPanel';
import { useAgentMonitorStore } from '../stores/agentMonitorStore';
import { useEventWebSocket } from '../hooks/useEventWebSocket';
import { useUiStore } from '../stores/uiStore';
import { checkHealth, fetchSystemMetrics } from '../api/client';

const AgentPage: React.FC = () => {
  const {
    setAgentStatus, addLog, addTask, updateTaskProgress,
    addTimelineEvent, setActiveTool, updateMetrics, setUptime,
  } = useAgentMonitorStore();
  const { setSystemStatus } = useUiStore();
  const [startTime] = useState(Date.now());

  // ── WebSocket integration for real-time monitoring ──────────
  useEventWebSocket({
    onToolExecutionStarted: (data) => {
      const toolName = data?.name || data?.tool_name || 'Unknown Tool';
      setActiveTool({
        name: toolName,
        startedAt: new Date().toISOString(),
        duration: 0,
        status: 'running',
      });
      setAgentStatus('running');
      addLog({ level: 'info', source: 'Tool', message: `▶ ${toolName} 실행 시작` });
      addTimelineEvent({ type: 'tool_start', label: `🔧 ${toolName}` });
    },

    onToolExecutionFinished: () => {
      // Read tool name BEFORE clearing
      const toolName = useAgentMonitorStore.getState().activeTool?.name || 'Tool';
      setAgentStatus('idle');
      setActiveTool(null);
      addLog({ level: 'success', source: 'Tool', message: `✓ ${toolName} 완료` });
      addTimelineEvent({ type: 'tool_end', label: `✅ ${toolName}` });
    },

    onFailureDetected: (data) => {
      setAgentStatus('error');
      addLog({ level: 'error', source: 'System', message: `❌ 오류 감지: ${data?.error || data?.message || 'Unknown error'}` });
      addTimelineEvent({ type: 'error', label: '❌ Failure', detail: data?.error });
    },

    onCognitiveAdaptation: (data) => {
      setAgentStatus('thinking');
      addLog({ level: 'info', source: 'Agent', message: `🧠 적응: ${data?.reason || data?.adaptation || ''}` });
    },

    onPlanningModeStarted: (data) => {
      setAgentStatus('planning');
      addLog({ level: 'info', source: 'Agent', message: `📋 계획 모드 시작: ${data?.goal || ''}` });
      addTimelineEvent({ type: 'plan', label: '📋 계획 시작', detail: data?.goal });
    },

    onModeChanged: (data) => {
      const mode = data?.to_mode || 'interactive';
      addLog({ level: 'info', source: 'System', message: `🔄 모드 전환: ${mode.toUpperCase()}` });
      addTimelineEvent({ type: 'mode_change', label: `🔄 Mode: ${mode}` });
    },
  });

  // ── Poll system metrics ─────────────────────────────────────
  useEffect(() => {
    const poll = async () => {
      try {
        const health = await checkHealth();
        setSystemStatus({
          healthy: health.status === 'ok',
          backends: health.backends || {},
        });

        const metrics = await fetchSystemMetrics();
        if (metrics.ok) {
          updateMetrics({
            memoryMb: metrics.memory_mb,
            cpuPercent: metrics.cpu_percent,
            totalTokens: metrics.total_tokens,
          });
        }

        // Update uptime
        setUptime(Math.floor((Date.now() - startTime) / 1000));
      } catch {
        // silent
      }
    };

    poll();
    const interval = setInterval(poll, 5000);
    const uptimeInterval = setInterval(() => {
      setUptime(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);

    return () => {
      clearInterval(interval);
      clearInterval(uptimeInterval);
    };
  }, []);

  return (
    <div className="page-container full-height-page agent-page">
      <div className="page-header">
        <div className="flex items-center gap-md">
          <div>
            <h2>🤖 에이전트 모니터링 <span>Agent Dashboard</span></h2>
            <p className="page-subtitle">AI 에이전트의 실시간 상태, 로그 스트림, 작업 진행 상황을 모니터링합니다.</p>
          </div>
        </div>
      </div>
      <AgentMonitorPanel />
    </div>
  );
};

export default AgentPage;
