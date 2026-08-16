import { describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import ModelOperationsPanel from '../ModelOperationsPanel';
import { fetchModelOperations, type ModelOperationsStatus } from '../../../api/client';

vi.mock('../../../api/client', () => ({
  fetchModelOperations: vi.fn(),
}));

const STATUS: ModelOperationsStatus = {
  provider_capabilities: {
    'qwen3.6:latest': {
      model: 'qwen3.6:latest',
      provider: 'ollama',
      is_local: true,
      runtime_status: 'available',
      native_tool_calling: 'supported',
      source: 'ollama:/api/show',
    },
  },
  quality_calibration: {
    enabled: true,
    eligible_models: ['qwen3.6:latest'],
    ineligible_models: [],
    operational_metrics: [
      {
        model: 'qwen3.6:latest',
        outcome_count: 3,
        task_success_rate: 1,
        tool_accuracy: 1,
        retry_rate: 0,
      },
    ],
  },
};

describe('ModelOperationsPanel', () => {
  it('renders provider readiness and observed Qwen task metrics', async () => {
    vi.mocked(fetchModelOperations).mockResolvedValue(STATUS);

    render(<ModelOperationsPanel />);

    expect(await screen.findAllByText('qwen3.6:latest')).toHaveLength(2);
    expect(screen.getByText('available')).toBeInTheDocument();
    expect(screen.getByText('supported')).toBeInTheDocument();
    expect(screen.getAllByText('3')).toHaveLength(2);
    await waitFor(() => expect(fetchModelOperations).toHaveBeenCalledOnce());
  });
});
