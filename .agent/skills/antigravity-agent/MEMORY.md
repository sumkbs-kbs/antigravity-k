---
name: antigravity-agent-memory
description: Antigravity-K의 메모리 관리 가이드 — User.md/的记忆.md 구조, 하드리밋 관리, 월간 정리
version: "1.0.0"
tags: [memory, user, management, hard-limit]
triggers: ["메모리", "기억", "user.md", "memory.md"]
---

# MEMORY.md — 메모리 관리 가이드

## 메모리 공간 구조

### User.md (사용자 정보) — 1,375자 한도
- 사용자의 기본 정보: 이름, 역할, 선호도, 업무 패턴
- 선호하는 응답 방식, 도메인 관심사
- **매월 1일 자동 검토 → 정리/압축**

### Memory.md (에이전트 기억) — 2,200자 한도
- 세션 내 학습: 작업 패턴, 발견한 conventions, 피해야 할 것들
- 프로젝트별 상태 추적: Antigravity-K 진행 상태, Wiki 구조 등
- **매월 1일 자동 검토 → 정리/압축**

### Memory Context Injection
- 세션 시작 시 한 번 주입 → **같은 세션 내 변경사항은 다음 세션까지 반영 안 됨**
- 따라서 메모리는 섹션별로 관리하고, 변경사항은 세션 사이마다 갱신

## 한계 관리 (하드리밋)

| 공간 | 한도 | 주요 내용 |
|-----|-|--|
| User.md | 1,375자 | 사용자 프로필, 선호도 |
| Memory.md | 2,200자 | 에이전트 학습, 패턴, conventions |
| Wiki | 제한없음 | 영구 지식 아카이브 |

## 정리 규칙

### 월간 정리 (매월 1일 11:00)
1. Memory.md에서 "불필요한 정보" 식별:
   - 완료된 작업 추적 (과거 상태 → 삭제)
   - 너무 상세한 기술 정보 (Wiki로 이동)
   - 일반 지식 (Wiki → Memory 이동)
2. "압축 후보" 추천 → 사용자가 확인
3. User.md: 선호도 반영된 최신 정보만 유지

### 일일 정리 (매일 자정)
- **불필요**: 일일 정리는 메모리 낭비
- **필요**: 당일 발견한 새로운 패턴만 메모

### 작성 원칙
- **영문 권장**: 토큰 효율 ↑ (한글 표현은 뉘앙스 중요한 부분만)
- **핵심 사실만**: "왜"보다 "무엇"에 집중
- **접두사 사용**: `[P]` 중요, `[S]` 상태, `[A]` 액션

## 예시: User.md 구조
```yaml
name: K (강병석)
role: Developer/Researcher
domain: 금융 > AI트렌드 > 코딩
preference: 한국어, 간결, 실용적
devices: MacBook M5Max 128GB, Android
memory: Wiki 외부 장기 기억
```

## 예시: Memory.md 구조
```yaml
last_reviewed: 2026-06-01
active_projects:
  - Antigravity-K: Soul/Agent 구조 완성 중
  - Wiki: broken link audit 완료
patterns: [한국어 응답, Cross-domain, 결론-근거-액션 순]
pitfalls: [git merge 충돌 지속, tree 명령어 unavailable]
```
