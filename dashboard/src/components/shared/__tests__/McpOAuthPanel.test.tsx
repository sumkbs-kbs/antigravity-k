/**
 * McpOAuthPanel tests
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import McpOAuthPanel from '../McpOAuthPanel';
import { fetchMcpOAuthStatus, startMcpOAuth, revokeMcpOAuth } from '../../../api/client';

vi.mock('../../../api/client', () => ({
  fetchMcpOAuthStatus: vi.fn(),
  startMcpOAuth: vi.fn(),
  revokeMcpOAuth: vi.fn(),
}));

const fetchMock = vi.mocked(fetchMcpOAuthStatus);
const startMock = vi.mocked(startMcpOAuth);
const revokeMock = vi.mocked(revokeMcpOAuth);

const SAMPLE = {
  ok: true as const,
  source: '/tmp/.mcp.json',
  summary: { total: 2, oauth_capable: 1, connected: 0 },
  servers: [
    {
      name: 'remote',
      transport: 'http',
      url: 'https://mcp.example.com/mcp',
      supports_oauth: true,
      auth_type: 'oauth',
      connected: false,
      has_client_id: true,
      status: null,
    },
    {
      name: 'local',
      transport: 'stdio',
      url: '',
      supports_oauth: false,
      auth_type: '',
      connected: false,
      has_client_id: false,
      status: null,
    },
  ],
};

describe('McpOAuthPanel', () => {
  beforeEach(() => {
    fetchMock.mockReset();
    startMock.mockReset();
    revokeMock.mockReset();
    fetchMock.mockResolvedValue(SAMPLE);
    startMock.mockResolvedValue({
      ok: true,
      server_name: 'remote',
      authorization_url: 'https://auth.example.com/authorize?x=1',
      state: 'st',
    });
    revokeMock.mockResolvedValue({ ok: true, revoked: true, connected: false });
    vi.stubGlobal('open', vi.fn());
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.unstubAllGlobals();
  });

  it('renders OAuth-capable servers only', async () => {
    render(<McpOAuthPanel refreshInterval={60_000} />);
    await waitFor(() => expect(screen.getByText('remote')).toBeInTheDocument());
    expect(screen.getByRole('heading', { name: /MCP OAuth 2.1/ })).toBeInTheDocument();
    expect(screen.queryByText('local')).not.toBeInTheDocument();
    expect(screen.getByTestId('mcp-oauth-summary-oauth_capable')).toHaveTextContent('1');
  });

  it('starts OAuth and opens authorization URL', async () => {
    render(<McpOAuthPanel refreshInterval={60_000} />);
    const btn = await screen.findByTestId('mcp-oauth-connect-remote');
    fireEvent.click(btn);
    await waitFor(() => expect(startMock).toHaveBeenCalledWith('remote'));
    expect(window.open).toHaveBeenCalledWith(
      'https://auth.example.com/authorize?x=1',
      'ssak-mcp-oauth',
      expect.any(String),
    );
  });

  it('revokes connected server', async () => {
    fetchMock.mockResolvedValue({
      ...SAMPLE,
      summary: { total: 2, oauth_capable: 1, connected: 1 },
      servers: [
        {
          ...SAMPLE.servers[0],
          connected: true,
          status: { connected: true, expired: false },
        },
      ],
    });
    render(<McpOAuthPanel refreshInterval={60_000} />);
    const btn = await screen.findByTestId('mcp-oauth-revoke-remote');
    fireEvent.click(btn);
    await waitFor(() => expect(revokeMock).toHaveBeenCalledWith('remote'));
  });
});
