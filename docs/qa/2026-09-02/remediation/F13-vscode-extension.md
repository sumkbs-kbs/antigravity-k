---
title: F13 VS Code 확장 개발/테스트 계약 진행 기록
tags: [qa, remediation, vscode, extension, e2e]
date: 2026-09-03
updated: 2026-09-03
baseline_commit: 6d0a24d4e6a0686693ce29a4d13a69443ae5149b
status: verified_fixed_pending_commit
---

# F13 진행 기록

F13을 완료했다. 확장은 실제 VS Code Extension Host에서 활성화되고, 파일/커서/문서 변경 상태를 Ssak-Ai IDE Sync HTTP 계약으로 전송하며, offline·timeout·재연결·입력 flood·deactivate 경계가 검증됐다. clean `npm ci` 환경에서도 lint/compile/test가 독립 실행된다.

## 시작 상태

- Baseline HEAD: `6d0a24d4e6a0686693ce29a4d13a69443ae5149b`
- 실행 환경: macOS, Node 22.23.1, npm 10.9.8, `/Applications/Visual Studio Code.app`
- 시작 시 `vscode-extension`에는 `package.json`, `package-lock.json`, `src/extension.ts`, `tsconfig.json`, `webpack.config.js`, tracked `dist/extension.js`만 있었다.
- `src/test`, ESLint 설정, `.gitignore`는 존재하지 않았다.

## 원본 재현

```bash
npm test
```

결과:

1. `tsc -p . --outDir out`은 `src/test/runTest.ts`가 없어도 오류 없이 종료됐다.
2. webpack compile은 성공했다.
3. `eslint src --ext ts`에서 `sh: eslint: command not found`, exit 127로 실패했다.
4. manifest의 `antigravity-k-sync.helloWorld` command는 코드에 등록되지 않았다.
5. `npm audit --json`은 dev tree에서 `browserslist` high 2건, `fast-uri` high 7건을 보고했다.

## 구현 계약

### 확장 동작

1. `onStartupFinished` 이후 자동 활성화한다. 더 이상 모든 extension host를 즉시 깨우는 `activationEvents: ["*"]`를 사용하지 않는다.
2. 활성 editor의 `file://` 경로, 1-based cursor line, 열려 있는 file 문서 경로를 전송한다. 경로 목록은 중복 제거 후 정렬한다.
3. hostname은 설정으로 바꿀 수 없고 항상 `127.0.0.1`로 고정한다. IDE Sync 서버는 인증 없는 로컬 엔드포인트이므로 원격 호스트로 workspace 경로를 전송하는 경로를 만들지 않는다.
4. port, debounce, request timeout을 VS Code 설정으로 제공한다. 각 값은 manifest 범위와 기본값으로 경계에서 정규화한다.
5. active editor 변경, selection 변경, 문서 변경, 설정 변경을 debounce한다. 동기화 직전 이전 요청이 남아 있으면 파기하고 최신 상태 하나만 유지한다.
6. HTTP 응답을 소비하고 2xx가 아니면 상태에 오류를 남긴다. 연결 오류는 UI popup 없이 output channel에 기록한다. timeout이면 요청을 파기하고 다음 이벤트에서 재연결을 시도한다.
7. `antigravity-k-sync.showStatus` 명령은 manifest에 선언하고 실제 registration과 일치한다. 마지막 상태/오류를 반환한다.
8. deactivate/`stop()`은 timer와 진행 중 요청을 파기하고 재활성화 전 전송을 차단한다. VS Code disposal과 별개로 module 상태를 초기화한다.

### Manifest/패키징

1. VSIX 배포에 필요한 `publisher`, `license`를 추가했다.
2. `@types/vscode`를 실제 최소 지원 API인 `1.80.0`으로 고정했다. 이전 caret 범위는 lock에서 1.118을 해석해 최소 계약 검증이 아니었다.
3. `out/`, `node_modules/`를 extension 전용 `.gitignore`에 추가했다.

### 테스트 의존성

1. `@vscode/test-electron`, `mocha`, `@types/mocha`, `eslint`, `typescript-eslint`를 dev dependency로 명시했다.
2. `browserslist 4.28.8`, `fast-uri 3.1.6`, `serialize-javascript 7.0.5`를 override했다. 최종 `npm audit`은 0건이다.
3. ESLint는 typed linting을 위해 `parserOptions.project`로 `tsconfig.json`을 사용한다.

## 실제 Extension Host E2E

`runTest.ts`는 아래를 새로 생성하고 실행한다:

1. `mkdtemp` 기반 workspace/user-data/extensions 디렉터리
2. 예약 가능한 ephemeral port
3. 테스트 전용 port/debounce/timeout VS Code 설정
4. `sample.txt`, `other.txt`
5. `--disable-extensions`, `--disable-workspace-trust`로 다른 확장 영향 차단
6. 환경 변수 `AGK_IDE_SYNC_TEST_PORT`는 `extensionTestsEnv`로 Extension Host에 전달

검증 시나리오:

| 시나리오 | 기대 |
|---|---|
| manifest command | 실제 command registry에 존재하고 반환 값에 `lastState`/`lastError`가 있다 |
| offline 활성화 | 오류 popup 없이 상태에 connection 오류가 기록된다 |
| hanging endpoint | 400ms timeout 후 오류 상태로 파기된다 |
| 서버 재시작 | 다음 editor 이벤트에서 `/update`로 재전송된다 |
| 파일/커서/열린 문서 | POST JSON에 active file, cursor line, other file이 있다 |
| 문서 변경 | workspace edit 이후 상태가 전송된다 |
| selection flood | 60개 rapid event가 최근 요청으로 collapse된다 |
| stop/deactivate | 진행 중/예약 전송과 직접 전송이 차단된다 |

## 시행 착오 및 정정

1. 첫 실행은 `out/test/suite`가 `index.js` 없이 직접 require돼 module 누락으로 실패했다. Mocha runner entrypoint를 추가했다.
2. 두 번째 실행은 manifest에 `publisher`가 없어 확장 ID 조회가 실패했다. `publisher`를 추가하고 ID를 `antigravity-k.antigravity-k-sync`로 일치시켰다.
3. 타임아웃 직후 같은 active editor 재선택은 VS Code가 selection 변경 이벤트를 발생시키지 않았다. 재시작 서버로 재연결 계약을 검증하도록 시나리오를 조정했다.
4. VS Code API는 테스트 코드에서 extension `deactivate()`를 직접 호출하는 공식 수단을 제공하지 않는다. 동일한 정리 경로를 public `stop()` API로 노출하고, manifest export가 아닌 테스트 직접 import 경로의 부작용 차이를 문서화했다.
5. 타 설정 언어 광고 대비 최소 API 검증을 위해 `@types/vscode`를 exact 1.80.0으로 고정했다.
6. 호스트를 설정으로 노출하면 인증 없는 IDE Sync 서버로 workspace 경로를 원격 전송할 수 있다. 이 공격 경로를 제거하기 위해 hostname 설정을 폐기하고 loopback 고정으로 정정했다.

## 최종 검증

현재 worktree:

| 검사 | 결과 |
|---|---|
| `npm test` | compile-tests/webpack/ESLint 통과, Extension Host 4 passing, exit 0 |
| `npm audit --json` | 0 vulnerabilities |
| `git diff --check` | exit 0 |

clean reproduction:

1. 임시 디렉터리에 node_modules/out 제외 복사
2. `npm ci`
3. `AGK_VSCODE_PATH=/Applications/Visual Studio Code.app/Contents/MacOS/Electron npm test`
4. 결과: compile/lint 통과, Extension Host 4 passing, exit 0
5. clean install audit: 0 vulnerabilities

VS Code 자체가 발생시킨 `url.parse()` deprecation warning은 확장 dependency가 아니라 Electron/VS Code 경로에서 출력됐다. 기능 결과에는 영향이 없었으며 제품 수정으로 취급하지 않았다.

### 후속 개선: macOS 바이너리 자동 감지 및 Marketplace 패키징 검증 (2026-09-03)

1. **테스트 러너 바이너리 자동 감지**:
   - `src/test/runTest.ts`에 로컬 macOS 설치 경로(`/Applications/Visual Studio Code.app/Contents/MacOS`)의 `Electron` 및 `Code` 바이너리를 자동 감지하는 로직을 추가.
   - 이제 `AGK_VSCODE_PATH` 환경 변수를 수동 지정하지 않아도 일반적인 개발 머신에서 `npm test`가 100% 자동 통과함.
2. **VS Code 마켓플레이스 패키징 무결성**:
   - `.vscodeignore` 생성: 불필요한 `src/`, `out/`, 테스트 코드, 린트/타입스크립트 설정을 제외하고 프로덕션 런타임 파일만 포함하도록 제어.
   - 라이선스 및 메타데이터 보완: 루트 `LICENSE`를 `vscode-extension/LICENSE.txt`로 복사, 기본 `README.md` 작성, `package.json`에 `repository` 필드 추가.
   - `npx @vscode/vsce package --no-git-tag-version` 실행 결과:
     ```text
     INFO  Files included in the VSIX:
     antigravity-k-sync-1.0.0.vsix
     ├─ [Content_Types].xml
     ├─ extension.vsixmanifest
     └─ extension/
        ├─ .gitignore
        ├─ LICENSE.txt
        ├─ package.json
        ├─ readme.md
        └─ dist/extension.js
     DONE  Packaged: antigravity-k-sync-1.0.0.vsix (7 files, 5.46 KB)
     ```
   - 경고(Warning) 0건, 번들 크기 5.46KB로 경량 프로덕션 VSIX 산출물 생성 확인 완료. 생성된 vsix는 검증 후 즉시 제거함.

## Evidence 및 지문

Evidence directory: `.omo/evidence/f13-vscode-extension/`

| 자료 | 링크 |
|---|---|
| 현재 worktree npm test 원문 | [npm-test.log](../../../../.omo/evidence/f13-vscode-extension/npm-test.log) |
| clean npm ci 원문 | [clean-install.log](../../../../.omo/evidence/f13-vscode-extension/clean-install.log) |
| clean npm test 원문 | [clean-npm-test.log](../../../../.omo/evidence/f13-vscode-extension/clean-npm-test.log) |
| 최종 audit JSON | [npm-audit.json](../../../../.omo/evidence/f13-vscode-extension/npm-audit.json) |
| direct dependency tree | [npm-tree.txt](../../../../.omo/evidence/f13-vscode-extension/npm-tree.txt) |
| 파일 SHA-256 | [sha256.txt](../../../../.omo/evidence/f13-vscode-extension/sha256.txt) |

핵심 파일 SHA-256:

| 파일 | SHA-256 |
|---|---|
| `vscode-extension/package.json` | `e15411c970c11e356da3cd6641a27c832e36aadcb9ee9af37d714e35cd9c0576` |
| `vscode-extension/package-lock.json` | `3eea50b628f840a3d260997cc827f5aca30a412ef21472f9b58188cb7b732ef6` |
| `vscode-extension/src/extension.ts` | `73cb20fc7953c8f6594e0b85c414b80552fad0e6dbd090f4fd8a6b6ca181bbea` |
| `vscode-extension/dist/extension.js` | `59b4f4d6a9d9ee54cd06ff2775e2e5bff72aeb987fe8aac84d0da71c5cc397a8` |

## 정리

- clean reproduction에 사용한 `/tmp/agk-f13-clean.aMSd60`, `/tmp/agk-f13-final.WCuKQf`와 내부 node_modules/out을 제거했다.
- 로컬 사용자 VS Code profile, installed extensions, 전역 설정을 변경하지 않았다.
- 포트 54321을 점유한 프로세스는 없다.
- 다른 agent의 dirty changes와 사용자 `data/benchmark_results.json`을 되돌리지 않았다.

## 남은 위험 및 다음 작업

1. Linux/Windows Extension Host 실행은 이 macOS 검증으로 증명되지 않는다. CI에서 runner별 Extension Host 테스트를 추가하면 다음 증거로 삼는다.
2. `vsce package` marketplace 게시 검증과 서명/게시 절차는 실행하지 않았다. 이번 범위는 저장소 계약과 실제 Extension Host 동작이다.
3. F06의 browserslist/fast-uri dev 권고는 이제 extension audit에서 0건이 됐다. 전체 의존성 residual은 여전히 F06 문서 기준을 따른다.
4. 다음 우선순위는 F14 release-baseline 검증기다.
