import { z } from 'zod';

export const TaskIdSchema = z.string().min(1).brand<'TaskId'>();
export const AgentIdSchema = z.string().min(1).brand<'AgentId'>();
export const StepIdSchema = z.string().min(1).brand<'StepId'>();
export const ToolCallIdSchema = z.string().min(1).brand<'ToolCallId'>();

export const TaskEventSchema = z.object({
  sequence: z.number().int().nonnegative(),
  schema_version: z.number().int().positive(),
  task_id: TaskIdSchema,
  step_id: StepIdSchema.nullable(),
  agent_id: AgentIdSchema.nullable(),
  parent_id: AgentIdSchema.nullable(),
  tool_call_id: ToolCallIdSchema.nullable(),
  approval_id: z.string().min(1).nullable(),
  resource_job_id: z.string().min(1).nullable(),
  correlation_id: z.string().min(1).nullable(),
  event_type: z.string().min(1),
  payload: z.json(),
  created_at: z.string().min(1),
}).readonly();

export const TaskEventsResponseSchema = z.object({
  task_id: TaskIdSchema,
  events: z.array(TaskEventSchema).readonly(),
  last_sequence: z.number().int().nonnegative(),
}).readonly();

export const TaskSummarySchema = z.object({
  task_id: TaskIdSchema,
  prompt: z.string(),
  status: z.string().min(1),
  output: z.string().optional().default(''),
  error: z.string().nullable(),
  created_at: z.string().min(1),
  updated_at: z.string().min(1),
  completed_at: z.string().nullable().optional().default(null),
}).readonly();

export const TaskListResponseSchema = z.object({
  status: z.literal('ok'),
  data: z.array(TaskSummarySchema).readonly(),
}).readonly();

export const TaskStreamEndSchema = z.object({
  task_id: TaskIdSchema,
  last_sequence: z.number().int().nonnegative(),
  status: z.string().min(1),
}).readonly();

export type TaskId = z.infer<typeof TaskIdSchema>;
export type AgentId = z.infer<typeof AgentIdSchema>;
export type StepId = z.infer<typeof StepIdSchema>;
export type TaskEvent = z.infer<typeof TaskEventSchema>;
export type TaskSummary = z.infer<typeof TaskSummarySchema>;
export type JsonValue = z.infer<ReturnType<typeof z.json>>;
