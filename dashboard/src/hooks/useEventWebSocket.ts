/**
 * useEventWebSocket — Real-time agent event WebSocket hook
 * ========================================================
 * Handles 7+ event types: ModeChanged, ToolExecutionStarted/Finished,
 * FailureDetected, CognitiveAdaptation, PlanningModeStarted, FileOpened/Modified.
 * Auto-reconnects with 3s delay, prevents duplicate connections.
 */

import { useEffect, useRef, useCallback } from 'react';
import { useUiStore } from '../stores/uiStore';
import { firePluginHook } from '../plugin/pluginRegistry';

export interface EventHandlers {
  onToolExecutionStarted?: (data: { name?: string; tool_name?: string }) => void;
  onToolExecutionFinished?: () => void;
  onFailureDetected?: (data: any) => void;
  onCognitiveAdaptation?: (data: any) => void;
  onPlanningModeStarted?: (data: any) => void;
  onFileOpened?: (data: { filepath?: string; content?: string }) => void;
  onFileModified?: (data: { filepath?: string; content?: string }) => void;
  onModeChanged?: (data: { to_mode?: string }) => void;
}

export function useEventWebSocket(handlers: EventHandlers) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const handlersRef = useRef(handlers);
  const isConnectingRef = useRef(false);
  handlersRef.current = handlers;

  const connect = useCallback(() => {
    // Prevent duplicate connections
    if (wsRef.current?.readyState === WebSocket.OPEN || wsRef.current?.readyState === WebSocket.CONNECTING) {
      return;
    }
    if (isConnectingRef.current) return;
    isConnectingRef.current = true;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.port === '5173' || window.location.port === '5174'
      ? 'localhost:8000'
      : window.location.host;
    const wsUrl = `${protocol}//${host}/v1/ws/events`;

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        isConnectingRef.current = false;
        if (reconnectTimerRef.current) {
          clearTimeout(reconnectTimerRef.current);
          reconnectTimerRef.current = null;
        }
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          const h = handlersRef.current;

          switch (msg.event) {
            case 'ModeChanged':
              h.onModeChanged?.(msg.data);
              const newMode = msg.data?.to_mode;
              if (newMode && ['interactive', 'plan', 'build'].includes(newMode)) {
                useUiStore.getState().setMode(newMode as any);
              }
              break;
            case 'ToolExecutionStarted':
              h.onToolExecutionStarted?.(msg.data);
              firePluginHook('tool:start', msg.data);
              break;
            case 'ToolExecutionFinished':
              h.onToolExecutionFinished?.();
              firePluginHook('tool:end', msg.data);
              break;
            case 'FailureDetected':
              h.onFailureDetected?.(msg.data);
              break;
            case 'CognitiveAdaptation':
              h.onCognitiveAdaptation?.(msg.data);
              break;
            case 'PlanningModeStarted':
              h.onPlanningModeStarted?.(msg.data);
              break;
            case 'FileOpened':
              h.onFileOpened?.(msg.data);
              break;
            case 'FileModified':
              h.onFileModified?.(msg.data);
              break;
            default:
              break;
          }
        } catch {
          // ignore malformed messages
        }
      };

      ws.onclose = () => {
        wsRef.current = null;
        isConnectingRef.current = false;
        if (!reconnectTimerRef.current) {
          reconnectTimerRef.current = setTimeout(() => {
            reconnectTimerRef.current = null;
            connect();
          }, 3000);
        }
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch {
      isConnectingRef.current = false;
      if (!reconnectTimerRef.current) {
        reconnectTimerRef.current = setTimeout(() => {
          reconnectTimerRef.current = null;
          connect();
        }, 3000);
      }
    }
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      isConnectingRef.current = false;
    };
  }, [connect]);
}
