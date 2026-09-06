import type {
  AgentProjection,
  ChecklistProjection,
  ExecutionStatus,
  TerminalProjection,
} from './taskExecutionProjection';

const STATUS_LABELS = {
  running: '실행 중',
  completed: '완료',
  failed: '실패',
  cancelled: '취소됨',
  waiting: '대기 중',
  degraded: '제한적 저하',
  unknown: '상태 미확인',
} as const satisfies Record<ExecutionStatus, string>;

function statusClass(status: ExecutionStatus): string {
  return `task-execution-status task-execution-status-${status}`;
}

type AgentForest = Readonly<{
  roots: readonly AgentProjection[];
  childrenByParent: ReadonlyMap<AgentProjection['id'], readonly AgentProjection[]>;
}>;

function buildAgentForest(agents: readonly AgentProjection[]): AgentForest {
  const agentsById = new Map(agents.map((agent) => [agent.id, agent]));
  const childrenByParent = new Map<AgentProjection['id'], AgentProjection[]>();
  const roots: AgentProjection[] = [];

  for (const agent of agents) {
    const parentId = agent.parentId;
    const parent = parentId === null ? undefined : agentsById.get(parentId);
    if (parentId === null || parent === undefined || parent.depth >= agent.depth) {
      roots.push(agent);
      continue;
    }

    const siblings = childrenByParent.get(parentId);
    if (siblings === undefined) childrenByParent.set(parentId, [agent]);
    else siblings.push(agent);
  }

  return { roots, childrenByParent };
}

function AgentNode({
  agent,
  childrenByParent,
}: Readonly<{
  agent: AgentProjection;
  childrenByParent: ReadonlyMap<AgentProjection['id'], readonly AgentProjection[]>;
}>) {
  const children = childrenByParent.get(agent.id) ?? [];
  return (
    <li className="task-agent-node">
      <div className="task-agent-row">
        <div className="task-agent-identity">
          <strong>{agent.label}</strong>
          <code>{agent.id}</code>
          {agent.role !== null && <span>{agent.role}</span>}
        </div>
        <div className="task-agent-state">
          <span className={statusClass(agent.status)}>{STATUS_LABELS[agent.status]}</span>
          <span>seq {agent.lastSequence}</span>
        </div>
      </div>
      {children.length > 0 && (
        <ul className="task-agent-children" aria-label={`${agent.label} 하위 에이전트`}>
          {children.map((child) => (
            <AgentNode key={child.id} agent={child} childrenByParent={childrenByParent} />
          ))}
        </ul>
      )}
    </li>
  );
}

export function AgentTree({ agents }: Readonly<{ agents: readonly AgentProjection[] }>) {
  const forest = buildAgentForest(agents);
  return (
    <section className="task-execution-region" aria-labelledby="task-agent-tree-title">
      <div className="task-execution-region-heading">
        <h4 id="task-agent-tree-title">에이전트 트리</h4>
        <span>{agents.length} agents</span>
      </div>
      {agents.length === 0 ? (
        <p className="task-execution-empty">agent_id 메타데이터를 기다리고 있습니다.</p>
      ) : (
        <ul className="task-agent-list">
          {forest.roots.map((agent) => (
            <AgentNode key={agent.id} agent={agent} childrenByParent={forest.childrenByParent} />
          ))}
        </ul>
      )}
    </section>
  );
}

export function ExecutionChecklist({ items }: Readonly<{ items: readonly ChecklistProjection[] }>) {
  return (
    <section className="task-execution-region" aria-labelledby="task-checklist-title">
      <div className="task-execution-region-heading">
        <h4 id="task-checklist-title">실행 체크리스트</h4>
        <span>{items.length} steps</span>
      </div>
      {items.length === 0 ? (
        <p className="task-execution-empty">step_id가 포함된 이벤트를 기다리고 있습니다.</p>
      ) : (
        <ol className="task-checklist">
          {items.map((item) => (
            <li key={item.id} className="task-checklist-row">
              <div className="task-checklist-sequence">{item.firstSequence}</div>
              <div className="task-checklist-copy">
                <strong>{item.label}</strong>
                <code>{item.id}</code>
              </div>
              <span className={statusClass(item.status)}>{STATUS_LABELS[item.status]}</span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

export function TerminalEventList({ terminals }: Readonly<{ terminals: readonly TerminalProjection[] }>) {
  return (
    <section className="task-terminal-region" aria-labelledby="task-terminal-title">
      <div className="task-execution-region-heading">
        <h4 id="task-terminal-title">터미널 이벤트</h4>
        <span>{terminals.length} calls</span>
      </div>
      {terminals.length === 0 ? (
        <p className="task-execution-empty">tool 또는 terminal 이벤트가 아직 없습니다.</p>
      ) : (
        <div className="task-terminal-list">
          {terminals.map((terminal) => (
            <article key={terminal.id} className="task-terminal-card">
              <header>
                <div>
                  <strong>{terminal.toolName}</strong>
                  <code>{terminal.id}</code>
                </div>
                <span className={statusClass(terminal.status)}>{STATUS_LABELS[terminal.status]}</span>
              </header>
              {terminal.command !== null && <code className="task-terminal-command">{terminal.command}</code>}
              <pre tabIndex={0}>{terminal.output.length > 0 ? terminal.output : '아직 출력이 없습니다.'}</pre>
              <footer>
                <span>seq {terminal.firstSequence}-{terminal.lastSequence}</span>
                {terminal.truncated && <span>head/tail 미리보기</span>}
              </footer>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
