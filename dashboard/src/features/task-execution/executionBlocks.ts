import type {
  AgentProjection,
  ChecklistProjection,
  TaskExecutionProjection,
  TerminalProjection,
} from './taskExecutionProjection';

export type ExecutionBlock =
  | Readonly<{ kind: 'agents'; agents: readonly AgentProjection[] }>
  | Readonly<{ kind: 'checklist'; items: readonly ChecklistProjection[] }>
  | Readonly<{ kind: 'terminals'; terminals: readonly TerminalProjection[] }>;

export function buildExecutionBlocks(projection: TaskExecutionProjection): readonly ExecutionBlock[] {
  return [
    { kind: 'agents', agents: projection.agents },
    { kind: 'checklist', items: projection.checklist },
    { kind: 'terminals', terminals: projection.terminals },
  ];
}
