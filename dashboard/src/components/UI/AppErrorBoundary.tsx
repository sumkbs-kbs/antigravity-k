/**
 * AppErrorBoundary — 화면 오류 복구 경계 (CR-07)
 * ==============================================
 * 발견 F03: lazy/Suspense만 있고 오류 경계가 없어서 페이지 하나가 던진 예외가
 * 셸 전체(사이드바, 전역 배너, 로그인 이후 UI)를 지웠다.
 *
 * 이 경계는 두 층으로 쓰인다.
 *  - `scope="app"`   : 최상위 최후 boundary. 셸까지 실패했을 때 앱 전체를 대체한다.
 *  - `scope="route"` : route 수준. 페이지 하나가 실패해도 셸과 다른 화면은 살린다.
 *
 * 지키는 계약:
 *  - 오류 식별자(`E-XXXXXXXX`)·재시도·안전 재로드만 보여주고 **원문 메시지/스택을
 *    화면에 노출하지 않는다**(경로·토큰이 섞일 수 있다).
 *  - chunk 로드 실패는 "다시 시도"를 약속하지 않는다. 같은 URL의 실패한 모듈은
 *    다시 import해도 실패하므로 새로고침(reload)만이 실제 복구다.
 *  - 오류 때문에 대화/로컬 히스토리 저장소를 **지우지 않는다**(여기서 어떤 storage도
 *    건드리지 않는다).
 *  - Suspense는 여전히 loading만 담당한다(경계는 실패만 담당).
 */

import React from 'react';

export type AppErrorScope = 'app' | 'route';
export type AppErrorKind = 'chunk' | 'render';

export interface AppErrorBoundaryProps {
  children: React.ReactNode;
  /** 앱 전체 최후 경계인지, route 단위 경계인지(문구만 달라진다). */
  scope?: AppErrorScope;
  /** 테스트/호스트가 재로드를 주입할 수 있다. 기본은 실제 새로고침. */
  onReload?: () => void;
}

interface AppErrorBoundaryState {
  errorId: string | null;
  kind: AppErrorKind;
  /** 같은 오류가 반복될 때 사용자가 "몇 번째 시도인지" 알 수 있게 한다. */
  attempt: number;
}

/** dynamic import 실패를 나타내는 메시지 패턴(브라우저·번들러별 표현). */
const CHUNK_ERROR_PATTERN =
  /dynamically imported module|ChunkLoadError|Loading chunk|Loading CSS chunk|Importing a module script failed|error loading dynamically imported module/i;

/**
 * 오류를 'chunk'(모듈 로드 실패)와 'render'(렌더 중 예외)로 나눈다.
 * 복구 수단이 다르기 때문에 필요하다 — chunk는 새로고침만, render는 재시도가 유효하다.
 */
export function classifyAppError(error: unknown): AppErrorKind {
  const message = error instanceof Error ? error.message : String(error ?? '');
  return CHUNK_ERROR_PATTERN.test(message) ? 'chunk' : 'render';
}

/** FNV-1a 32bit — 원문을 되돌릴 수 없는 짧은 식별자를 만든다. */
function fnv1a(text: string): number {
  let hash = 0x811c9dc5;
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index);
    hash = Math.imul(hash, 0x01000193) >>> 0;
  }
  return hash >>> 0;
}

/** 화면·로그·지원 요청에 쓰는 오류 식별자. 원문 메시지를 담지 않는다. */
export function createErrorId(kind: AppErrorKind, error: unknown): string {
  const name = error instanceof Error ? error.name : typeof error;
  const message = error instanceof Error ? error.message : String(error ?? '');
  const digest = fnv1a(`${kind}|${name}|${message}`).toString(16).toUpperCase().padStart(8, '0');
  return `E-${digest}`;
}

export class AppErrorBoundary extends React.Component<AppErrorBoundaryProps, AppErrorBoundaryState> {
  state: AppErrorBoundaryState = { errorId: null, kind: 'render', attempt: 0 };

  static getDerivedStateFromError(error: unknown): Partial<AppErrorBoundaryState> {
    const kind = classifyAppError(error);
    return { errorId: createErrorId(kind, error), kind };
  }

  componentDidCatch(error: unknown): void {
    // 화면에는 식별자만; 원문은 개발자 콘솔/기존 전역 핸들러로만 남긴다.
    console.error(`[CR-07] 화면 오류 ${this.state.errorId ?? ''}`, error);
  }

  private readonly handleRetry = (): void => {
    this.setState(previous => ({ errorId: null, attempt: previous.attempt + 1 }));
  };

  private readonly handleReload = (): void => {
    if (this.props.onReload) {
      this.props.onReload();
      return;
    }
    window.location.reload();
  };

  render(): React.ReactNode {
    const { children, scope = 'route' } = this.props;
    const { errorId, kind, attempt } = this.state;

    if (errorId === null) {
      // attempt를 key로 써서 재시도가 하위 트리를 실제로 다시 마운트하게 한다.
      return <React.Fragment key={attempt}>{children}</React.Fragment>;
    }

    const isChunk = kind === 'chunk';
    const title = scope === 'app'
      ? '앱 화면을 표시할 수 없습니다'
      : '이 페이지를 표시할 수 없습니다';

    return (
      <div
        data-testid="cr07-recovery"
        data-error-kind={kind}
        data-error-scope={scope}
        role="alert"
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
          maxWidth: 560,
          margin: '48px auto',
          padding: 24,
          border: '1px solid var(--glass-border)',
          borderRadius: 12,
          background: 'var(--glass-bg, rgba(255,255,255,0.03))',
        }}
      >
        <div className="hero-eyebrow">RECOVERY</div>
        <h2 style={{ margin: 0 }}>{title}</h2>
        <p style={{ margin: 0, color: 'var(--text-muted)', fontSize: 14 }}>
          {isChunk
            ? '새 버전이 배포되었거나 네트워크가 끊겼을 수 있습니다. 새로고침하면 최신 화면을 다시 불러옵니다.'
            : '화면을 그리는 중 문제가 발생했습니다. 다시 시도하거나 새로고침하세요. 저장된 대화와 설정은 지워지지 않습니다.'}
        </p>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          {!isChunk && (
            <button type="button" className="btn-primary" data-testid="cr07-retry" onClick={this.handleRetry}>
              ↻ 다시 시도
            </button>
          )}
          <button type="button" className="btn-ghost" data-testid="cr07-reload" onClick={this.handleReload}>
            ⟳ 새로고침
          </button>
          <span
            data-testid="cr07-attempts"
            style={{ fontSize: 12, color: 'var(--text-muted)' }}
          >
            시도 {attempt + 1}회
          </span>
        </div>
        <p style={{ margin: 0, fontSize: 12, color: 'var(--text-muted)' }}>
          문제가 계속되면 아래 식별자를 알려주세요. · 식별자{' '}
          <code data-testid="cr07-error-id">{errorId}</code>
        </p>
        <p style={{ margin: 0, fontSize: 12, color: 'var(--text-muted)' }}>
          새로고침은 저장되지 않은 입력을 지울 수 있습니다. 대화 기록과 API 키 저장은 그대로입니다.
        </p>
      </div>
    );
  }
}

export default AppErrorBoundary;
