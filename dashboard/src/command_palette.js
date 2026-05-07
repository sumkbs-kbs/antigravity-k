document.addEventListener('DOMContentLoaded', () => {
    const overlay = document.getElementById('command-palette-overlay');
    const input = document.getElementById('cmd-input');
    const resultsContainer = document.getElementById('cmd-results');

    let isVisible = false;
    let currentResults = [];
    let selectedIndex = 0;

    // Helper: Execute sync vault
    async function syncVault() {
        window.showToast?.('🔄 Vault 동기화 중...', 'info');
        try {
            const res = await fetch('/api/vault/sync', { method: 'POST' });
            const data = await res.json();
            if (data.ok) {
                window.showToast?.('✅ Vault 동기화 완료 (commit: ' + (data.commit ? data.commit.substring(0, 7) : 'N/A') + ')', 'success');
            } else {
                window.showToast?.('❌ Vault 동기화 실패', 'error');
            }
        } catch (e) {
            window.showToast?.('❌ Vault 동기화 오류: ' + e.message, 'error');
        }
    }

    // Dummy commands for UI demonstration
    const availableCommands = [
        { id: 'search', title: 'Search Notes', icon: '🔍', action: () => {
            if (input) input.focus();
        }},
        { id: 'new_note', title: 'Create New Note', icon: '📝', action: () => {
            navigateTo('wiki');
            setTimeout(() => window.dispatchEvent(new CustomEvent('open-wiki-new')), 100);
        }},
        { id: 'chat', title: 'Open AI Chat', icon: '💬', action: () => navigateTo('chat') },
        { id: 'goal', title: 'Autonomous Goal (/goal)', icon: '🎯', action: () => {
            navigateTo('chat');
            setTimeout(() => {
                const chatInput = document.getElementById('chat-input');
                if (chatInput) {
                    chatInput.value = '/goal ';
                    chatInput.focus();
                    chatInput.dispatchEvent(new Event('input', { bubbles: true }));
                }
            }, 120);
        }},
        { id: 'agentic', title: 'Agentic Upgrade Radar (/agentic)', icon: '🧭', action: () => {
            navigateTo('chat');
            setTimeout(() => {
                const chatInput = document.getElementById('chat-input');
                if (chatInput) {
                    chatInput.value = '/agentic ';
                    chatInput.focus();
                    chatInput.dispatchEvent(new Event('input', { bubbles: true }));
                }
            }, 120);
        }},
        { id: 'mcp', title: 'MCP Upgrade Radar (/mcp)', icon: '🔌', action: () => {
            navigateTo('chat');
            setTimeout(() => {
                const chatInput = document.getElementById('chat-input');
                if (chatInput) {
                    chatInput.value = '/mcp ';
                    chatInput.focus();
                    chatInput.dispatchEvent(new Event('input', { bubbles: true }));
                }
            }, 120);
        }},
        { id: 'capabilities', title: 'Autonomous Capabilities (/capabilities)', icon: '🧠', action: () => {
            navigateTo('chat');
            setTimeout(() => {
                const chatInput = document.getElementById('chat-input');
                if (chatInput) {
                    chatInput.value = '/capabilities ';
                    chatInput.focus();
                    chatInput.dispatchEvent(new Event('input', { bubbles: true }));
                }
            }, 120);
        }},
        { id: 'self', title: 'Self Capability Report (/self)', icon: '🪪', action: () => {
            navigateTo('chat');
            setTimeout(() => {
                const chatInput = document.getElementById('chat-input');
                if (chatInput) {
                    chatInput.value = '/self';
                    chatInput.focus();
                    chatInput.dispatchEvent(new Event('input', { bubbles: true }));
                }
            }, 120);
        }},
        { id: 'codex', title: 'Codex Capability Transfer (/codex)', icon: '⚡', action: () => {
            navigateTo('chat');
            setTimeout(() => {
                const chatInput = document.getElementById('chat-input');
                if (chatInput) {
                    chatInput.value = '/codex ';
                    chatInput.focus();
                    chatInput.dispatchEvent(new Event('input', { bubbles: true }));
                }
            }, 120);
        }},
        { id: 'benchmark', title: 'Collective Benchmark Report (/benchmark)', icon: '📊', action: () => {
            navigateTo('chat');
            setTimeout(() => {
                const chatInput = document.getElementById('chat-input');
                if (chatInput) {
                    chatInput.value = '/benchmark report';
                    chatInput.focus();
                    chatInput.dispatchEvent(new Event('input', { bubbles: true }));
                }
            }, 120);
        }},
        { id: 'settings', title: 'Preferences', icon: '⚙️', action: () => navigateTo('settings') },
        { id: 'sync', title: 'Sync Vault (Git)', icon: '🔄', action: () => syncVault() },
        { id: 'selftest', title: 'Run Self-Test (Cmd+Shift+T)', icon: '🧪', action: () => {
            hidePalette();
            if (window.runSelfTest) window.runSelfTest();
        }},
        { id: 'autonomous_qa', title: 'Autonomous QA Loop (Cmd+Shift+Q)', icon: '🤖', action: () => {
            hidePalette();
            if (window.runAutonomousQA) window.runAutonomousQA();
        }},
        { id: 'tdd_loop', title: 'Test-Driven Code Generation (Cmd+Shift+D)', icon: '🧪', action: () => {
            hidePalette();
            const prompt = window.prompt('TDD 코딩 요구사항을 상세히 입력하세요:');
            if (prompt) {
                window.showToast?.('🧪 TDD 루프 생성 중...', 'info');
                fetch('/api/agent/tools/tdd-generate', {
                    method:'POST', headers:{'Content-Type':'application/json'},
                    body: JSON.stringify({
                        prompt,
                        // 사용자의 대형 모델 제안에 따라 deepseek-r1:70b 등 더 강력한 모델을 옵션으로 사용
                        coding_model: 'deepseek-r1:70b'
                    })
                }).then(r=>r.json()).then(d=> {
                    if(d.ok) {
                        window.showToast?.('✅ TDD 검증 통과! (승자: ' + d.report.winner_source + ')', 'success');
                        if (window.appendMessageGlobal) {
                            window.appendMessageGlobal('assistant', '## 🧪 TDD 최종 통과 코드 (승자: ' + d.report.winner_source + ')\n\n```python\n' + d.report.final_code + '\n```');
                        }
                    } else {
                        window.showToast?.('❌ TDD 최종 실패', 'error');
                        if (window.appendMessageGlobal && d.report) {
                            window.appendMessageGlobal('assistant', '## ❌ TDD 실패 로그\n\n```\n' + d.report.error + '\n```');
                        }
                    }
                });
            }
        }},
        { id: 'ext_brain_list', title: 'External Brain — List Available', icon: '🧠', action: async () => {
            hidePalette();
            try {
                const res = await fetch('/api/agent/tools/external-brain/list');
                const data = await res.json();
                const msg = data.brains.map(b => `${b.available ? '✅' : '❌'} **${b.name}** (timeout: ${b.timeout_sec}s)`).join('\n');
                window.showToast?.('🧠 외부 두뇌 목록 조회 완료', 'success');
                if (window.appendMessageGlobal) window.appendMessageGlobal('assistant', '## 🧠 외부 AI 두뇌 목록\n\n' + msg);
            } catch(e) { window.showToast?.('❌ ' + e.message, 'error'); }
        }},
        { id: 'ext_brain_gemini', title: 'External Brain — Ask Gemini App', icon: '♊', action: () => {
            hidePalette();
            const prompt = window.prompt('Gemini에게 물어볼 질문:');
            if (prompt) {
                fetch('/api/agent/tools/external-brain/send', {
                    method:'POST', headers:{'Content-Type':'application/json'},
                    body: JSON.stringify({prompt, target:'gemini_app'})
                }).then(r=>r.json()).then(d=> {
                    if(d.ok) window.showToast?.(`♊ Gemini 응답 (${d.latency_ms}ms)`, 'success');
                    else window.showToast?.('❌ '+d.error, 'error');
                });
            }
        }},
        { id: 'ext_brain_compare', title: 'External Brain — Compare All', icon: '⚖️', action: () => {
            hidePalette();
            const prompt = window.prompt('모든 외부 두뇌에 동시에 물어볼 질문:');
            if (prompt) {
                window.showToast?.('⚖️ 비교 모드 실행 중...', 'info');
                fetch('/api/agent/tools/external-brain/send', {
                    method:'POST', headers:{'Content-Type':'application/json'},
                    body: JSON.stringify({prompt, strategy:'compare'})
                }).then(r=>r.json()).then(d=> {
                    if(d.ok) {
                        window.showToast?.('⚖️ 비교 완료', 'success');
                        if (window.appendMessageGlobal) window.appendMessageGlobal('assistant', d.text);
                    } else window.showToast?.('❌ '+d.error, 'error');
                });
            }
        }},
    ];

    function navigateTo(pageId) {
        const item = document.querySelector(`.nav-item[data-page="${pageId}"]`);
        if (item) {
            item.click();
        }
        hidePalette();
    }

    function togglePalette() {
        isVisible = !isVisible;
        overlay.style.display = isVisible ? 'flex' : 'none';
        if (isVisible) {
            input.value = '';
            selectedIndex = 0;
            renderResults(availableCommands);
            setTimeout(() => input.focus(), 50);
        }
    }

    function hidePalette() {
        isVisible = false;
        overlay.style.display = 'none';
    }

    window.openCommandPalette = () => {
        if (!isVisible) togglePalette();
    };
    window.toggleCommandPalette = togglePalette;

    const triggerButton = document.getElementById('open-command-palette-btn');
    if (triggerButton) {
        triggerButton.addEventListener('click', () => togglePalette());
    }

    function renderResults(results) {
        currentResults = results;
        selectedIndex = Math.min(selectedIndex, Math.max(results.length - 1, 0));
        resultsContainer.innerHTML = '';
        if (results.length === 0) {
            resultsContainer.innerHTML = '<div style="padding: 20px; color: #888; text-align: center;">No results found</div>';
            return;
        }

        results.forEach((cmd, index) => {
            const div = document.createElement('div');
            div.className = `cmd-item ${index === selectedIndex ? 'selected' : ''}`;
            const subTitle = cmd.subtitle ? `<span class="cmd-item-subtitle" style="font-size:0.8em;color:#888;margin-left:10px;">${cmd.subtitle}</span>` : '';
            div.innerHTML = `
                <span class="cmd-item-icon">${cmd.icon}</span>
                <span class="cmd-item-title">${cmd.title}</span>
                ${subTitle}
            `;
            div.addEventListener('click', () => {
                cmd.action();
                hidePalette();
            });
            resultsContainer.appendChild(div);
        });
    }

    function moveSelection(delta) {
        if (currentResults.length === 0) return;
        selectedIndex = (selectedIndex + delta + currentResults.length) % currentResults.length;
        renderResults(currentResults);
    }

    function runSelected() {
        const cmd = currentResults[selectedIndex];
        if (!cmd) return;
        cmd.action();
        hidePalette();
    }

    let searchTimeout = null;

    function getLocalMatches(query) {
        const normalized = query.toLowerCase();
        return availableCommands.filter(cmd =>
            cmd.title.toLowerCase().includes(normalized) || cmd.id.includes(normalized)
        );
    }

    async function performSearch(query) {
        if (!query) {
            selectedIndex = 0;
            renderResults(availableCommands);
            return;
        }

        try {
            // Include fixed commands that match
            const localFiltered = getLocalMatches(query);

            const response = await fetch(`/v1/notes/search?q=${encodeURIComponent(query)}`);
            if (!response.ok) throw new Error('Search failed');

            const data = await response.json();
            const apiResults = [];

            // Add Semantic Results
            if (data.semantic_results && data.semantic_results.length > 0) {
                data.semantic_results.forEach(res => {
                    apiResults.push({
                        id: 'rag_res',
                        title: res.text.substring(0, 40) + '...',
                        subtitle: 'Semantic Match',
                        icon: '🧠',
                        action: () => {
                            const path = res.metadata?.source || res.id;
                            navigateTo('wiki');
                            setTimeout(() => window.dispatchEvent(new CustomEvent('open-wiki-note', { detail: path })), 150);
                        }
                    });
                });
            }

            // Add Keyword Results
            if (data.keyword_results && data.keyword_results.length > 0) {
                data.keyword_results.forEach(path => {
                    apiResults.push({
                        id: 'kw_res',
                        title: path,
                        subtitle: 'Keyword Match',
                        icon: '📄',
                        action: () => {
                            navigateTo('wiki');
                            setTimeout(() => window.dispatchEvent(new CustomEvent('open-wiki-note', { detail: path })), 150);
                        }
                    });
                });
            }

            selectedIndex = 0;
            renderResults([...localFiltered, ...apiResults]);
        } catch (error) {
            console.error('Search error:', error);
            selectedIndex = 0;
            const localFiltered = getLocalMatches(query);
            renderResults(localFiltered.length > 0
                ? localFiltered
                : [{ id: 'error', title: 'Error searching notes', icon: '⚠️', action: () => {} }]
            );
        }
    }

    // Keyboard bindings
    document.addEventListener('keydown', (e) => {
        // Cmd+K (Mac) or Ctrl+K (Windows/Linux)
        if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
            e.preventDefault();
            togglePalette();
        }

        if (isVisible && e.key === 'Escape') {
            hidePalette();
        }

        if (isVisible && e.key === 'ArrowDown') {
            e.preventDefault();
            moveSelection(1);
        }

        if (isVisible && e.key === 'ArrowUp') {
            e.preventDefault();
            moveSelection(-1);
        }

        if (isVisible && e.key === 'Enter') {
            e.preventDefault();
            runSelected();
        }

        // TDD Shortcut Cmd+Shift+D
        if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key.toLowerCase() === 'd') {
            e.preventDefault();
            const tddCmd = availableCommands.find(c => c.id === 'tdd_loop');
            if (tddCmd) tddCmd.action();
        }
    });

    // Close on overlay click
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) {
            hidePalette();
        }
    });

    // Filter results on input with debounce
    input.addEventListener('input', (e) => {
        const query = e.target.value;
        if (searchTimeout) clearTimeout(searchTimeout);
        selectedIndex = 0;
        renderResults(query ? getLocalMatches(query) : availableCommands);
        searchTimeout = setTimeout(() => {
            performSearch(query);
        }, 300); // 300ms debounce
    });
});
