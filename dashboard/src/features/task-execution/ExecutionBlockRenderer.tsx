import { AgentTree, ExecutionChecklist, TerminalEventList } from './TaskExecutionSections';
import { buildExecutionBlocks } from './executionBlocks';
import type { ExecutionBlock } from './executionBlocks';
import type { TaskExecutionProjection } from './taskExecutionProjection';

function assertNever(value: never): never {
  return value;
}

function renderBlock(block: ExecutionBlock) {
  switch (block.kind) {
    case 'agents':
      return <AgentTree agents={block.agents} />;
    case 'checklist':
      return <ExecutionChecklist items={block.items} />;
    case 'terminals':
      return <TerminalEventList terminals={block.terminals} />;
    default:
      return assertNever(block);
  }
}

export function ExecutionBlockRenderer({
  projection,
}: Readonly<{ projection: TaskExecutionProjection }>) {
  return (
    <div className="task-execution-blocks">
      {buildExecutionBlocks(projection).map((block) => (
        <div key={block.kind} className={`task-execution-block task-execution-block-${block.kind}`}>
          {renderBlock(block)}
        </div>
      ))}
    </div>
  );
}
