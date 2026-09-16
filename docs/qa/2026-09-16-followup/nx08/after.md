# NX-08 — after (수정 후, 같은 드라이버)

측정 시각: 2026-09-16
대상: **작업 트리** 엔진(수정 포함), 드라이버 `--label after`
원자료: `after-run-output.json`

## 판정 요약

    before: {"CONFIRMED": 6, "NOT_REPRODUCED": 7, "INCONCLUSIVE": 2}
    after:  {"CONFIRMED": 1, "NOT_REPRODUCED": 12, "INCONCLUSIVE": 2}

| id | before | after | after 관측 |
|---|---|---|---|
| A1-fsync-failure | CONFIRMED | **NOT_REPRODUCED** | sha 가 `018bcda…` 그대로. 오류는 `VaultCommitError: Vault bytes could not be persisted: …/note.md` 로 **타입화**되어 올라온다 |
| A2-crash-mid-write | CONFIRMED | **NOT_REPRODUCED** | 자식 exit 9 뒤 파일이 `---\ntitle: v1\n---\nBODY-V1\n` = 이전 bytes 와 **동일**, git 에는 `v1` 하나 |
| C1-crlf | CONFIRMED | **NOT_REPRODUCED** | `{'title': 'T', 'tags': ['a']}` — frontmatter 정상 인식 |
| C2-eof-no-newline | CONFIRMED | **NOT_REPRODUCED** | 예외 없음, `{'title': 'T'}` |
| D1-snapshot-restore | CONFIRMED | **NOT_REPRODUCED** | `original_mode 0o600 / after_mode 0o600`, 내용·Schema 보존 |
| F2-foreign-host-stale-lock | CONFIRMED | **CONFIRMED (미해결)** | 남는다 — 외부 의존성(filelock) 동작이라 코드로 없애지 않았다. 아래 참조 |
| B1 / C1-lf / C2-with-newline / C3 ×2 / C4 / E1 | NOT_REPRODUCED | NOT_REPRODUCED | 회귀 없음(같은 조건, 같은 결과) |
| F1-nfs / G1-tombstone-gc | INCONCLUSIVE | INCONCLUSIVE | 관측 조건이 그대로 — 아래 “남긴 것” 참조 |

## 실제 변경 (제품 코드 3파일 +176/−18)

### 1) `engine/vault.py` — 저장이 자르지 않는다 (A1·A2 해결)

`write_text_atomically(path, text)` 신설, 순서는 CR-02 세션 저장과 **같은 계약**:

1. 같은 디렉터리에 `.<name>.<pid>.<token>.tmp` 를 `O_CREAT|O_EXCL` 로 생성
   (이전 파일의 `st_mode` 를 `fchmod` 로 승계 → 저장이 권한을 넓히지 않는다)
2. `write` → `flush` → `fsync` (여기서 죽어도 **원본은 그대로**)
3. `os.replace` (같은 파일시스템 rename = 원자적)
4. 디렉터리 fsync (미지원 FS 는 통과 — rename 은 이미 끝났다)

`_fsync_fd` · `_replace_file` 을 이름 있는 한 줄짜리로 분리한 이유는 실패 주입 지점을
시험이 안정적으로 붙잡게 하기 위함이다(monkeypatch 대상이 분명해진다).

replace **이전** 실패에서만 정리한다(`_cleanup_failed_write`). 60초 이상 된, 죽은 pid 의
같은 대상 `.tmp` 는 다음 저장이 수거한다(살아 있는지 확신할 수 없으면 지우지 않는다).

`write_note` 는 이 함수를 쓰고, 실패는 `VaultCommitError` 로 올린다.

### 2) `engine/vault.py` — 읽기 두 결함 (C1-crlf·C2-eof)

* 구분자 정규식 `^---[ \t]*\r?$` — CRLF 파일의 frontmatter 가 본문으로 새던 것을 막는다.
* 본문 시작: `content.index(...)` → `content.find(...)`, `-1` 이면 **빈 본문**. 닫는 구분자로
  파일이 끝나는 정상 파일이 예외로 죽지 않는다.

### 3) `engine/vault.py` + `engine/vault_privacy_git.py` — 복구가 권한을 넓히지 않는다 (D1)

복구 전 대상 파일의 `st_mode` 를 기록해 두고, git 복구 **뒤에** 되돌려 놓는다. git 은 실행
비트만 추적하므로 이 보정이 없으면 복구가 `0600` 을 `0644` 로 완화한다. 운영자가 좁혀 둔
권한을 복구가 넓히는 것은 조용한 보안 회귀다.

### 4) `engine/vault_privacy.py` — 마스킹도 같은 계약 (A1·A2 파급)

`_apply_files` 의 `path.open("w")` 을 `write_text_atomically` 로 교체. 마스킹은 비밀값을
지우는 경로라서, 여기서 잘리면 **원문이 남거나 파일이 깨진다** — 가장 위험한 곳이었다.

## F2 를 왜 남겼는가

`filelock` 3.29 의 `SoftFileLock._try_break_stale_lock` 은
`hostname != socket.gethostname()` 이면 **즉시 return** 한다(다른 호스트가 만든 lock 은
살아 있다고 본다). 이건 우리 코드가 아니라 의존성의 안전 선택이고, 우리가 우회하려면
파일시스템 lock 자체를 갈아엎어야 한다. 카드 규칙대로 **미해결로 남기고** 복구 절차
(`.git/.agk_vault.lock` 수동 제거)를 문서에 남긴다 — 단일 호스트 배포(현재 제품 형태)에서는
발생하지 않고, SHARED 볼륨 다중 인스턴스 구성에서만 유효하다.

## 시험 조건의 한계 (그대로 적는다)

* 드라이버는 **이 호스트의 로컬 파일시스템**에서만 돌았다. NFS/SMB 관측이 아니므로 F1 은
  여전히 INCONCLUSIVE 다.
* A2 의 SIGKILL 은 자식 프로세스의 `os.fsync` 를 바꿔치기해 죽인다 — 커널 전원 차단을
  재현한 것이 아니라 “정리 코드가 실행되지 않는 종료”를 재현한 것이다.
* D1 은 복구 대상이 git 추적 파일일 때만 의미가 있다(추적 밖 파일은 복구 대상이 아니다).
