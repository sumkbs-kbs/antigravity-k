/**
 * useEventWebSocket — Real-time agent event WebSocket hook
 * ========================================================
 * Handles 7+ event types: ModeChanged, ToolExecutionStarted/Finished,
 * FailureDetected, CognitiveAdaptation, PlanningModeStarted, FileOpened/Modified.
 * Auto-reconnects with 3s delay, prevents duplicate connections.
 */

import { useEffect, useRef } from 'react';
import { z } from 'zod';
import { useUiStore } from '../stores/uiStore';
import { firePluginHook } from '../plugin/pluginRegistry';
import { readStoredAccessToken } from '../utils/accessPinCredential';

const executionModeSchema = z.enum(['interactive', 'plan', 'build']);
const eventObjectSchema = z.object({}).catchall(z.unknown()).readonly();
const toolExecutionDataSchema = z.object({
  name: z.string().optional(),
  tool_name: z.string().optional(),
}).catchall(z.unknown()).readonly();
const failureDataSchema = z.object({
  error: z.string().optional(),
  message: z.string().optional(),
}).catchall(z.unknown()).readonly();
const cognitiveAdaptationDataSchema = z.object({
  reason: z.string().optional(),
  adaptation: z.string().optional(),
}).catchall(z.unknown()).readonly();
const planningModeDataSchema = z.object({
  goal: z.string().optional(),
}).catchall(z.unknown()).readonly();
const fileEventDataSchema = z.object({
  filepath: z.string().optional(),
  content: z.string().optional(),
}).catchall(z.unknown()).readonly();
const modeChangedDataSchema = z.object({
  from_mode: executionModeSchema.optional(),
  to_mode: executionModeSchema.optional(),
  reason: z.string().optional(),
  timestamp: z.string().optional(),
}).catchall(z.unknown()).readonly();

const eventMessageSchema = z.discriminatedUnion('event', [
  z.object({ event: z.literal('ModeChanged'), data: modeChangedDataSchema }).readonly(),
  z.object({ event: z.literal('ToolExecutionStarted'), data: toolExecutionDataSchema }).readonly(),
  z.object({ event: z.literal('ToolExecutionFinished'), data: eventObjectSchema }).readonly(),
  z.object({ event: z.literal('FailureDetected'), data: failureDataSchema }).readonly(),
  z.object({ event: z.literal('CognitiveAdaptation'), data: cognitiveAdaptationDataSchema }).readonly(),
  z.object({ event: z.literal('PlanningModeStarted'), data: planningModeDataSchema }).readonly(),
  z.object({ event: z.literal('FileOpened'), data: fileEventDataSchema }).readonly(),
  z.object({ event: z.literal('FileModified'), data: fileEventDataSchema }).readonly(),
]);

type ToolExecutionData = z.infer<typeof toolExecutionDataSchema>;
type FailureData = z.infer<typeof failureDataSchema>;
type CognitiveAdaptationData = z.infer<typeof cognitiveAdaptationDataSchema>;
type PlanningModeData = z.infer<typeof planningModeDataSchema>;
type FileEventData = z.infer<typeof fileEventDataSchema>;
type ModeChangedData = z.infer<typeof modeChangedDataSchema>;
type EventMessage = z.infer<typeof eventMessageSchema>;

function assertNever(message: never): never {
  throw new TypeError(`Unsupported event message: ${JSON.stringify(message)}`);
}

export type EventHandlers = Readonly<{
  onToolExecutionStarted?: (data: ToolExecutionData) => void;
  onToolExecutionFinished?: () => void;
  onFailureDetected?: (data: FailureData) => void;
  onCognitiveAdaptation?: (data: CognitiveAdaptationData) => void;
  onPlanningModeStarted?: (data: PlanningModeData) => void;
  onFileOpened?: (data: FileEventData) => void;
  onFileModified?: (data: FileEventData) => void;
  onModeChanged?: (data: ModeChangedData) => void;
}>;

function dispatchEventMessage(message: EventMessage, handlers: EventHandlers): void {
  switch (message.event) {
    case 'ModeChanged':
      handlers.onModeChanged?.(message.data);
      if (message.data.to_mode !== undefined) {
        useUiStore.getState().setMode(message.data.to_mode);
      }
      return;
    case 'ToolExecutionStarted':
      handlers.onToolExecutionStarted?.(message.data);
      firePluginHook('tool:start', message.data);
      return;
    case 'ToolExecutionFinished':
      handlers.onToolExecutionFinished?.();
      firePluginHook('tool:end', message.data);
      return;
    case 'FailureDetected':
      handlers.onFailureDetected?.(message.data);
      return;
    case 'CognitiveAdaptation':
      handlers.onCognitiveAdaptation?.(message.data);
      return;
    case 'PlanningModeStarted':
      handlers.onPlanningModeStarted?.(message.data);
      return;
    case 'FileOpened':
      handlers.onFileOpened?.(message.data);
      return;
    case 'FileModified':
      handlers.onFileModified?.(message.data);
      return;
    default:
      return assertNever(message);
  }
}

export function useEventWebSocket(handlers: EventHandlers) {
  const handlersRef = useRef(handlers);
  useEffect(() => {
    handlersRef.current = handlers;
  }, [handlers]);

  useEffect(() => {
    let socket: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let isConnecting = false;
    let isDisposed = false;

    function scheduleReconnect(): void {
      if (isDisposed || reconnectTimer !== null) return;
      reconnectTimer = setTimeout(() => {
        reconnectTimer = null;
        connect();
      }, 3000);
    }

    function connect(): void {
      if (isDisposed || isConnecting) return;
      if (socket?.readyState === WebSocket.OPEN || socket?.readyState === WebSocket.CONNECTING) return;
      isConnecting = true;

      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = window.location.port === '5173' || window.location.port === '5174'
        ? 'localhost:8000'
        : window.location.host;
      const wsUrl = new URL(`${protocol}//${host}/v1/ws/events`);
      const accessToken = readStoredAccessToken();

      try {
        const nextSocket = accessToken === null
          ? new WebSocket(wsUrl)
          : new WebSocket(wsUrl, [`bearer.${accessToken}`]);
        socket = nextSocket;

        nextSocket.onopen = () => {
          isConnecting = false;
          if (reconnectTimer !== null) {
            clearTimeout(reconnectTimer);
            reconnectTimer = null;
          }
        };

        nextSocket.onmessage = (event) => {
          let rawMessage: unknown;
          try {
            rawMessage = JSON.parse(event.data);
          } catch {
            return;
          }

          const parsedMessage = eventMessageSchema.safeParse(rawMessage);
          if (!parsedMessage.success) return;
          dispatchEventMessage(parsedMessage.data, handlersRef.current);
        };

        nextSocket.onclose = () => {
          if (socket === nextSocket) socket = null;
          isConnecting = false;
          scheduleReconnect();
        };

        nextSocket.onerror = () => {
          nextSocket.close();
        };
      } catch {
        isConnecting = false;
        scheduleReconnect();
      }
    }

    connect();
    return () => {
      isDisposed = true;
      if (reconnectTimer !== null) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      if (socket !== null) {
        socket.onclose = null;
        socket.close();
        socket = null;
      }
      isConnecting = false;
    };
  }, []);
}
