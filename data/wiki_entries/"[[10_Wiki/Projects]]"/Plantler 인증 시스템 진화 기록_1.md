---
id: 10
category: "[[10_Wiki/Projects]]"
tags: ["projects", "인증", "보안", "토큰", "자동로그인"]
created: 2026-05-04T09:42:52.093775
---

# [[Plantler 인증 시스템 진화 기록]]

## 📌 한 줄 통찰 (The Karpathy Summary)
> 초기 버전에서는 `SharedPreferences`에 `login_auto_login` 플래그만 저장하고, 앱 시작 시 실제로 체크하지 않았다. 결과적으로:

## 📖 구조화된 지식 (Synthesized Content)
- **추출된 패턴:**
  - 사용자가 앱을 재시작할 때마다 **온보딩 화면**으로 돌아감
  - 토큰이 만료되어 세션이 끊김
  - UX가 매우 나빴음
  - `AuthService.loadToken()` → 저장된 토큰 로드
  - `AuthService.tryRefreshAccessToken()` → 백그라운드에서 토큰 갱신

- **세부 내용:**
  - 초기 버전에서는 `SharedPreferences`에 `login_auto_login` 플래그만 저장하고, 앱 시작 시 실제로 체크하지 않았다. 결과적으로:
  - 1. 사용자 로그인 → Access Token + Refresh Token 발급
  - 2. Access Token 만료 → Refresh Token(30일)으로 자동 갱신
  - 3. 앱 시작 시 `main.dart`에서 **runApp() 이전에** 토큰 체크
  - > "인증은 앱의 첫 인상이다. 자동 로그인이 안 되면 사용자는 앱을 버린다."

## ⚠️ 모순 및 업데이트 (Contradictions & RL Update)
- **과거 데이터와의 충돌:** 현재까지 발견된 모순 없음.
- **정책 변화:** 이 문서를 통해 분류 정책에 변화 없음.

## 🔗 지식 연결 (Graph)
- **Parent:** [[Projects]]
- **Related:** [[Plantler 인증 시스템 진화 기록]]
- **Raw Source:** [[00_Raw/03_인증_시스템_진화.md]]
