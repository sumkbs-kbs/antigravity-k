"""
ContextShaper — 5단계 컨텍스트 압축 파이프라인
================================================
Claw Code의 Context Compaction Shapers 아키텍처 이식.

긴 코딩 세션에서 토큰 예산을 지키면서 핵심 컨텍스트를 유지하는 엔진.

5단계 파이프라인:
1. BudgetReducer — 남은 토큰 예산 기반 허용량 계산
2. Snip         — 오래된 메시지 우선순위 기반 절삭
3. MicroCompact — 최근 대화 턴의 경량 요약
4. ContextCollapse — 긴 도구 출력을 참조 ID로 교체
5. AutoCompact  — LLM을 활용한 전체 세션 요약
"""
import hashlib
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ContextShaper:
    """
    5단계 컨텍스트 압축 파이프라인.
    
    Claw Code의 Shaper 체인 패턴:
    messages → BudgetReducer → Snip → MicroCompact → ContextCollapse → AutoCompact → shaped
    """
    
    # 메시지 역할별 우선순위 (낮을수록 절삭 대상)
    ROLE_PRIORITY = {
        "system": 10,    # 절대 삭제 안 됨
        "user": 7,       # 높은 보존
        "assistant": 5,  # 중간
        "tool": 3,       # 낮음 (긴 출력 → 참조 ID)
    }
    
    def __init__(
        self,
        max_tokens: int = 128_000,
        reserve_tokens: int = 4_096,   # 응답 예약
        collapse_threshold: int = 2000, # 이 길이 초과 도구 출력 → collapse
        storage_dir: Optional[str] = None,
    ):
        self.max_tokens = max_tokens
        self.reserve_tokens = reserve_tokens
        self.collapse_threshold = collapse_threshold
        self.storage_dir = storage_dir or os.path.join(
            os.path.expanduser("~"), ".antigravity", "context_store"
        )
        os.makedirs(self.storage_dir, exist_ok=True)
        
        # 압축 통계
        self._stats = {
            "total_shaped": 0,
            "tokens_saved": 0,
            "collapses": 0,
            "snips": 0,
        }
    
    def shape(
        self,
        messages: List[Dict[str, str]],
        budget: Optional[int] = None,
        force_compact: bool = False,
    ) -> List[Dict[str, str]]:
        """
        메시지 리스트에 5단계 압축 파이프라인을 적용합니다.
        
        Args:
            messages: [{"role": "...", "content": "..."}] 리스트
            budget: 사용 가능한 최대 토큰 (None이면 self.max_tokens)
            force_compact: True이면 예산 이내라도 강제 압축 수행
                          (API 에러 분류기의 context_overflow 감지 시 사용)
        
        Returns:
            압축된 메시지 리스트
        """
        budget = budget or (self.max_tokens - self.reserve_tokens)
        original_size = self._estimate_tokens(messages)
        
        if not force_compact and original_size <= budget:
            return messages  # 예산 내 → 그대로 반환
        
        # force_compact 시 더 공격적인 예산 설정
        if force_compact:
            budget = int(budget * 0.6)  # 60% 수준으로 강제 축소
        
        shaped = list(messages)
        
        # Stage 1: Budget Reducer — 허용량 계산
        target = self._budget_reduce(original_size, budget)
        
        # Stage 2: Snip — 오래된 저우선 메시지 절삭
        shaped = self._snip(shaped, target)
        
        # Stage 3: MicroCompact — 연속 도구 결과 압축
        shaped = self._micro_compact(shaped)
        
        # Stage 4: ContextCollapse — 긴 출력 → 참조 ID
        shaped = self._context_collapse(shaped)
        
        # Stage 5: AutoCompact — 여전히 초과 시 요약 주입
        current_size = self._estimate_tokens(shaped)
        if current_size > budget:
            shaped = self._auto_compact(shaped, budget)
        
        self._stats["total_shaped"] += 1
        self._stats["tokens_saved"] += original_size - self._estimate_tokens(shaped)
        
        logger.info(
            f"Context shaped: {original_size} → {self._estimate_tokens(shaped)} tokens "
            f"(saved {original_size - self._estimate_tokens(shaped)})"
        )
        
        return shaped
    
    # ─────────── Stage 1: Budget Reducer ───────────
    
    def _budget_reduce(self, current: int, budget: int) -> int:
        """목표 토큰 수를 계산합니다."""
        overshoot = current - budget
        # 80% 수준으로 타겟 설정 (여유 확보)
        target = int(budget * 0.8)
        logger.debug(f"BudgetReducer: current={current}, budget={budget}, target={target}")
        return target
    
    # ─────────── Stage 2: Snip ───────────
    
    def _snip(self, messages: List[Dict], target: int) -> List[Dict]:
        """
        오래된 저우선 메시지를 절삭합니다.
        시스템 메시지와 최근 5턴은 보존.
        """
        if self._estimate_tokens(messages) <= target:
            return messages
        
        # 시스템 메시지 보존
        system_msgs = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]
        
        # 최근 5턴(10메시지) 보존
        preserve_count = min(10, len(non_system))
        preserved = non_system[-preserve_count:]
        candidates = non_system[:-preserve_count]
        
        # 우선순위 낮은 순서로 제거
        candidates.sort(
            key=lambda m: self.ROLE_PRIORITY.get(m.get("role", ""), 0)
        )
        
        result = system_msgs + candidates + preserved
        
        while self._estimate_tokens(result) > target and candidates:
            removed = candidates.pop(0)
            result = system_msgs + candidates + preserved
            self._stats["snips"] += 1
        
        return result
    
    # ─────────── Stage 3: MicroCompact ───────────
    
    def _micro_compact(self, messages: List[Dict]) -> List[Dict]:
        """
        연속 도구 결과를 합치고, 긴 내용을 축약합니다.
        Claw Code의 'consecutive tool results merge' 패턴.
        """
        if len(messages) < 3:
            return messages
        
        result = []
        tool_buffer = []
        
        for msg in messages:
            if msg.get("role") == "tool":
                tool_buffer.append(msg)
            else:
                if tool_buffer:
                    # 연속 도구 결과 → 하나로 합침
                    if len(tool_buffer) > 1:
                        merged_content = "\n---\n".join(
                            f"[{t.get('name', 'tool')}] {self._truncate(t.get('content', ''), 500)}"
                            for t in tool_buffer
                        )
                        result.append({
                            "role": "tool",
                            "content": merged_content,
                            "name": "merged_tools"
                        })
                    else:
                        # 단일 도구 결과도 축약
                        t = tool_buffer[0]
                        t["content"] = self._truncate(t.get("content", ""), 1000)
                        result.append(t)
                    tool_buffer = []
                result.append(msg)
        
        # 잔여 버퍼 처리
        if tool_buffer:
            if len(tool_buffer) > 1:
                merged = "\n---\n".join(
                    f"[{t.get('name', 'tool')}] {self._truncate(t.get('content', ''), 500)}"
                    for t in tool_buffer
                )
                result.append({"role": "tool", "content": merged, "name": "merged_tools"})
            else:
                tool_buffer[0]["content"] = self._truncate(tool_buffer[0].get("content", ""), 1000)
                result.append(tool_buffer[0])
        
        return result
    
    # ─────────── Stage 4: Context Collapse ───────────
    
    def _context_collapse(self, messages: List[Dict]) -> List[Dict]:
        """
        긴 도구 출력(파일 내용, grep 결과)을 참조 ID로 교체하고 디스크에 저장.
        Claw Code의 'reference ID replacement' 패턴.
        """
        result = []
        for msg in messages:
            content = msg.get("content", "")
            
            if msg.get("role") == "tool" and len(content) > self.collapse_threshold:
                # 참조 ID 생성 (P0 보안 일관성: MD5 → SHA256)
                ref_id = hashlib.sha256(content.encode()).hexdigest()[:12]
                
                # 디스크 저장
                ref_path = os.path.join(self.storage_dir, f"{ref_id}.json")
                with open(ref_path, "w", encoding="utf-8") as f:
                    json.dump({"content": content, "ts": time.time()}, f)
                
                # 축약 버전 (첫 200자 + 참조 ID)
                preview = content[:200]
                collapsed = (
                    f"{preview}...\n"
                    f"[Full output stored as ref:{ref_id}, {len(content)} chars]"
                )
                
                result.append({**msg, "content": collapsed})
                self._stats["collapses"] += 1
            else:
                result.append(msg)
        
        return result
    
    def restore_collapsed(self, ref_id: str) -> Optional[str]:
        """참조 ID로 저장된 전체 내용을 복원합니다."""
        ref_path = os.path.join(self.storage_dir, f"{ref_id}.json")
        if os.path.exists(ref_path):
            with open(ref_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("content")
        return None
    
    # ─────────── Stage 5: Auto Compact ───────────
    
    def _auto_compact(
        self, messages: List[Dict], budget: int
    ) -> List[Dict]:
        """
        여전히 예산 초과 시, 이전 대화를 요약문으로 교체합니다.
        Claw Code의 'auto-compact with LLM summary' 패턴.
        
        Note: LLM 호출 없이 규칙 기반 요약으로 구현 (로컬 LLM 호출은 추후).
        """
        system_msgs = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]
        
        # 최근 3턴(6메시지) 보존
        preserve = min(6, len(non_system))
        old = non_system[:-preserve] if preserve else non_system
        recent = non_system[-preserve:] if preserve else []
        
        if not old:
            return messages
        
        # 규칙 기반 요약 생성
        summary_parts = []
        for msg in old:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if role == "user":
                summary_parts.append(f"- User asked: {self._truncate(content, 100)}")
            elif role == "assistant":
                summary_parts.append(f"- Assistant: {self._truncate(content, 100)}")
            elif role == "tool":
                name = msg.get("name", "tool")
                summary_parts.append(f"- Tool '{name}' executed")
        
        summary = (
            "[Previous conversation summary]\n"
            + "\n".join(summary_parts[:20])  # 최대 20개 항목
        )
        
        summary_msg = {"role": "system", "content": summary}
        
        return system_msgs + [summary_msg] + recent
    
    # ─────────── 유틸리티 ───────────
    
    @staticmethod
    def _estimate_tokens(messages: List[Dict]) -> int:
        """
        메시지 리스트의 대략적인 토큰 수를 추정합니다.
        한국어/CJK 문자는 보통 1자에 2-3 토큰이므로 UTF-8 바이트 기반으로 계산합니다.
        (UTF-8 바이트 수 / 3 ≈ 토큰 수)
        """
        total_bytes = sum(len(m.get("content", "").encode("utf-8")) for m in messages)
        return total_bytes // 3
    
    @staticmethod
    def _truncate(text: str, max_len: int) -> str:
        """텍스트를 max_len 길이로 잘라냅니다."""
        if len(text) <= max_len:
            return text
        return text[:max_len] + f"... ({len(text)} total chars)"
    
    def get_stats(self) -> Dict[str, int]:
        """압축 통계를 반환합니다."""
        return dict(self._stats)
    
    def get_token_usage(self, messages: List[Dict]) -> Dict[str, Any]:
        """현재 컨텍스트 토큰 사용량을 분석합니다."""
        total = self._estimate_tokens(messages)
        by_role = {}
        for msg in messages:
            role = msg.get("role", "unknown")
            tokens = len(msg.get("content", "").encode("utf-8")) // 3
            by_role[role] = by_role.get(role, 0) + tokens
        
        return {
            "total_tokens": total,
            "max_tokens": self.max_tokens,
            "usage_pct": round(total / self.max_tokens * 100, 1),
            "by_role": by_role,
            "budget_remaining": self.max_tokens - self.reserve_tokens - total,
        }
