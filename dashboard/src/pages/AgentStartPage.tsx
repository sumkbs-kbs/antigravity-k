/**
 * AgentStartPage — Unsloth Start & Agent Bridge
 * ===============================================
 * Inspired by `unsloth start`:
 * Instant 1-click bridge connecting Claude Code, OpenAI Codex, Hermes Agent,
 * OpenClaw, and MCP clients to local Ssak-Ai inference.
 */

import React, { useState } from 'react';
import { useChatStore } from '../stores/chatStore';
import { useUiStore } from '../stores/uiStore';

interface AgentIntegration {
  id: string;
  name: string;
  command: string;
  tag: string;
  icon: string;
  description: string;
  envVars: string[];
}

const INTEGRATIONS: AgentIntegration[] = [
  {
    id: 'claude-code',
    name: 'Claude Code CLI',
    command: 'agk start claude',
    tag: '가장 인기',
    icon: '⚡',
    description: 'Anthropic Claude Code CLI를 로컬 Ssak-Ai 프록시에 연결하여 토큰 비용 없이 오프라인 코딩 에이전트를 구동합니다.',
    envVars: [
      'export ANTHROPIC_BASE_URL="http://127.0.0.1:8000/v1"',
      'export ANTHROPIC_API_KEY="agk-local"',
    ],
  },
  {
    id: 'codex',
    name: 'OpenAI Codex CLI',
    command: 'agk start codex',
    tag: '공식 지원',
    icon: '💻',
    description: 'OpenAI 호환 규격의 코덱스 터미널 도구를 로컬 루프백 엔드포인트에 즉시 바인딩합니다.',
    envVars: [
      'export OPENAI_BASE_URL="http://127.0.0.1:8000/v1"',
      'export OPENAI_API_KEY="agk-local"',
    ],
  },
  {
    id: 'hermes',
    name: 'Hermes Agent',
    command: 'agk start hermes',
    tag: '자율 에이전트',
    icon: '🪽',
    description: '자가 치유(Self-healing) 도구 호출 및 복합 리서치 역량을 갖춘 Hermes 에이전트를 기동합니다.',
    envVars: [
      'export HERMES_ENDPOINT="http://127.0.0.1:8000/v1"',
    ],
  },
  {
    id: 'openclaw',
    name: 'OpenClaw / OpenCode',
    command: 'agk start openclaw',
    tag: '오픈소스',
    icon: '🦀',
    description: '오픈소스 에이전트 프레임워크와 직접 통신하며 컨텍스트 롤링 및 RAG를 공급합니다.',
    envVars: [
      'export AGENT_MODEL_ENDPOINT="http://127.0.0.1:8000/v1"',
    ],
  },
];

export const AgentStartPage: React.FC = () => {
  const { selectedModel } = useChatStore();
  const { addToast } = useUiStore();
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const handleCopy = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    addToast(`클립보드에 복사되었습니다: ${text}`, 'info');
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="unsloth-start-container">
      {/* Header */}
      <header className="unsloth-start-header">
        <div className="start-title-box">
          <div className="start-icon">🚀</div>
          <div>
            <div className="flex-align-center gap-8">
              <h1 className="start-title">Unsloth Start</h1>
              <span className="start-badge">LOCAL AGENT BRIDGE</span>
            </div>
            <p className="start-sub">
              한 줄의 명령어로 Claude Code, Codex, Hermes 등 터미널 에이전트를 로컬 모델(Qwen/Gemma)에 즉시 연결합니다.
            </p>
          </div>
        </div>

        {/* Global Endpoint Info Card */}
        <div className="endpoint-hud-card">
          <div className="endpoint-row">
            <span className="ep-lbl">Local Endpoint</span>
            <code className="ep-code">http://127.0.0.1:8000/v1</code>
          </div>
          <div className="endpoint-row">
            <span className="ep-lbl">Active Target Model</span>
            <span className="ep-model">{selectedModel.split('/').pop()}</span>
          </div>
          <div className="endpoint-row">
            <span className="ep-lbl">Cloudflare Tunnel</span>
            <span className="ep-tunnel-status">✓ Ready</span>
          </div>
        </div>
      </header>

      {/* Integration Cards Grid */}
      <div className="integrations-grid">
        {INTEGRATIONS.map(item => (
          <div key={item.id} className="integration-card">
            <div className="card-top-row">
              <div className="icon-title-cluster">
                <span className="item-icon">{item.icon}</span>
                <div>
                  <h2 className="item-name">{item.name}</h2>
                  <span className="item-tag">{item.tag}</span>
                </div>
              </div>
            </div>

            <p className="item-description">{item.description}</p>

            {/* Quick Command Snippet */}
            <div className="cmd-box">
              <div className="cmd-header">
                <span>Start Command</span>
                <button
                  type="button"
                  className="copy-btn"
                  onClick={() => handleCopy(`${item.command} --model ${selectedModel}`, item.id)}
                >
                  {copiedId === item.id ? '✓ 복사됨' : '📋 복사'}
                </button>
              </div>
              <pre className="cmd-text">
                <code>{item.command} --model {selectedModel}</code>
              </pre>
            </div>

            {/* Env Vars Snippet */}
            <div className="env-box">
              <span className="env-title">환경 변수 (Manual Setup):</span>
              {item.envVars.map((env, i) => (
                <div key={i} className="env-line">
                  <code>{env}</code>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Network & Cloudflare Tunnel Banner */}
      <div className="tunnel-banner-card">
        <div className="tunnel-info">
          <h3>🌐 원격 &amp; 모바일 접속 (Serve Anywhere via Cloudflare / LAN)</h3>
          <p>
            와이파이(LAN) 또는 무료 Cloudflare HTTPS 터널을 열어 모바일 폰이나 외부 노트북에서도 로컬 고성능 모델을 안전하게 호출할 수 있습니다.
          </p>
        </div>
        <div className="tunnel-actions">
          <button
            type="button"
            className="unsloth-btn-primary"
            onClick={() => handleCopy('agk run --host 0.0.0.0 --tunnel cloudflare', 'tunnel')}
          >
            터널 커맨드 복사
          </button>
        </div>
      </div>
    </div>
  );
};

export default AgentStartPage;
