/**
 * EmptyState — TERMINAL-7 Hero Section
 * =====================================
 * Cold-blooded engineering for warm-blooded users.
 * Editorial Serif headline + terminal boot simulation + command chips.
 */

import React from 'react';

interface Props {
  onExampleClick: (text: string) => void;
}

const TERMINAL_COMMANDS = [
  { cmd: '$ review --project', text: '이 프로젝트 코드 리뷰해줘' },
  { cmd: '$ search --files', text: '파일 목록 보여줘' },
  { cmd: '$ agent --capabilities', text: '니가 할 수 있는 게 뭐야?' },
  { cmd: '$ query --weather', text: '오늘 서울 날씨 알려줘' },
];

const EmptyState: React.FC<Props> = ({ onExampleClick }) => {
  return (
    <div className="empty-state-container" aria-label="Welcome Hero">
      <div className="terminal7-hero-split">
        {/* ── Left Column: Editorial Headline & Manifest ─────────── */}
        <div className="terminal7-headline-area">
          <div className="terminal7-sub-tag">
            <span>■</span>
            <span>// SSAK-AI RESEARCH ENGINE</span>
          </div>

          <h2 className="empty-state-title terminal7-title">
            Cold-blooded engineering for{' '}
            <span className="accent-italic">warm-blooded users.</span>
            <span className="cursor-block">■</span>
          </h2>

          <p className="empty-state-subtitle terminal7-subtitle">
            // Ssak-Ai is a local-first autonomous engineering agent system working
            on deterministic tool use, plain-text git vault memory, and full-stack
            software synthesis.
          </p>

          <div className="terminal7-actions-row">
            {TERMINAL_COMMANDS.map(item => (
              <button
                key={item.cmd}
                type="button"
                className="example-chip"
                onClick={() => onExampleClick(item.text)}
                title={item.text}
              >
                <span className="terminal-prompt-prefix" style={{ marginRight: 6 }}>
                  {item.cmd.split(' ')[0]}
                </span>
                <span>{item.cmd.split(' ').slice(1).join(' ')}</span>
              </button>
            ))}
          </div>
        </div>

        {/* ── Right Column: Terminal Boot Window Simulation ──────── */}
        <div className="terminal-boot-box" aria-hidden="true">
          <div className="terminal-boot-header">
            <div className="terminal-window-dots">
              <span className="terminal-dot-red" />
              <span className="terminal-dot-yellow" />
              <span className="terminal-dot-green" />
            </div>
            <div className="terminal-boot-title">~/ssak-ai - 80x24 - bash</div>
            <div style={{ width: 36 }} />
          </div>

          <div className="terminal-boot-body">
            <div className="terminal-line-comment"># Ssak-Ai boot sequence — September 2026</div>
            <div className="terminal-line-command">
              <span className="prompt-char">$</span>./bin/init --mode=autonomous
            </div>
            <div className="terminal-line-success">- ok · loaded vault / git-first core</div>
            <div className="terminal-line-success">- ok · loaded dynamic model registry</div>
            <div className="terminal-line-success">- ok · loaded skills & subagent orchestra</div>
            <div className="terminal-line-comment"># 3 modules online · 0.8s cold start</div>
            <div style={{ height: 4 }} />
            <div className="terminal-line-command">
              <span className="prompt-char">$</span>ssak-ai --status
            </div>
            <div className="terminal-line-amber">
              [0028] autonomous reasoning loop active
            </div>
            <div className="terminal-line-cyan">
              [0029] local execution sandbox engaged
            </div>
            <div style={{ height: 4 }} />
            <div className="terminal-line-command">
              <span className="prompt-char">$</span>
              <span className="cursor-block">█</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default EmptyState;
