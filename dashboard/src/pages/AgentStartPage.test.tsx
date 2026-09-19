import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import AgentStartPage from './AgentStartPage';

describe('AgentStartPage', () => {
  it('renders unsloth start title, local endpoint, and agent integrations', () => {
    render(<AgentStartPage />);

    expect(screen.getByText('Unsloth Start')).toBeInTheDocument();
    expect(screen.getByText('LOCAL AGENT BRIDGE')).toBeInTheDocument();
    expect(screen.getByText('http://127.0.0.1:8000/v1')).toBeInTheDocument();
    expect(screen.getByText('Claude Code CLI')).toBeInTheDocument();
    expect(screen.getByText('OpenAI Codex CLI')).toBeInTheDocument();
    expect(screen.getByText('Hermes Agent')).toBeInTheDocument();
  });
});
