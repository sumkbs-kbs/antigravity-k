import { describe, expect, it, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import ActivityTimeline from '../ActivityTimeline';
import { useActivityStore } from '../../../stores/activityStore';

describe('activityStore', () => {
  beforeEach(() => {
    useActivityStore.getState().clear();
  });

  it('records tool start with a mapped Korean label and running status', () => {
    useActivityStore.getState().recordToolStart({ tool_name: 'run_bash_command', command: 'pytest -q' });
    const items = useActivityStore.getState().items;
    expect(items).toHaveLength(1);
    expect(items[0].label).toBe('명령 실행');
    expect(items[0].detail).toBe('pytest -q');
    expect(items[0].status).toBe('running');
  });

  it('marks the latest running tool as done on tool end', () => {
    useActivityStore.getState().recordToolStart({ tool_name: 'web_search', query: '대기열' });
    useActivityStore.getState().recordToolStart({ tool_name: 'read_file', filepath: 'a.py' });
    useActivityStore.getState().recordToolEnd();
    const items = useActivityStore.getState().items;
    expect(items[0].status).toBe('running');
    expect(items[1].status).toBe('done');
  });

  it('dedupes identical activity within the window instead of growing unbounded', () => {
    useActivityStore.getState().recordFileEdit('src/App.tsx');
    useActivityStore.getState().recordFileEdit('src/App.tsx');
    expect(useActivityStore.getState().items).toHaveLength(1);
  });
});

describe('ActivityTimeline', () => {
  beforeEach(() => {
    useActivityStore.getState().clear();
  });

  it('renders nothing without activity', () => {
    render(<ActivityTimeline />);
    expect(screen.queryByTestId('activity-timeline')).not.toBeInTheDocument();
  });

  it('shows collapsed chips and expands into detail rows', () => {
    const store = useActivityStore.getState();
    store.recordFileEdit('src/App.tsx');
    store.recordFileRead('README.md');
    store.recordToolStart({ tool_name: 'run_bash_command', command: 'pytest -q' });

    render(<ActivityTimeline />);

    expect(screen.getByTestId('activity-timeline')).toBeInTheDocument();
    expect(screen.getByText('파일 수정함')).toBeInTheDocument();
    expect(screen.queryByText('pytest -q')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button'));
    expect(screen.getByText('pytest -q')).toBeInTheDocument();
    expect(screen.getByText('src/App.tsx')).toBeInTheDocument();
    expect(screen.getByText(/활동 3개/)).toBeInTheDocument();
  });
});
