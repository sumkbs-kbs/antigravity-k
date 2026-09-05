import { z } from 'zod';

export const ModelInfoSchema = z.object({
  id: z.string(),
  role: z.string().optional(),
  description: z.string().optional(),
}).passthrough();

export const ModelListResponseSchema = z.object({
  data: z.array(ModelInfoSchema).default([]),
}).passthrough();

export const ModelProviderCapabilitySchema = z.object({
  model: z.string(),
  provider: z.string(),
  is_local: z.boolean(),
  runtime_status: z.enum(['available', 'unavailable', 'not_required']),
  native_tool_calling: z.enum(['supported', 'unsupported', 'unknown']),
  source: z.string(),
  detail: z.string().optional(),
  reported_capabilities: z.array(z.string()).optional(),
  long_context: z.object({
    strategy: z.enum(['native', 'retrieval_fallback', 'unavailable']),
    native_sparse_attention: z.enum(['supported', 'unsupported', 'unknown']),
    native_linear_attention: z.enum(['supported', 'unsupported', 'unknown']),
    kv_cache_compression: z.enum(['supported', 'unsupported', 'unknown']),
  }).optional(),
  long_context_plan: z.object({
    strategy: z.enum(['native', 'retrieval_fallback', 'unavailable']),
    retrieval_mode: z.enum(['native', 'long_context']),
    native_attention_enabled: z.boolean(),
    kv_cache_compression_enabled: z.boolean(),
    kv_cache_mode: z.enum(['backend_managed', 'bounded_context', 'unavailable']),
    context_token_limit: z.number(),
    candidate_pool: z.number(),
    rationale: z.string(),
  }).optional(),
});

export const ModelOperationalMetricSchema = z.object({
  model: z.string(),
  outcome_count: z.number(),
  task_success_rate: z.number().nullable(),
  tool_accuracy: z.number().nullable(),
  retry_rate: z.number().nullable(),
});

export const ModelQualityCalibrationStatusSchema = z.object({
  enabled: z.boolean(),
  eligible_models: z.array(z.string()),
  ineligible_models: z.array(z.string()),
  operational_metrics: z.array(ModelOperationalMetricSchema),
});

export const ModelOperationsStatusSchema = z.object({
  provider_capabilities: z.record(z.string(), ModelProviderCapabilitySchema),
  quality_calibration: ModelQualityCalibrationStatusSchema,
});

export const HealthStatusSchema = z.object({
  status: z.string(),
  version: z.string().optional(),
  backends: z.union([z.record(z.string(), z.unknown()), z.array(z.unknown())]).optional(),
  rag_index_files: z.number().optional(),
  cov_active: z.boolean().optional(),
  daily_spend_usd: z.number().optional(),
  daily_budget_usd: z.number().optional(),
});

export const SystemMetricsSchema = z.object({
  ok: z.boolean(),
  status: z.string().optional(),
  memory_mb: z.number().optional(),
  cpu_percent: z.number().optional(),
  total_tokens: z.number().optional(),
  uptime_seconds: z.number().optional(),
  version: z.string().optional(),
});

export const CacheEntrySchema = z.object({
  key: z.string(),
  ttl: z.number(),
  age: z.number(),
  remaining_ttl: z.number(),
  tags: z.array(z.string()),
  hits: z.number(),
});

export const CacheStatsSchema = z.object({
  total_entries: z.number(),
  total_tags: z.number(),
  hits: z.number(),
  misses: z.number(),
  hit_ratio: z.number(),
  memory_estimate_kb: z.number(),
  entries: z.array(CacheEntrySchema),
});

export const CacheStatsResponseSchema = z.discriminatedUnion('ok', [
  z.object({ ok: z.literal(true), stats: CacheStatsSchema }),
  z.object({ ok: z.literal(false), error: z.string() }),
]);

// ─── Session Disclosure (세션 한도 고지, freebuff 벤치마킹) ──────────

export const DisclosureLevelSchema = z.enum(['healthy', 'warning', 'exhausted']);

export const LimitDisclosureSchema = z.object({
  kind: z.string(),
  label: z.string(),
  limit: z.number(),
  used: z.number(),
  remaining: z.number(),
  usage_percent: z.number(),
  level: DisclosureLevelSchema,
  message: z.string(),
  reset_at: z.string().optional(),
  seconds_until_reset: z.number().optional(),
});

export const SessionDisclosureSchema = z.object({
  level: DisclosureLevelSchema,
  reset_date: z.string(),
  reset_at: z.string().optional(),
  seconds_until_reset: z.number().optional(),
  notices: z.array(z.string()),
  limits: z.array(LimitDisclosureSchema),
  markdown: z.string(),
});

export type DisclosureLevel = z.infer<typeof DisclosureLevelSchema>;
export type LimitDisclosure = z.infer<typeof LimitDisclosureSchema>;
export type SessionDisclosure = z.infer<typeof SessionDisclosureSchema>;

export const LogLevelInfoSchema = z.object({
  name: z.string(),
  level: z.number(),
  level_name: z.string(),
  effective_level: z.number(),
  effective_level_name: z.string(),
  handlers: z.number(),
});

export const LogLevelListResponseSchema = z.object({
  ok: z.boolean(),
  loggers: z.array(LogLevelInfoSchema),
  debug_mode: z.boolean(),
  count: z.number(),
  error: z.string().optional(),
});

export const LogLevelSetResultSchema = z.object({
  name: z.string(),
  previous_level: z.number(),
  current_level: z.number(),
  previous_level_name: z.string(),
  current_level_name: z.string(),
});

export const LogLevelSetResponseSchema = z.discriminatedUnion('ok', [
  z.object({ ok: z.literal(true), result: LogLevelSetResultSchema }),
  z.object({ ok: z.literal(false), error: z.string() }),
]);

export const SetAllLogLevelsResultSchema = z.object({
  target_level: z.number(),
  target_level_name: z.string(),
  updated_count: z.number(),
  loggers: z.array(LogLevelSetResultSchema),
});

export const SetAllLogLevelsResponseSchema = z.discriminatedUnion('ok', [
  z.object({ ok: z.literal(true), result: SetAllLogLevelsResultSchema }),
  z.object({ ok: z.literal(false), error: z.string() }),
]);

export const DebugModeResultSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  updated_count: z.number().optional(),
  restored_count: z.number().optional(),
});

export const DebugModeResponseSchema = z.discriminatedUnion('ok', [
  z.object({
    ok: z.literal(true),
    debug_mode: z.boolean(),
    result: DebugModeResultSchema,
  }),
  z.object({
    ok: z.literal(false),
    error: z.string(),
    debug_mode: z.boolean().optional(),
  }),
]);

export const SettingsDataSchema = z.object({
  api_keys: z.record(z.string(), z.string()).optional(),
  server: z.object({
    host: z.string().optional(),
    port: z.union([z.string(), z.number()]).optional(),
  }).optional(),
  model: z.object({
    provider: z.string().optional(),
    name: z.string().optional(),
  }).optional(),
}).passthrough();

export const SettingsResponseSchema = z.object({
  settings: SettingsDataSchema,
});

export const SettingsSaveResponseSchema = z.discriminatedUnion('ok', [
  z.object({
    ok: z.literal(true),
    updated: z.number(),
    message: z.string(),
  }),
  z.object({
    ok: z.literal(false),
    error: z.string().optional(),
    detail: z.string().optional(),
  }),
]);

export const ChatCompletionChunkSchema = z.object({
  choices: z.array(z.object({
    delta: z.object({
      content: z.string().optional(),
    }),
  })),
});

export type ModelInfo = z.infer<typeof ModelInfoSchema>;
export type ModelProviderCapability = z.infer<typeof ModelProviderCapabilitySchema>;
export type ModelOperationalMetric = z.infer<typeof ModelOperationalMetricSchema>;
export type ModelQualityCalibrationStatus = z.infer<typeof ModelQualityCalibrationStatusSchema>;
export type ModelOperationsStatus = z.infer<typeof ModelOperationsStatusSchema>;
export type HealthStatus = z.infer<typeof HealthStatusSchema>;
export type SystemMetrics = z.infer<typeof SystemMetricsSchema>;
export type CacheStats = z.infer<typeof CacheStatsSchema>;
export type CacheStatsResponse = z.infer<typeof CacheStatsResponseSchema>;
export type LogLevelInfo = z.infer<typeof LogLevelInfoSchema>;
export type LogLevelListResponse = z.infer<typeof LogLevelListResponseSchema>;
export type LogLevelSetResult = z.infer<typeof LogLevelSetResultSchema>;
export type LogLevelSetResponse = z.infer<typeof LogLevelSetResponseSchema>;
export type SetAllLogLevelsResult = z.infer<typeof SetAllLogLevelsResultSchema>;
export type SetAllLogLevelsResponse = z.infer<typeof SetAllLogLevelsResponseSchema>;
export type DebugModeResult = z.infer<typeof DebugModeResultSchema>;
export type DebugModeResponse = z.infer<typeof DebugModeResponseSchema>;
export type SettingsData = z.infer<typeof SettingsDataSchema>;
export type SettingsResponse = z.infer<typeof SettingsResponseSchema>;
export type SettingsSaveResponse = z.infer<typeof SettingsSaveResponseSchema>;

/* ─── Desktop & Workspace Contract Schemas ─────────────────────── */
export const ProjectRecordSchema = z.object({
  id: z.string().default('default'),
  name: z.string(),
  path: z.string().default(''),
  is_active: z.boolean().default(false),
  last_accessed_at: z.string().optional(),
  tasks: z.array(z.string()).default([]),
  preview: z.string().optional(),
}).passthrough();

export const ProjectListResponseSchema = z.object({
  ok: z.boolean(),
  workspace: z.string().default(''),
  current_project: ProjectRecordSchema.optional(),
  projects: z.array(ProjectRecordSchema).default([]),
}).passthrough();

export const WorkspaceContextSchema = z.object({
  project_name: z.string().default('Ssak-Ai'),
  workspace_path: z.string().optional(),
  target: z.string().default('로컬'),
  branch: z.string().default('main'),
  projects: z.array(ProjectRecordSchema).default([]),
}).passthrough();

export const SystemQuotaSchema = z.object({
  percent_remaining: z.number().min(0).max(100),
  period_label: z.string(),
  resets_note: z.string(),
  tokens_used: z.number().nonnegative(),
  tokens_budget: z.number().positive(),
  requests: z.number().nonnegative().optional(),
}).passthrough();

export const McpServerItemSchema = z.object({
  name: z.string(),
  transport: z.string().default('stdio'),
  status: z.string().default('connected'),
  command: z.string().optional(),
}).passthrough();

export const McpServersResponseSchema = z.object({
  ok: z.boolean(),
  servers: z.array(McpServerItemSchema).default([]),
  source: z.string().optional(),
  error: z.string().optional(),
}).passthrough();

export const AccessModeResponseSchema = z.object({
  ok: z.boolean().optional(),
  mode: z.string(),
  label: z.string(),
  message: z.string().optional(),
  error: z.string().optional(),
}).passthrough();

export type ProjectRecord = z.infer<typeof ProjectRecordSchema>;
export type ProjectListResponse = z.infer<typeof ProjectListResponseSchema>;
export type WorkspaceContext = z.infer<typeof WorkspaceContextSchema>;
export type SystemQuota = z.infer<typeof SystemQuotaSchema>;
export type McpServerItem = z.infer<typeof McpServerItemSchema>;
export type McpServersResponse = z.infer<typeof McpServersResponseSchema>;

export const McpHealthEntrySchema = z.object({
  name: z.string(),
  transport: z.string().default('stdio'),
  status: z.enum(['healthy', 'error', 'blocked', 'configured', 'unknown']).or(z.string()).default('unknown'),
  tool_count: z.number().nonnegative().default(0),
  tools: z.array(z.string()).default([]),
  error: z.string().nullable().optional(),
  initialized: z.boolean().default(false),
  checked_at: z.number().nullable().optional(),
  latency_ms: z.number().nullable().optional(),
  source: z.string().optional(),
  command: z.string().optional(),
}).passthrough();

export const McpHealthSummarySchema = z.object({
  total: z.number().nonnegative().default(0),
  healthy: z.number().nonnegative().default(0),
  error: z.number().nonnegative().default(0),
  blocked: z.number().nonnegative().default(0),
  configured: z.number().nonnegative().default(0),
  unknown: z.number().nonnegative().default(0),
}).passthrough();

export const McpHealthResponseSchema = z.object({
  ok: z.boolean(),
  servers: z.array(McpHealthEntrySchema).default([]),
  summary: McpHealthSummarySchema.default({
    total: 0,
    healthy: 0,
    error: 0,
    blocked: 0,
    configured: 0,
    unknown: 0,
  }),
  source: z.string().optional(),
  probed_at: z.number().nullable().optional(),
  error: z.string().optional(),
}).passthrough();

export type McpHealthEntry = z.infer<typeof McpHealthEntrySchema>;
export type McpHealthSummary = z.infer<typeof McpHealthSummarySchema>;
export type McpHealthResponse = z.infer<typeof McpHealthResponseSchema>;

export const McpOAuthServerStatusSchema = z.object({
  name: z.string(),
  transport: z.string().default('stdio'),
  url: z.string().optional().default(''),
  supports_oauth: z.boolean().default(false),
  auth_type: z.string().optional().default(''),
  connected: z.boolean().default(false),
  has_client_id: z.boolean().optional().default(false),
  status: z.object({
    server_name: z.string().optional(),
    connected: z.boolean().optional(),
    token_type: z.string().optional(),
    expires_at: z.number().nullable().optional(),
    scope: z.string().nullable().optional(),
    resource: z.string().nullable().optional(),
    has_refresh_token: z.boolean().optional(),
    obtained_at: z.number().optional(),
    expired: z.boolean().optional(),
  }).nullable().optional(),
}).passthrough();

export const McpOAuthStatusResponseSchema = z.object({
  ok: z.boolean(),
  servers: z.array(McpOAuthServerStatusSchema).default([]),
  source: z.string().optional(),
  summary: z.object({
    total: z.number().nonnegative().default(0),
    oauth_capable: z.number().nonnegative().default(0),
    connected: z.number().nonnegative().default(0),
  }).passthrough().default({ total: 0, oauth_capable: 0, connected: 0 }),
  error: z.string().optional(),
}).passthrough();

export const McpOAuthStartResponseSchema = z.object({
  ok: z.boolean(),
  server_name: z.string().optional(),
  authorization_url: z.string().optional(),
  state: z.string().optional(),
  redirect_uri: z.string().optional(),
  resource: z.string().optional(),
  authorization_server: z.string().optional(),
  scope: z.string().nullable().optional(),
  client_id: z.string().optional(),
  expires_in_seconds: z.number().optional(),
  detail: z.string().optional(),
  error: z.string().optional(),
}).passthrough();

export type McpOAuthServerStatus = z.infer<typeof McpOAuthServerStatusSchema>;
export type McpOAuthStatusResponse = z.infer<typeof McpOAuthStatusResponseSchema>;
export type McpOAuthStartResponse = z.infer<typeof McpOAuthStartResponseSchema>;



export type AccessModeResponse = z.infer<typeof AccessModeResponseSchema>;

/* ─── Local Model Discovery Schemas ─────────────────────────────── */
export const LocalModelItemSchema = z.object({
  id: z.string(),
  name: z.string().default(''),
  provider: z.string().default('local'),
  role: z.string().default('reasoning'),
  description: z.string().optional(),
  parameter_count_b: z.number().default(0),
  is_local: z.boolean().default(true),
  context_length: z.number().optional(),
  tier: z.string().optional(),
  status: z.enum(['running', 'installed', 'cached']).or(z.string()).default('installed'),
  disk_path: z.string().default(''),
  disk_size_gb: z.number().default(0),
  quantization: z.string().default(''),
  source: z.string().default(''),
}).passthrough();

export const LocalModelsResponseSchema = z.object({
  ok: z.boolean(),
  total: z.number().default(0),
  recommended_default: z.string().nullable().optional(),
  models: z.array(LocalModelItemSchema).default([]),
  message: z.string().optional(),
}).passthrough();

export type LocalModelItem = z.infer<typeof LocalModelItemSchema>;
export type LocalModelsResponse = z.infer<typeof LocalModelsResponseSchema>;

// ─── Training Recipe Presets (학습 레시피 프리셋, Phase 24) ────────────

export const RecipeHyperparametersSchema = z.record(z.string(), z.union([z.number(), z.string()]));

export const TrainingRecipeSchema = z.object({
  name: z.string(),
  title: z.string(),
  description: z.string(),
  source_hint: z.string(),
  format: z.string(),
  min_records: z.number(),
  hyperparameters: RecipeHyperparametersSchema,
});

export type RecipeHyperparameters = z.infer<typeof RecipeHyperparametersSchema>;
export type TrainingRecipe = z.infer<typeof TrainingRecipeSchema>;
export type TrainingRecipesResponse = { ok: true; recipes: TrainingRecipe[] };

/* ─── ARC-01 RequestExecutionContext (frozen) ───────────────── */
export const RequestExecutionContextWireSchema = z.object({
  schema_version: z.number().int().min(1).default(1),
  request_id: z.string().min(1).max(128),
  task_id: z.string().min(1).max(128).nullable().optional(),
  project_id: z.string().min(1).max(128),
  conversation_id: z.string().min(1).max(128),
  conversation_revision: z.number().int().min(0),
  actor_subject: z.string().min(1).max(256),
  session_id: z.string().min(1).max(256),
  model_id: z.string().min(1).max(128),
  correlation_id: z.string().max(128).default(""),
  client_hint_path: z.string().max(4096).nullable().optional(),
}).strict();

export const RequestExecutionContextSchema = z.object({
  schema_version: z.number().int().min(1).default(1),
  request_id: z.string().min(1).max(128),
  task_id: z.string().min(1).max(128).nullable().optional(),
  project_id: z.string().min(1).max(128),
  canonical_project_root: z.string().min(1).max(4096),
  conversation_id: z.string().min(1).max(128),
  conversation_revision: z.number().int().min(0),
  actor_subject: z.string().min(1).max(256),
  session_id: z.string().min(1).max(256),
  model_id: z.string().min(1).max(128),
  correlation_id: z.string().max(128).default(""),
  project_name: z.string().max(256).default(""),
}).strict();

export const ConversationConflictPayloadSchema = z.object({
  ok: z.literal(false),
  error: z.literal("stale_conversation_revision"),
  detail: z.string(),
  conversation_id: z.string().min(1),
  expected_revision: z.number().int().min(0),
  current_revision: z.number().int().min(0),
  correlation_id: z.string().default(""),
}).strict();

export const ConversationSnapshotSchema = z.object({
  conversation_id: z.string().min(1),
  project_id: z.string().min(1),
  revision: z.number().int().min(0),
  message_count: z.number().int().min(0),
  summary: z.string().nullable().optional(),
  retained_message_ids: z.array(z.string()).default([]),
}).strict();

export const ExecutionContextErrorCodeSchema = z.enum([
  "missing_execution_context",
  "invalid_execution_context",
  "invalid_conversation_revision",
  "project_not_found",
  "conversation_not_found",
  "project_root_invalid",
  "stale_conversation_revision",
]);

export const EXECUTION_CONTEXT_ERROR_HTTP_STATUS = {
  missing_execution_context: 400,
  invalid_execution_context: 400,
  invalid_conversation_revision: 400,
  project_not_found: 404,
  conversation_not_found: 404,
  project_root_invalid: 403,
  stale_conversation_revision: 409,
} as const;

export type RequestExecutionContextWire = z.infer<typeof RequestExecutionContextWireSchema>;
export type RequestExecutionContext = z.infer<typeof RequestExecutionContextSchema>;
export type ConversationConflictPayload = z.infer<typeof ConversationConflictPayloadSchema>;
export type ConversationSnapshot = z.infer<typeof ConversationSnapshotSchema>;
export type ExecutionContextErrorCode = z.infer<typeof ExecutionContextErrorCodeSchema>;
