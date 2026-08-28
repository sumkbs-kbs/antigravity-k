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
  backends: z.record(z.string(), z.unknown()).optional(),
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
