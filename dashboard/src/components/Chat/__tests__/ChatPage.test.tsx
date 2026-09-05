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
    expect(screen.getByText('Open IDE')).toBeInTheDocument();
  });

  it('renders Antigravity environment rail with env sections', () => {
    renderChatPage();

    expect(screen.getByLabelText('환경 패널')).toBeInTheDocument();
    expect(screen.getByText('변경 사항')).toBeInTheDocument();
    expect(screen.getByText('로그')).toBeInTheDocument();
    expect(screen.getByText('커밋 또는 푸시')).toBeInTheDocument();
    expect(screen.getByText('풀 리퀘스트 만들기')).toBeInTheDocument();
    expect(screen.getByText('파일 액티브티')).toBeInTheDocument();
    // 소스 섹션은 /api/mcp/servers 결과를 반영 (빈 환경에서는 안내 문구)
    expect(screen.getByText('소스')).toBeInTheDocument();
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
    // Branch appears in both the docked context bar and the 환경 rail
    expect(screen.getAllByText('codex/m1-task-events').length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByTestId('hero-headline')).not.toBeInTheDocument();
  });
});
