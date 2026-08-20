import { TaskExecutionView } from './TaskExecutionView';
import { useTaskExecutionEvents } from './useTaskExecutionEvents';

export function TaskExecutionPanel() {
  const state = useTaskExecutionEvents();
  return (
    <TaskExecutionView
      tasks={state.tasks}
      selectedTaskId={state.selectedTaskId}
      events={state.events}
      connectionState={state.connectionState}
      error={state.error}
      onSelectTask={state.selectTask}
      onRetry={state.retry}
    />
  );
}
