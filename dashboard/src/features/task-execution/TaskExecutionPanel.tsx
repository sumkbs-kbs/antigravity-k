import { useApprovalQueue } from './useApprovalQueue';
import { TaskExecutionView } from './TaskExecutionView';
import { useTaskExecutionEvents } from './useTaskExecutionEvents';

export function TaskExecutionPanel() {
  const state = useTaskExecutionEvents();
  const approvals = useApprovalQueue();
  return (
    <TaskExecutionView
      tasks={state.tasks}
      selectedTaskId={state.selectedTaskId}
      events={state.events}
      connectionState={state.connectionState}
      error={state.error}
      pendingAction={state.pendingAction}
      approvals={approvals.approvals}
      pendingApprovalId={approvals.pendingRequestId}
      approvalError={approvals.error}
      onSelectTask={state.selectTask}
      onSubmit={state.submit}
      onCancel={state.cancel}
      onResume={state.resume}
      onFork={state.fork}
      onResolveApproval={approvals.resolve}
      onRetry={state.retry}
    />
  );
}
