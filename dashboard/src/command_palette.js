document.addEventListener('DOMContentLoaded', () => {
    const overlay = document.getElementById('command-palette-overlay');
    const input = document.getElementById('cmd-input');
    const resultsContainer = document.getElementById('cmd-results');
    
    let isVisible = false;

    // Dummy commands for UI demonstration
    const availableCommands = [
        { id: 'search', title: 'Search Notes', icon: '🔍', action: () => console.log('Search invoked') },
        { id: 'new_note', title: 'Create New Note', icon: '📝', action: () => console.log('New note') },
        { id: 'chat', title: 'Open AI Chat', icon: '💬', action: () => navigateTo('chat') },
        { id: 'settings', title: 'Preferences', icon: '⚙️', action: () => navigateTo('settings') },
        { id: 'sync', title: 'Sync Vault (Git)', icon: '🔄', action: () => console.log('Vault synced') },
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
            renderResults(availableCommands);
            setTimeout(() => input.focus(), 50);
        }
    }

    function hidePalette() {
        isVisible = false;
        overlay.style.display = 'none';
    }

    function renderResults(results) {
        resultsContainer.innerHTML = '';
        if (results.length === 0) {
            resultsContainer.innerHTML = '<div style="padding: 20px; color: #888; text-align: center;">No results found</div>';
            return;
        }

        results.forEach((cmd, index) => {
            const div = document.createElement('div');
            div.className = `cmd-item ${index === 0 ? 'selected' : ''}`;
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

    let searchTimeout = null;
    
    async function performSearch(query) {
        if (!query) {
            renderResults(availableCommands);
            return;
        }
        
        try {
            // Include fixed commands that match
            const localFiltered = availableCommands.filter(cmd => 
                cmd.title.toLowerCase().includes(query.toLowerCase()) || cmd.id.includes(query.toLowerCase())
            );
            
            const response = await fetch(`http://localhost:8000/v1/notes/search?q=${encodeURIComponent(query)}`);
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
                        action: () => console.log('Opened RAG result:', res)
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
                        action: () => console.log('Opened Note:', path)
                    });
                });
            }
            
            renderResults([...localFiltered, ...apiResults]);
        } catch (error) {
            console.error('Search error:', error);
            renderResults([{ id: 'error', title: 'Error searching notes', icon: '⚠️', action: () => {} }]);
        }
    }

    // Keyboard bindings
    document.addEventListener('keydown', (e) => {
        // Cmd+K (Mac) or Ctrl+K (Windows/Linux)
        if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
            e.preventDefault();
            togglePalette();
        }

        if (isVisible && e.key === 'Escape') {
            hidePalette();
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
        searchTimeout = setTimeout(() => {
            performSearch(query);
        }, 300); // 300ms debounce
    });
});
