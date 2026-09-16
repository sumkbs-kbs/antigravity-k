# NX-08 — before (기준 나무에서 측정)

카드: `docs/19_RELIABILITY_AND_CONNECTOME_CHECKLIST.md` §NX-08 (NX-03 잔여 의혹 재검증)
측정 시각: 2026-09-16
기준: `git archive HEAD src` 를 `/tmp/nx08-before/src` 에 추출한 **HEAD 엔진**(작업 트리 무변경)
드라이버: `repro_nx08_vault_persistence.py --label before --src /tmp/nx08-before/src`
원자료: `before-run-output.json` (드라이버 stdout 전체)

## 왜 작업 트리가 아니라 추출본을 재는가

이 드라이버는 SIGKILL·fsync 실패·lock 잔존을 **실제로** 일으킨다. 이후 수정이 들어가면
같은 명령이 더 이상 before 를 재현하지 못하므로, 기준을 `git archive HEAD` 로 고정해
“같은 자, 다른 나무”로 비교한다. 사용자 vault 는 쓰지 않는다 — 임시 디렉터리에 임시 Git
repo 만 만든다.

## 판정 요약

    verdict_tally: {"CONFIRMED": 6, "NOT_REPRODUCED": 7, "INCONCLUSIVE": 2}

| id | 질문 | 판정 | 관측 핵심 |
|---|---|---|---|
| A1-fsync-failure | fsync 실패 시 저장 전 bytes 가 남는가 | **CONFIRMED** | sha `018bcda…` → `cf898d0…` 로 **바뀜**. `OSError: [Errno 28] No space left on device (주입)` 는 올라왔지만 이전 내용은 이미 사라졌다 |
| A2-crash-mid-write | write 도중 SIGKILL 이면 파일이 잘리는가 | **CONFIRMED** | 자식 exit 9 직후 파일이 `---\ntitle: crash\n---\nBODY-V2\n` (이 중간 상태)이고 git 에는 `dd358f0 v1` 하나. 잘린 내용이 **커밋 후보**로 남았다 |
| B1-lock-after-sigkill | 죽은 프로세스의 lock 이 제품을 막는가 | NOT_REPRODUCED | 3초 후 시도가 `wrote` — filelock 이 같은 호스트 죽은 pid 를 스스로 깬다. lock 파일은 남지만(`29` bytes) 막지 않는다 |
| C1-lf | LF frontmatter 가 정상 파싱되는가 | NOT_REPRODUCED | `{'title': 'T'}` + 본문 유지 |
| C1-crlf | CRLF frontmatter 가 정상 파싱되는가 | **CONFIRMED** | `metadata={}` — frontmatter 가 **통째로 본문으로** 취급됐다(메타데이터 소실) |
| C2-eof-no-newline | 닫는 `---` 로 파일이 끝나면(개행 없음) | **CONFIRMED** | `ValueError: substring not found` — 읽기 자체가 예외로 죽는다 |
| C2-eof-with-newline | 같은 조건 + 개행 | NOT_REPRODUCED | 정상 |
| C3-malformed-yaml / C3-non-mapping | YAML 오류·비매핑 frontmatter | NOT_REPRODUCED | 예외 없이 `{}` 로 흡수, 본문 보존 |
| C4-writer-reader-roundtrip | 쓴 것을 그대로 다시 읽는가 | NOT_REPRODUCED | metadata/body 왕복 일치 |
| D1-snapshot-restore | 스냅샷 복구가 내용·Schema·권한을 지키는가 | **CONFIRMED** | 내용·Schema 는 보존되지만 `0o600 → 0o644` (**권한 확대**) |
| E1-redact-lock | 마스킹이 lock 안에서 도는가 | NOT_REPRODUCED | `['enter', 'exit']` 1회, 비밀값 제거 확인 |
| F2-foreign-host-stale-lock | 다른 호스트가 죽긴 lock 도 깨지는가 | **CONFIRMED** | `blocked_after_3s=True`. filelock 3.29 는 `hostname != socket.gethostname()` 이면 stale lock 을 깨지 **않는다**(의존성 동작) |
| F1-nfs-flock-fsync | NFS 에서 flock/fsync 를 신뢰할 수 있는가 | INCONCLUSIVE | 이 호스트에 NFS 마운트가 없다(`/dev/disk3s5`). 로컬 관측을 다른 파일시스템으로 일반화하지 않는다 |
| G1-tombstone-gc | tombstone GC 경로가 있는가 | INCONCLUSIVE | GC 심볼 없음만 관측 — 정책 결정은 NX-08-F |

## 이 시점의 코드 사실

* `VaultEngine.write_note` 는 `open(file_path, "w")` → `write` → `flush` → `os.fsync` 였다.
  `w` 는 **여는 순간 파일을 자른다** — fsync 가 실패하거나 프로세스가 죽으면 이전 bytes 는
  이미 없다(A1·A2). `VaultCommitError` 타입은 존재했지만 이 경로는 그 계약을 쓰지 않았다.
* `_FRONTMATTER_DELIMITER` 는 `^---[ \t]*$` (MULTILINE) 였다. 파이썬 `$` 는 `\n` 앞에서
  매칭되므로 LF 는 되지만 **CRLF 는 안 된다**(C1-crlf).
* 본문 시작 계산이 `content.index("\n", closing + 3)` — 닫는 구분자 뒤에 개행이 없으면
  `ValueError`(C2-eof-no-newline). `str.index` 는 없는 부분 문자열에 예외를 낸다.
* 복구는 `git restore --source`/`git checkout` 기반이라 **git 이 아는 실행 비트만** 돌아온다.
  `0600` note 가 `0644` 로 완화됐다(D1).
* `vault_privacy._apply_files` 는 같은 `open("w")` 패턴을 썼다 — A1/A2 결함을 그대로 공유한다.

## 미재현(NOT_REPRODUCED)을 “결함 없음”으로 일반화하지 않는 이유

각 NOT_REPRODUCED 는 **그 조건에서만** 관측된 것이다. 특히 B1 은 *같은 호스트*의 죽은 pid
시나리오라서, 같은 호스트가 아닌 lock(F2)에서는 정반대 결과가 나온다 — 그래서 F2 를 따로
측정했고 CONFIRMED 로 남았다.
