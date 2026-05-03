import * as vscode from 'vscode';
import * as http from 'http';

export function activate(context: vscode.ExtensionContext) {
    console.log('Antigravity-K IDE Sync extension is now active!');

    // 전송 로직
    const sendState = () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor) { return; }

        const activeFile = editor.document.uri.fsPath;
        const cursorLine = editor.selection.active.line + 1;
        
        // 열린 파일 목록
        const openFiles = vscode.workspace.textDocuments
            .map(doc => doc.uri.fsPath)
            .filter((value, index, self) => self.indexOf(value) === index);

        const payload = JSON.stringify({
            active_file: activeFile,
            cursor_line: cursorLine,
            open_files: openFiles
        });

        const req = http.request({
            hostname: '127.0.0.1',
            port: 54321,
            path: '/update',
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Content-Length': Buffer.byteLength(payload)
            }
        }, (res) => {
            // 응답 무시 (조용히 실패 허용)
        });

        req.on('error', (e) => {
            // 서버가 꺼져있어도 에러 팝업을 띄우지 않음
        });

        req.write(payload);
        req.end();
    };

    // 이벤트 리스너 등록
    let disposable1 = vscode.window.onDidChangeActiveTextEditor(sendState);
    let disposable2 = vscode.window.onDidChangeTextEditorSelection(sendState);

    context.subscriptions.push(disposable1, disposable2);
}

export function deactivate() {}
