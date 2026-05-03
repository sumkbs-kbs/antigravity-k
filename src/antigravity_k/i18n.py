"""
i18n — 에이전트 다국어 지원 시스템
===================================

tiptap-vuetify의 i18n 패턴에서 영감:
- Vuetify.lang.current에서 자동으로 현재 언어를 감지
- 언어별 번역 사전을 분리 관리
- 폴백(fallback) 언어 지원
- 확장 가능한 번역 키 시스템

이를 Antigravity-K에 적용:
- 에이전트 시스템 메시지의 다국어 지원
- 도구 설명/에러 메시지의 자동 번역
- 사용자 언어 자동 감지 및 전환
"""

import logging
import locale
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


# ─────────────────── 번역 사전 ───────────────────

_TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "ko": {
        "agent.greeting": "안녕하세요! {agent_name} 에이전트입니다. 무엇을 도와드릴까요?",
        "agent.task_complete": "작업이 완료되었습니다.",
        "agent.task_failed": "작업 중 오류가 발생했습니다: {error}",
        "agent.thinking": "생각 중입니다...",
        "agent.delegating": "{target_agent}에게 작업을 위임합니다.",
        "tool.execution_start": "도구 '{tool_name}' 실행 중...",
        "tool.execution_success": "도구 '{tool_name}' 실행 완료.",
        "tool.execution_error": "도구 '{tool_name}' 실행 오류: {error}",
        "tool.hitl_required": "[승인 필요] 에이전트가 다음 작업을 실행하려 합니다: {action}",
        "tool.hitl_approved": "사용자가 승인했습니다.",
        "tool.hitl_denied": "사용자가 거부했습니다.",
        "security.scan_passed": "보안 검사 통과.",
        "security.scan_failed": "보안 위험이 감지되었습니다: {details}",
        "skill.loaded": "스킬 '{skill_name}' 로드 완료 (도구: {tools})",
        "skill.not_found": "스킬 '{skill_name}'을(를) 찾을 수 없습니다.",
        "registry.summary": "등록된 도구: {count}개",
    },
    "en": {
        "agent.greeting": "Hello! I'm the {agent_name} agent. How can I help you?",
        "agent.task_complete": "Task completed successfully.",
        "agent.task_failed": "An error occurred during the task: {error}",
        "agent.thinking": "Thinking...",
        "agent.delegating": "Delegating task to {target_agent}.",
        "tool.execution_start": "Executing tool '{tool_name}'...",
        "tool.execution_success": "Tool '{tool_name}' executed successfully.",
        "tool.execution_error": "Tool '{tool_name}' execution error: {error}",
        "tool.hitl_required": "[Approval Required] Agent wants to execute: {action}",
        "tool.hitl_approved": "User approved.",
        "tool.hitl_denied": "User denied.",
        "security.scan_passed": "Security scan passed.",
        "security.scan_failed": "Security risk detected: {details}",
        "skill.loaded": "Skill '{skill_name}' loaded (tools: {tools})",
        "skill.not_found": "Skill '{skill_name}' not found.",
        "registry.summary": "Registered tools: {count}",
    },
    "ja": {
        "agent.greeting": "こんにちは！{agent_name}エージェントです。何かお手伝いしましょうか？",
        "agent.task_complete": "タスクが完了しました。",
        "agent.task_failed": "タスク中にエラーが発生しました: {error}",
        "agent.thinking": "考え中です...",
        "agent.delegating": "{target_agent}にタスクを委任します。",
        "tool.execution_start": "ツール '{tool_name}' を実行中...",
        "tool.execution_success": "ツール '{tool_name}' の実行が完了しました。",
        "tool.execution_error": "ツール '{tool_name}' 実行エラー: {error}",
        "tool.hitl_required": "[承認が必要] エージェントが次の操作を実行しようとしています: {action}",
        "tool.hitl_approved": "ユーザーが承認しました。",
        "tool.hitl_denied": "ユーザーが拒否しました。",
        "security.scan_passed": "セキュリティスキャンに合格しました。",
        "security.scan_failed": "セキュリティリスクが検出されました: {details}",
        "skill.loaded": "スキル '{skill_name}' ロード完了 (ツール: {tools})",
        "skill.not_found": "スキル '{skill_name}' が見つかりません。",
        "registry.summary": "登録済みツール: {count}個",
    },
}

# 기본 폴백 언어
_DEFAULT_LOCALE = "ko"
_FALLBACK_LOCALE = "en"


class I18n:
    """
    에이전트 시스템의 다국어 관리자.
    
    tiptap-vuetify가 Vuetify.lang.current를 자동 감지하듯,
    OS 로케일에서 언어를 자동 감지하거나 명시적으로 설정할 수 있습니다.
    
    사용 예:
        i18n = I18n()                          # 자동 감지
        i18n = I18n(locale="en")               # 명시 지정
        msg = i18n.t("agent.greeting", agent_name="PM")
    """
    
    def __init__(self, locale_code: Optional[str] = None):
        if locale_code:
            if locale_code in _TRANSLATIONS:
                self._locale = locale_code
            else:
                logger.warning(
                    f"Locale '{locale_code}' not supported. "
                    f"Using fallback: {_FALLBACK_LOCALE}"
                )
                self._locale = _FALLBACK_LOCALE
        else:
            self._locale = self._detect_locale()
        
        logger.info(f"I18n initialized with locale: {self._locale}")
    
    @property
    def locale(self) -> str:
        return self._locale
    
    @locale.setter
    def locale(self, value: str):
        if value not in _TRANSLATIONS:
            logger.warning(
                f"Locale '{value}' not supported. "
                f"Available: {list(_TRANSLATIONS.keys())}. "
                f"Using fallback: {_FALLBACK_LOCALE}"
            )
            self._locale = _FALLBACK_LOCALE
        else:
            self._locale = value
            logger.info(f"Locale changed to: {value}")
    
    def t(self, key: str, **kwargs) -> str:
        """
        번역 키에 대응하는 메시지를 반환합니다.
        
        tiptap-vuetify의 i18n 맵핑과 동일한 패턴:
        키 → 현재 언어 사전에서 조회 → 없으면 폴백 → 없으면 키 자체 반환
        
        Args:
            key: 번역 키 (예: "agent.greeting")
            **kwargs: 문자열 포맷 파라미터
        
        Returns:
            번역된 문자열
        """
        # 1차: 현재 로케일에서 검색
        message = _TRANSLATIONS.get(self._locale, {}).get(key)
        
        # 2차: 폴백 로케일에서 검색
        if message is None and self._locale != _FALLBACK_LOCALE:
            message = _TRANSLATIONS.get(_FALLBACK_LOCALE, {}).get(key)
        
        # 3차: 키 자체를 반환
        if message is None:
            logger.debug(f"Translation not found for key: '{key}' (locale={self._locale})")
            return key
        
        # 포맷 파라미터 적용
        try:
            return message.format(**kwargs)
        except (KeyError, IndexError):
            return message
    
    def add_translations(self, locale_code: str, translations: Dict[str, str]):
        """
        동적으로 번역을 추가합니다.
        
        tiptap-vuetify의 커스텀 아이콘 팩 확장과 유사하게,
        사용자가 커스텀 번역을 추가/오버라이드할 수 있습니다.
        """
        if locale_code not in _TRANSLATIONS:
            _TRANSLATIONS[locale_code] = {}
        _TRANSLATIONS[locale_code].update(translations)
        logger.info(
            f"Added {len(translations)} translations for locale '{locale_code}'"
        )
    
    def available_locales(self) -> list:
        """사용 가능한 언어 목록."""
        return list(_TRANSLATIONS.keys())
    
    def _detect_locale(self) -> str:
        """
        OS 로케일에서 언어를 자동 감지합니다.
        tiptap-vuetify가 Vuetify.lang.current를 읽는 것과 동일한 원리.
        """
        try:
            os_locale = locale.getlocale()[0]  # 예: "ko_KR" 또는 "Korean_Korea"
            if os_locale:
                lang = os_locale.split("_")[0].lower()  # "ko"
                if lang in _TRANSLATIONS:
                    return lang
        except Exception:
            pass
        
        return _DEFAULT_LOCALE
    
    def summary(self) -> Dict[str, Any]:
        """현재 i18n 상태 요약."""
        return {
            "current_locale": self._locale,
            "available_locales": self.available_locales(),
            "total_keys": {
                loc: len(trans) 
                for loc, trans in _TRANSLATIONS.items()
            },
        }


# ─────────────────── 글로벌 인스턴스 ───────────────────
# tiptap-vuetify처럼 import 즉시 사용 가능한 싱글턴

_global_i18n: Optional[I18n] = None


def get_i18n() -> I18n:
    """글로벌 I18n 인스턴스를 반환합니다. 없으면 자동 생성."""
    global _global_i18n
    if _global_i18n is None:
        _global_i18n = I18n()
    return _global_i18n


def set_locale(locale_code: str):
    """글로벌 로케일을 변경합니다."""
    get_i18n().locale = locale_code


def t(key: str, **kwargs) -> str:
    """글로벌 번역 함수 — 어디서든 바로 호출 가능."""
    return get_i18n().t(key, **kwargs)
