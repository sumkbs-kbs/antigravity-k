/**
 * McpHealthCachePanel tests
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import McpHealthCachePanel from '../McpHealthCachePanel';
import { fetchMcpHealth, refreshMcpHealth } from '../../../api/client';

vi.mock('../../../api/client', () => ({
  fetchMcpHealth: vi.fn(),
  refreshMcpHealth: vi.fn(),
}));

const fetchMock = vi.mocked(fetchMcpHealth);
const refreshMock = vi.mocked(refreshMcpHealth);

const SAMPLE = {
  ok: true as const,
  source: '/tmp/.mcp.json',
  probed_at: 1_725_000_000,
  summary: { total: 2, healthy: 1, error: 1, blocked: 0, configured: 0, unknown: 0 },
  servers: [
    {
      name: 'filesystem',
      transport: 'stdio',
      status: 'healthy',
      tool_count: 2,
      tools: ['read_file', 'write_file'],
      error: null,
      initialized: true,
      checked_at: 1_725_000_000,
      latency_ms: 42,
      source: '/tmp/.mcp.json',
      command: 'npx',
    },
    {
      name: 'broken',
      transport: 'http',
      status: 'error',
      tool_count: 0,
      tools: [],
      error: 'connection refused',
      initialized: false,
      checked_at: 1_725_000_000,
      latency_ms: 10,
      source: '/tmp/.mcp.json',
      command: 'https://x',
    },
  ],
};

describe('McpHealthCachePanel', () => {
  beforeEach(() => {
    fetchMock.mockReset();
    refreshMock.mockReset();
    fetchMock.mockResolvedValue(SAMPLE);
    refreshMock.mockResolvedValue({ ...SAMPLE, summary: { ...SAMPLE.summary, healthy: 2, error: 0 } });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('renders summary cards and server rows', async () => {
    render(<McpHealthCachePanel refreshInterval={60_000} />);
    await waitFor(() => expect(screen.getByText('filesystem')).toBeInTheDocument());
    expect(screen.getByRole('heading', { name: /MCP 서버 헬스 캐시/ })).toBeInTheDocument();
    expect(screen.getByText('broken')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalled();
  });

  it('expands a row to show failure reason', async () => {
    render(<McpHealthCachePanel refreshInterval={60_000} />);
    const row = await screen.findByTestId('mcp-health-row-broken');
    fireEvent.click(row);
    expect(await screen.findByText(/connection refused/)).toBeInTheDocument();
  });

  it('runs a health probe on button click', async () => {
    render(<McpHealthCachePanel refreshInterval={60_000} />);
    await screen.findByText('filesystem');
    fireEvent.click(screen.getByTestId('mcp-health-probe'));
    await waitFor(() => expect(refreshMock).toHaveBeenCalledOnce());
  });

  it('shows an empty state when no servers are configured', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      source: '',
      probed_at: null,
      summary: { total: 0, healthy: 0, error: 0, blocked: 0, configured: 0, unknown: 0 },
      servers: [],
    });
    render(<McpHealthCachePanel refreshInterval={60_000} />);
    expect(await screen.findByText(/구성된 MCP 서버가 없습니다/)).toBeInTheDocument();
  });
});
