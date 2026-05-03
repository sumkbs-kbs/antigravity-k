"""
Antigravity-K: 자율 학습 파이프라인 (Autonomous Learner)
=======================================================
사용자 명령 수행 시 에이전트가 자동으로 지식 갭을 감지하고,
웹 검색/스크래핑을 통해 학습하여 Vault(KI)에 영속적으로 저장합니다.

워크플로우:
  1. should_learn(task) → 학습 필요 여부 판단
  2. analyze_knowledge_gap(task) → 필요한 지식 목록 추출
  3. auto_learn(gaps) → 웹 검색 → 스크래핑 → 요약 → KI 저장
"""
import json
import logging
import re
import hashlib
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger(__name__)


# ─── 데이터 모델 ─────────────────────────────────────────────────

@dataclass
class KnowledgeGap:
    """에이전트가 모르는 지식 항목."""
    topic: str
    reason: str  # 왜 이 지식이 필요한지
    search_queries: List[str] = field(default_factory=list)  # 검색 쿼리 후보


@dataclass
class LearnedKnowledge:
    """학습 완료된 지식."""
    topic: str
    summary: str
    sources: List[str] = field(default_factory=list)
    learned_at: str = ""
    ki_id: str = ""


# ─── 학습 필요 여부 판단 ─────────────────────────────────────────

# 학습이 필요할 가능성이 높은 키워드 패턴
_LEARN_TRIGGERS_KO = [
    "최신", "새로운", "업데이트", "방법", "어떻게", "설치",
    "라이브러리", "프레임워크", "패키지", "API", "문서",
    "트렌드", "비교", "추천", "2025", "2026",
]
_LEARN_TRIGGERS_EN = [
    "latest", "new", "update", "how to", "install",
    "library", "framework", "package", "tutorial",
    "documentation", "best practice", "compare",
]


class AutonomousLearner:
    """
    자율 학습 엔진.
    
    CEO 분석 후, 에이전트가 태스크를 실행하기 전에 호출되어
    필요한 지식을 자동으로 웹에서 수집하고 Vault에 저장합니다.
    """

    def __init__(self, model_manager=None, ki_engine=None, project_root: str = "."):
        self.manager = model_manager
        self.ki_engine = ki_engine
        self.project_root = project_root
        self._max_gaps = 3  # 한 번에 최대 3개 지식 갭만 처리
        self._max_sources_per_gap = 3

    def should_learn(self, task_description: str) -> bool:
        """태스크 수행에 새로운 외부 지식이 필요한지 빠르게 판단합니다."""
        lower = task_description.lower()
        
        # 키워드 기반 빠른 감지
        all_triggers = _LEARN_TRIGGERS_KO + _LEARN_TRIGGERS_EN
        matches = sum(1 for kw in all_triggers if kw in lower)
        
        # 2개 이상 트리거 매칭 시 학습 필요
        if matches >= 2:
            logger.info(f"[AutoLearn] Triggered by keywords ({matches} matches)")
            return True
        
        # URL이나 패키지 이름이 포함된 경우
        if re.search(r'https?://|pip install|npm install|brew install', lower):
            return True
        
        # 물음표가 있으면 정보 탐색 의도
        if '?' in task_description or '어떻게' in lower or 'how' in lower:
            if matches >= 1:
                return True
        
        return False

    def analyze_knowledge_gap(self, task_description: str) -> List[KnowledgeGap]:
        """
        LLM을 사용하여 태스크에 필요한 지식 갭을 분석합니다.
        LLM이 없으면 키워드 기반 폴백으로 검색 쿼리를 생성합니다.
        """
        # LLM 기반 분석 시도
        if self.manager:
            try:
                return self._analyze_with_llm(task_description)
            except Exception as e:
                logger.warning(f"[AutoLearn] LLM analysis failed, falling back: {e}")
        
        # 키워드 기반 폴백
        return self._analyze_with_keywords(task_description)

    def _analyze_with_llm(self, task_description: str) -> List[KnowledgeGap]:
        """LLM에게 지식 갭 분석을 요청합니다."""
        prompt = (
            "You are a knowledge gap analyzer. Given the following user task, "
            "identify what specific knowledge or information would be needed from the internet "
            "to complete it successfully.\n\n"
            f"Task: {task_description}\n\n"
            "Return a JSON array of objects with fields:\n"
            "- topic: what knowledge is needed\n"
            "- reason: why it's needed\n"
            "- search_queries: list of 2-3 web search queries to find this info\n\n"
            "Return ONLY the JSON array, no markdown or explanation.\n"
            "If no external knowledge is needed, return an empty array []."
        )

        try:
            # Ollama API 직접 호출 (비스트리밍)
            default_model = "qwen3.6:latest"
            data = {
                "model": default_model,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": 512, "temperature": 0.3}
            }
            req = urllib.request.Request(
                "http://localhost:11434/api/generate",
                data=json.dumps(data).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                response_text = result.get("response", "")

            # JSON 추출
            # <think> 태그 제거
            clean = re.sub(r'<think>.*?</think>', '', response_text, flags=re.DOTALL)
            
            # JSON 배열 추출
            match = re.search(r'\[.*\]', clean, re.DOTALL)
            if match:
                gaps_data = json.loads(match.group())
                gaps = []
                for item in gaps_data[:self._max_gaps]:
                    gaps.append(KnowledgeGap(
                        topic=item.get("topic", ""),
                        reason=item.get("reason", ""),
                        search_queries=item.get("search_queries", [])[:3],
                    ))
                return gaps

        except Exception as e:
            logger.warning(f"[AutoLearn] LLM gap analysis error: {e}")

        return self._analyze_with_keywords(task_description)

    def _analyze_with_keywords(self, task_description: str) -> List[KnowledgeGap]:
        """키워드 기반 폴백 — LLM 없이 검색 쿼리를 생성합니다."""
        gaps = []
        
        # 핵심 명사구 추출 (간단한 휴리스틱)
        # 따옴표 안의 내용, 영문 고유명사, 기술 용어 추출
        quoted = re.findall(r'["\']([^"\']+)["\']', task_description)
        tech_terms = re.findall(r'\b[A-Z][a-zA-Z]+(?:\.[a-zA-Z]+)*\b', task_description)
        
        # 쿼리 후보 생성
        if quoted:
            for q in quoted[:2]:
                gaps.append(KnowledgeGap(
                    topic=q,
                    reason="사용자가 명시적으로 언급한 주제",
                    search_queries=[q, f"{q} tutorial", f"{q} 사용법"]
                ))
        
        if tech_terms:
            combined = " ".join(tech_terms[:3])
            gaps.append(KnowledgeGap(
                topic=combined,
                reason="기술 용어 감지",
                search_queries=[combined, f"{combined} documentation"]
            ))
        
        # 기본 폴백
        if not gaps:
            gaps.append(KnowledgeGap(
                topic=task_description[:100],
                reason="일반 태스크 학습",
                search_queries=[task_description[:80]]
            ))
        
        return gaps[:self._max_gaps]

    def auto_learn(self, gaps: List[KnowledgeGap]) -> List[LearnedKnowledge]:
        """
        지식 갭에 대해 웹 검색 + 스크래핑 + 요약을 수행하고 KI에 저장합니다.
        """
        from antigravity_k.tools.web_search import WebSearchTool
        
        search_tool = WebSearchTool()
        learned = []

        for gap in gaps:
            try:
                all_results = []
                for query in gap.search_queries[:2]:
                    result_text = search_tool.execute(query=query)
                    if result_text and "결과 없음" not in result_text:
                        all_results.append(result_text)

                if not all_results:
                    logger.info(f"[AutoLearn] No results for: {gap.topic}")
                    continue

                # 검색 결과 합산
                combined = "\n\n".join(all_results)

                # LLM 요약 (가능한 경우)
                summary = self._summarize_results(gap.topic, combined)
                
                # KI에 저장
                ki_id = self._save_to_ki(gap.topic, summary, gap.search_queries)
                
                learned.append(LearnedKnowledge(
                    topic=gap.topic,
                    summary=summary,
                    sources=gap.search_queries,
                    learned_at=datetime.now().isoformat(),
                    ki_id=ki_id,
                ))
                
                logger.info(f"[AutoLearn] Learned: {gap.topic} ({len(summary)} chars)")
                
            except Exception as e:
                logger.error(f"[AutoLearn] Failed to learn about '{gap.topic}': {e}")

        return learned

    def _summarize_results(self, topic: str, search_results: str) -> str:
        """검색 결과를 LLM으로 요약합니다. LLM 없으면 원문 반환."""
        if not self.manager:
            # LLM 없으면 원문 잘라서 반환
            return search_results[:2000]

        try:
            prompt = (
                f"Summarize the following web search results about '{topic}' "
                f"into a concise, actionable knowledge note (max 500 words).\n\n"
                f"Search Results:\n{search_results[:4000]}\n\n"
                f"Write a clear, structured summary in the language that matches the topic."
            )
            data = {
                "model": "qwen3.6:latest",
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": 800, "temperature": 0.3}
            }
            req = urllib.request.Request(
                "http://localhost:11434/api/generate",
                data=json.dumps(data).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                summary = result.get("response", "")
                # <think> 태그 제거
                summary = re.sub(r'<think>.*?</think>', '', summary, flags=re.DOTALL).strip()
                return summary if summary else search_results[:2000]
        except Exception as e:
            logger.warning(f"[AutoLearn] Summarization failed: {e}")
            return search_results[:2000]

    def _save_to_ki(self, topic: str, summary: str, sources: List[str]) -> str:
        """학습된 지식을 KIEngine에 저장합니다."""
        ki_id = f"autolearn_{hashlib.sha256(topic.encode()).hexdigest()[:12]}"
        
        if self.ki_engine:
            self.ki_engine.save_ki(ki_id, {
                "title": f"[AutoLearn] {topic}",
                "summary": summary,
                "sources": sources,
                "learned_at": datetime.now().isoformat(),
                "type": "auto_learned",
                "artifacts": [],
            })
        
        return ki_id

    def format_context(self, learned: List[LearnedKnowledge]) -> str:
        """학습된 지식을 LLM 컨텍스트 주입용 텍스트로 포맷합니다."""
        if not learned:
            return ""
        
        lines = ["\n<auto_learned_context>"]
        lines.append("# 자동 학습된 최신 정보 (웹 검색 기반)")
        lines.append("")
        
        for item in learned:
            lines.append(f"## {item.topic}")
            lines.append(f"*학습 시각: {item.learned_at}*")
            lines.append(f"*출처: {', '.join(item.sources[:3])}*")
            lines.append("")
            lines.append(item.summary[:1500])
            lines.append("")
        
        lines.append("</auto_learned_context>")
        return "\n".join(lines)
