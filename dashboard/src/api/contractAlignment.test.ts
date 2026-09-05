import { describe, expect, it } from 'vitest';
import { z } from 'zod';
import {
  WorkspaceContextSchema,
  SystemQuotaSchema,
  McpServersResponseSchema,
  AccessModeResponseSchema,
  ProjectListResponseSchema,
  LocalModelsResponseSchema,
} from './clientSchema';

/* ─── WebSocket Event Contract ───────────────────────────────────────────
 * /v1/ws/events (src/antigravity_k/api/routes/events.py)가 전달하는 이벤트
 * 페이로드 계약 — useEventWebSocket.ts의 eventMessageSchema와 동일한 형태로
 * 백엔드 발행자(mode_manager / tool_loop / tool_executor / cognitive_loop)가
 * 보내는 실제 데이터를 문서화·고정한다.
 * 발행자별 계약:
 *   - ModeChanged            → mode_manager._publish_to_eventbus: from_mode/to_mode/reason/timestamp
 *   - ToolExecutionStarted   → tool_loop._publish_event: name=tool_name
 *   - ToolExecutionFinished  → tool_loop._publish_event: name=tool_name
 *   - FailureDetected        → tool_executor._broadcast_failure_event: tool/error/message
 *   - CognitiveAdaptation    → cognitive_loop._publish_cognitive_adaptation: reason/adaptation
 *   - PlanningModeStarted    → mode_manager._publish_planning_started: goal
 *   - ApprovalRequired       → tool_executor._broadcast_approval_required: tool/request_id/reason
 *   - AgentTurnStarted/Ended → event_bus HOOK_KIND_TO_EVENT_NAME 브릿지: role/task_type
 *   - QualityCheckPassed/Failed → tool_loop._publish_quality_event: task_type/score/grade/issues/feedback
 *   - AntiPatternsDetected   → cognitive_loop._publish_anti_patterns: reason/tools/patterns
 *   - FileOpened/FileModified→ tool_executor._broadcast_file_event: filepath/content
 * ──────────────────────────────────────────────────────────────────────── */
const wsEventSchema = z.discriminatedUnion('event', [
  z.object({
    event: z.literal('ModeChanged'),
    data: z.object({ from_mode: z.string().optional(), to_mode: z.string().optional(), reason: z.string().optional() }),
  }),
  z.object({ event: z.literal('ToolExecutionStarted'), data: z.object({ name: z.string().optional() }) }),
  z.object({ event: z.literal('ToolExecutionFinished'), data: z.record(z.string(), z.unknown()) }),
  z.object({
    event: z.literal('FailureDetected'),
    data: z.object({ tool: z.string().optional(), error: z.string().optional(), message: z.string().optional() }),
  }),
  z.object({
    event: z.literal('CognitiveAdaptation'),
    data: z.object({ reason: z.string().optional(), adaptation: z.string().optional() }),
  }),
  z.object({ event: z.literal('PlanningModeStarted'), data: z.object({ goal: z.string().optional() }) }),
  z.object({
    event: z.literal('ApprovalRequired'),
    data: z.object({ tool: z.string().optional(), request_id: z.string().optional(), reason: z.string().optional() }),
  }),
  z.object({
    event: z.literal('AgentTurnStarted'),
    data: z.object({ role: z.string().optional(), task_type: z.string().optional() }),
  }),
  z.object({
    event: z.literal('AgentTurnEnded'),
    data: z.object({ role: z.string().optional(), task_type: z.string().optional() }),
  }),
  z.object({
    event: z.literal('QualityCheckPassed'),
    data: z.object({
      task_type: z.string().optional(),
      grade: z.string().optional(),
      score: z.union([z.number(), z.string()]).optional(),
      issues: z.array(z.string()).optional(),
    }),
  }),
  z.object({
    event: z.literal('QualityCheckFailed'),
    data: z.object({
      task_type: z.string().optional(),
      grade: z.string().optional(),
      score: z.union([z.number(), z.string()]).optional(),
      issues: z.array(z.string()).optional(),
      feedback: z.string().nullable().optional(),
    }),
  }),
  z.object({
    event: z.literal('AntiPatternsDetected'),
    data: z.object({ reason: z.string().optional(), tools: z.array(z.string()).optional(), patterns: z.array(z.string()).optional() }),
  }),
  z.object({
    event: z.literal('FileOpened'),
    data: z.object({ filepath: z.string().optional(), content: z.string().optional() }),
  }),
  z.object({
    event: z.literal('FileModified'),
    data: z.object({ filepath: z.string().optional(), content: z.string().optional() }),
  }),
]);

/* 프론트엔드가 소비하는 WS 이벤트 이름 — 백엔드 events.py의 events_to_track이
 * 이 목록을 모두 구독해야 한다 (tests/test_events.py 계약 테스트와 쌍). */
export const FRONTEND_WS_EVENT_NAMES = [
  'ModeChanged',
  'ToolExecutionStarted',
  'ToolExecutionFinished',
  'FailureDetected',
  'CognitiveAdaptation',
  'PlanningModeStarted',
  'ApprovalRequired',
  'AgentTurnStarted',
  'AgentTurnEnded',
  'QualityCheckPassed',
  'QualityCheckFailed',
  'AntiPatternsDetected',
  'FileOpened',
  'FileModified',
];

describe('Frontend-Backend Contract Alignment Tests', () => {
  describe('WorkspaceContextSchema', () => {
    it('successfully parses valid backend response from GET /api/workspace/context', () => {
      const backendPayload = {
        project_name: 'Ssak-Ai',
        target: '로컬',
        branch: 'codex/m1-task-events',
        projects: [
          {
            name: 'Ssak-Ai',
            preview: 'main active branch',
            tasks: ['task 1', 'task 2'],
          },
        ],
      };

      const result = WorkspaceContextSchema.safeParse(backendPayload);
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.project_name).toBe('Ssak-Ai');
        expect(result.data.target).toBe('로컬');
        expect(result.data.branch).toBe('codex/m1-task-events');
        expect(result.data.projects).toHaveLength(1);
      }
    });

    it('falls back to defaults when optional fields are omitted', () => {
      const emptyPayload = {};
      const result = WorkspaceContextSchema.safeParse(emptyPayload);
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.project_name).toBe('Ssak-Ai');
        expect(result.data.target).toBe('로컬');
        expect(result.data.branch).toBe('main');
        expect(result.data.projects).toEqual([]);
      }
    });
  });

  describe('ProjectListResponseSchema', () => {
    it('successfully parses real projects response from GET /api/projects', () => {
      const backendPayload = {
        ok: true,
        workspace: '/Users/mr.k/program/coding/ssak_comp/Ssak-Ai',
        current_project: {
          id: 'default',
          name: 'Ssak-Ai',
          path: '/Users/mr.k/program/coding/ssak_comp/Ssak-Ai',
          is_active: true,
          tasks: ['Task 1', 'Task 2'],
        },
        projects: [
          {
            id: 'default',
            name: 'Ssak-Ai',
            path: '/Users/mr.k/program/coding/ssak_comp/Ssak-Ai',
            is_active: true,
            tasks: ['Task 1', 'Task 2'],
          },
        ],
      };

      const result = ProjectListResponseSchema.safeParse(backendPayload);
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.ok).toBe(true);
        expect(result.data.projects).toHaveLength(1);
        expect(result.data.projects[0].is_active).toBe(true);
      }
    });
  });

  describe('LocalModelsResponseSchema', () => {
    it('successfully parses real local models response from GET /api/models/local', () => {
      const backendPayload = {
        ok: true,
        total: 2,
        recommended_default: 'qwen3.8',
        models: [
          {
            id: 'qwen3.8',
            name: 'Qwen 3.8 27B',
            provider: 'ollama',
            role: 'reasoning',
            parameter_count_b: 27.0,
            is_local: true,
            status: 'running',
            disk_path: '',
            disk_size_gb: 0.0,
            quantization: '',
            description: 'Qwen3.8 27B (Ollama / Local)',
          },
          {
            id: 'Qwen3.8-27B-UD-Q8_K_XL',
            name: 'Qwen3.8-27B-UD-Q8_K_XL',
            provider: 'unsloth',
            role: 'reasoning',
            parameter_count_b: 27.0,
            is_local: true,
            status: 'cached',
            disk_path: '/path/to/blob',
            disk_size_gb: 29.3,
            quantization: 'UD-Q8_K_XL',
            description: 'Qwen3.8 27B (Unsloth GGUF)',
          },
        ],
        message: '본 PC에서 2개의 로컬 모델이 감지되었습니다.',
      };

      const result = LocalModelsResponseSchema.safeParse(backendPayload);
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.ok).toBe(true);
        expect(result.data.total).toBe(2);
        expect(result.data.recommended_default).toBe('qwen3.8');
        expect(result.data.models).toHaveLength(2);
        expect(result.data.models[0].is_local).toBe(true);
        expect(result.data.models[0].status).toBe('running');
        expect(result.data.models[1].provider).toBe('unsloth');
        expect(result.data.models[1].disk_size_gb).toBe(29.3);
      }
    });
  });

  describe('SystemQuotaSchema', () => {
    it('successfully parses valid backend response from GET /api/system/quota', () => {
      const backendPayload = {
        percent_remaining: 85.5,
        period_label: '이번 주',
        resets_note: '매주 월요일 초기화 (KST)',
        tokens_used: 145000,
        tokens_budget: 1000000,
        requests: 42,
      };

      const result = SystemQuotaSchema.safeParse(backendPayload);
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.percent_remaining).toBe(85.5);
        expect(result.data.tokens_used).toBe(145000);
        expect(result.data.tokens_budget).toBe(1000000);
      }
    });

    it('rejects invalid quota values (e.g. negative percent)', () => {
      const invalidPayload = {
        percent_remaining: -5,
        period_label: '이번 주',
        resets_note: '매주 월요일 초기화',
        tokens_used: 0,
        tokens_budget: 1000,
      };

      const result = SystemQuotaSchema.safeParse(invalidPayload);
      expect(result.success).toBe(false);
    });
  });

  describe('McpServersResponseSchema', () => {
    it('successfully parses valid backend response from GET /api/mcp/servers', () => {
      const backendPayload = {
        ok: true,
        servers: [
          {
            name: 'codebase-memory-mcp',
            transport: 'stdio',
            status: 'connected',
            command: 'uvx codebase-memory-mcp',
          },
          {
            name: 'fetch-mcp',
            transport: 'stdio',
            status: 'ready',
          },
        ],
        source: 'mcp_registry',
      };

      const result = McpServersResponseSchema.safeParse(backendPayload);
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.ok).toBe(true);
        expect(result.data.servers).toHaveLength(2);
        expect(result.data.servers[0].name).toBe('codebase-memory-mcp');
        expect(result.data.source).toBe('mcp_registry');
      }
    });

    it('defaults servers to empty list when empty', () => {
      const emptyPayload = { ok: true };
      const result = McpServersResponseSchema.safeParse(emptyPayload);
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.servers).toEqual([]);
      }
    });
  });

  describe('WebSocket Event Contract (/v1/ws/events)', () => {
    it('parses every backend publisher payload shape', () => {
      const backendPayloads = [
        {
          event: 'ModeChanged',
          data: { from_mode: 'interactive', to_mode: 'plan', reason: '사용자 요청', timestamp: '2026-09-04T00:00:00Z' },
        },
        { event: 'ToolExecutionStarted', data: { name: 'read_file' } },
        { event: 'ToolExecutionFinished', data: { name: 'read_file' } },
        { event: 'FailureDetected', data: { tool: 'run_bash_command', error: 'exit_code=2', message: '실행 실패' } },
        { event: 'CognitiveAdaptation', data: { reason: '반복 실패 감지', adaptation: '전략 변경 필요' } },
        { event: 'PlanningModeStarted', data: { goal: '프로젝트 분석 계획' } },
        { event: 'ApprovalRequired', data: { tool: 'write_file', request_id: 'req-123', reason: 'write_file 실행 승인' } },
        { event: 'AgentTurnStarted', data: { role: 'WORKER', task_type: 'refactor' } },
        { event: 'AgentTurnEnded', data: { role: 'WORKER', task_type: 'refactor' } },
        {
          event: 'QualityCheckPassed',
          data: { task_type: 'code', grade: 'good', score: 0.85, issues: [] },
        },
        {
          event: 'QualityCheckFailed',
          data: { task_type: 'plan', grade: 'retry', score: 0.4, issues: ['불명확'], feedback: '보완 필요' },
        },
        {
          event: 'AntiPatternsDetected',
          data: { reason: '반복 실패 감지', tools: ['run_bash_command'], patterns: ['timeout 발생'] },
        },
        { event: 'FileOpened', data: { filepath: '/repo/a.py', content: 'print(1)' } },
        { event: 'FileModified', data: { filepath: '/repo/a.py', content: 'print(2)' } },
      ];
      for (const payload of backendPayloads) {
        expect(wsEventSchema.safeParse(payload).success, JSON.stringify(payload)).toBe(true);
      }
    });

    it('exposes the full frontend-consumed event name list', () => {
      expect(FRONTEND_WS_EVENT_NAMES).toEqual([
        'ModeChanged',
        'ToolExecutionStarted',
        'ToolExecutionFinished',
        'FailureDetected',
        'CognitiveAdaptation',
        'PlanningModeStarted',
        'ApprovalRequired',
        'AgentTurnStarted',
        'AgentTurnEnded',
        'QualityCheckPassed',
        'QualityCheckFailed',
        'AntiPatternsDetected',
        'FileOpened',
        'FileModified',
      ]);
    });
  });

  describe('AccessModeResponseSchema', () => {
    it('successfully parses valid responses from GET/POST /api/system/access-mode', () => {
      const fullAccessPayload = {
        ok: true,
        mode: 'full_access',
        label: '전체 액세스',
        message: '전체 액세스 모드가 적용되었습니다.',
      };
      const readOnlyPayload = {
        ok: true,
        mode: 'read_only',
        label: '읽기 전용',
        message: '읽기 전용 모드가 적용되었습니다.',
      };

      const fullResult = AccessModeResponseSchema.safeParse(fullAccessPayload);
      const roResult = AccessModeResponseSchema.safeParse(readOnlyPayload);

      expect(fullResult.success).toBe(true);
      expect(roResult.success).toBe(true);
      if (fullResult.success && roResult.success) {
        expect(fullResult.data.mode).toBe('full_access');
        expect(roResult.data.mode).toBe('read_only');
      }
    });
  });
});
