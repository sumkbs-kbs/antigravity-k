import { describe, expect, it, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ChatPage from '../ChatPage';
import { useChatStore } from '../../../stores/chatStore';

function renderChatPage() {
  return render(
    <MemoryRouter>
      <ChatPage />
    </MemoryRouter>
  );
}

describe('ChatPage agent workspace layout (Unsloth hero)', () => {
  afterEach(() => {
    useChatStore.setState({
      messages: [],
      activeSession: null,
      isStreaming: false,
    });
  });

  it('renders Unsloth hero, chip toolbar, and composer in the empty state', () => {
    renderChatPage();

    expect(screen.getByTestId('hero-headline')).toHaveTextContent('Ready when you are');
    expect(screen.getByPlaceholderText(/Ask anything/i)).toBeInTheDocument();
    expect(screen.getByText('전체 액세스')).toBeInTheDocument();
    expect(screen.getByText('Search')).toBeInTheDocument();
    expect(screen.getByText('Code')).toBeInTheDocument();
    expect(screen.getByText('MCP')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /모델 선택/i })).toBeInTheDocument();
    expect(screen.queryByText('5.6 Sol High')).toBeNull();
    expect(screen.getByText(/orchestrator-swarm/i)).toBeInTheDocument();
    expect(screen.getByLabelText('채팅 히스토리')).toBeInTheDocument();
    expect(screen.getByLabelText('환경 패널 토글')).toBeInTheDocument();
  });

  it('renders Antigravity environment rail with agent monitoring sections', () => {
    renderChatPage();

    expect(screen.getByLabelText('에이전트 모니터링 패널')).toBeInTheDocument();
    expect(screen.getByText('에이전트 상태')).toBeInTheDocument();
    expect(screen.getByText('실시간 활동')).toBeInTheDocument();
    expect(screen.getByText('토큰 사용량')).toBeInTheDocument();
    expect(screen.getByText('파일 변경 추적')).toBeInTheDocument();
    expect(screen.getByText('에러 / 경고')).toBeInTheDocument();
  });

  it('renders the docked context bar and breadcrumb when a conversation exists', () => {
    useChatStore.setState({
      messages: [
        { role: 'user', content: '안녕하세요' },
        { role: 'assistant', content: '무엇을 도와드릴까요?' },
      ],
      activeSession: {
        id: 's1',
        title: 'Continuing Previous Agent Work',
        updatedAt: new Date().toISOString(),
        messages: [],
      },
    });
    renderChatPage();

    expect(screen.getByText('Continuing Previous Agent Work')).toBeInTheDocument();
    expect(screen.getByText('Ssak-Ai', { selector: '.crumb-project' })).toBeInTheDocument();
    expect(screen.getByText('로컬')).toBeInTheDocument();
    // Branch now only appears in the docked context bar (moved from 환경 to 코드 tab)
    expect(screen.getAllByText('codex/m1-task-events').length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByTestId('hero-headline')).not.toBeInTheDocument();
  });
});
