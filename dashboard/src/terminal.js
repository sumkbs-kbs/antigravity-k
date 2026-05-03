// Terminal integration using xterm.js

let term;
let fitAddon;
let ws;
let terminalContainer;
let rightSplit;

export function initTerminal() {
    const toggleBtn = document.getElementById('toggle-terminal-btn');
    terminalContainer = document.getElementById('terminal-container');
    const rightContainer = document.getElementById('right-container');
    const mainContent = document.getElementById('main-content');
    
    if (!toggleBtn || !terminalContainer || typeof Terminal === 'undefined') {
        console.error("Terminal dependencies not loaded");
        return;
    }

    toggleBtn.addEventListener('click', () => {
        if (terminalContainer.style.display === 'none') {
            // Open terminal
            terminalContainer.style.display = 'block';
            toggleBtn.innerHTML = '💻 터미널 닫기';
            
            // Setup vertical split between main-content and terminal
            if (!rightSplit) {
                rightSplit = Split(['#main-content', '#terminal-container'], {
                    direction: 'vertical',
                    sizes: [70, 30],
                    minSize: [200, 100],
                    gutterSize: 6,
                    cursor: 'row-resize',
                    onDragEnd: () => {
                        if (fitAddon) fitAddon.fit();
                    }
                });
            }

            if (!term) {
                setupTerminal();
            } else {
                setTimeout(() => fitAddon.fit(), 100);
            }
        } else {
            // Close terminal
            terminalContainer.style.display = 'none';
            toggleBtn.innerHTML = '💻 터미널 토글';
            
            // Reset split
            if (rightSplit) {
                rightSplit.destroy();
                rightSplit = null;
            }
            mainContent.style.height = '100%';
        }
    });
}

function setupTerminal() {
    term = new Terminal({
        theme: {
            background: '#0f1117',
            foreground: '#f3f4f6'
        },
        fontFamily: '"JetBrains Mono", monospace',
        fontSize: 13,
        cursorBlink: true
    });
    
    fitAddon = new FitAddon.FitAddon();
    term.loadAddon(fitAddon);
    term.open(document.getElementById('terminal'));
    fitAddon.fit();

    // Connect WebSocket
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/terminal`;
    
    connectWebSocket(wsUrl);

    window.addEventListener('resize', () => {
        if (terminalContainer.style.display !== 'none' && fitAddon) {
            fitAddon.fit();
        }
    });
}

function connectWebSocket(url) {
    ws = new WebSocket(url);
    
    ws.onopen = () => {
        term.writeln('\x1b[32m[Antigravity-K] Terminal connected.\x1b[0m');
        
        term.onData(data => {
            if (ws.readyState === WebSocket.OPEN) {
                ws.send(data);
            }
        });

        // Send resize event
        term.onResize(size => {
            if (ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({
                    type: 'resize',
                    cols: size.cols,
                    rows: size.rows
                }));
            }
        });
        
        fitAddon.fit();
    };

    ws.onmessage = (event) => {
        term.write(event.data);
    };

    ws.onclose = () => {
        term.writeln('\x1b[31m[Antigravity-K] Terminal disconnected.\x1b[0m');
        // Reconnect after 3s
        setTimeout(() => connectWebSocket(url), 3000);
    };
    
    ws.onerror = (err) => {
        console.error("Terminal WebSocket error:", err);
    };
}
