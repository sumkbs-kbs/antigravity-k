"""Antigravity-K: 프롬프트 빌더 (PromptBuilder).

=============================================
역할별 시스템 프롬프트, 도구 가이드, 페르소나 스타일링을
코드에서 분리하여 `prompts/` 디렉토리의 마크다운 파일로 관리합니다.

설계 원칙 (Claude 패턴):
  - 프롬프트 엔지니어가 Python 코드를 몰라도 프롬프트를 튜닝할 수 있어야 합니다.
  - 모든 프롬프트는 YAML 프론트매터 + 마크다운 본문 형식입니다.
  - 파일 로드 시 캐싱하여 매 요청마다 디스크 I/O를 방지합니다.

디렉토리 구조:
  prompts/
  ├── roles/
  │   ├── ceo.md
  │   ├── worker.md
  │   ├── eng_manager.md
  │   ├── default.md
  │   └── ...
  └── persona.md
"""

import datetime
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


class PromptBuilder:
    """프롬프트 파일 로더 및 조합기.

    사용법:
        builder = PromptBuilder()
        system_prompt = builder.role_prompt("WORKER")
        tool_guide = builder.tool_guide(tool_schemas)
    """

    # prompts/ 디렉토리를 찾기 위한 기본 경로
    _DEFAULT_PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "prompts")

    def __init__(self, prompts_dir: str | None = None):
        """Initialize the PromptBuilder.

        Args:
            prompts_dir (str | None): str | None prompts dir.

        """
        self._dir = os.path.abspath(prompts_dir or self._DEFAULT_PROMPTS_DIR)
        self._cache: dict[str, str] = {}

        if not os.path.isdir(self._dir):
            logger.warning("Prompts directory not found: %s. Using inline fallbacks.", self._dir)

    def _load(self, relative_path: str) -> str | None:
        """프롬프트 파일을 로드합니다 (캐시 적용)."""
        if relative_path in self._cache:
            return self._cache[relative_path]

        full_path = os.path.join(self._dir, relative_path)
        if not os.path.exists(full_path):
            return None

        try:
            with open(full_path, encoding="utf-8") as f:
                content = f.read()

            # YAML 프론트매터 제거 (--- ... --- 블록)
            if content.startswith("---"):
                end_idx = content.find("---", 3)
                if end_idx != -1:
                    content = content[end_idx + 3 :].strip()

            self._cache[relative_path] = content
            return content
        except Exception:
            logger.exception("Failed to load prompt file %s", full_path)
            return None

    def role_prompt(self, role: str) -> str:
        """역할별 시스템 프롬프트를 로드합니다.

        Args:
            role: "WORKER", "CEO", "ENG_MANAGER", "DEFAULT" 등

        Returns:
            프롬프트 텍스트. 파일이 없으면 inline fallback 반환.

        """
        filename = f"roles/{role.lower()}.md"
        content = self._load(filename)

        if content is None:
            # fallback: 파일이 없으면 기본 프롬프트
            logger.debug("No prompt file for role '%s', using DEFAULT", role)
            content = self._load("roles/default.md")

        return content or f"You are a helpful AI assistant acting as {role}. Always respond in Korean."

    def persona_prompt(self) -> str:
        """페르소나 스타일링 CORE DIRECTIVE를 로드합니다."""
        content = self._load("persona.md")
        if content is None:
            return ""
        return f"\n\n[CORE DIRECTIVE: ANTIGRAVITY PERSONA & RESPONSE STYLING]\n{content}"

    def tool_guide(
        self,
        tool_schemas: list[dict[str, Any]],
        current_time: datetime.datetime | None = None,
    ) -> str:
        """도구 사용 가이드 프롬프트를 생성합니다.

        Args:
            tool_schemas: ToolRegistry.to_llm_schemas() 결과
            current_time: 현재 시간 (None이면 자동)

        """
        now = current_time or datetime.datetime.now()
        now_str = now.strftime("%Y년 %m월 %d일 %H시 %M분")

        tool_section = (
            "## 🛠️ 도구(Tool) 사용 가이드\n"
            f"**현재 시스템 시간**: {now_str}\n\n"
            "당신은 외부 환경과 상호작용할 수 있는 도구들을 가지고 있습니다.\n"
            "웹 검색, 파일 읽기, 시스템 제어 등의 액션이 필요하다면 **반드시 도구를 호출**해야 합니다.\n"
            "도구를 호출하려면, 아래와 같이 `<action_call>` 태그 안에 JSON 형식으로 작성하세요.\n\n"
            "<action_call>\n"
            '{"name": "사용할_도구_이름", "arguments": {"인자1": "값1"}}\n'
            "</action_call>\n\n"
            "### ⚠️ 중요 규칙:\n"
            "1. 계획이나 행동을 말로만 설명하지 말고, **즉시 <action_call>을 출력**하세요.\n"
            "2. (예: '웹 검색을 통해 확인하겠습니다'라고 말하는 대신, 바로 `<action_call>`을 출력하세요)\n"
            "3. 하나의 메시지에는 **단 1개의 <action_call>**만 포함해야 합니다.\n"
            "4. <action_call>을 출력했다면, 다른 부연 설명을 덧붙이지 말고 즉시 응답 생성을 중단하세요.\n"
            "5. 사용자에게 전달하는 최종 답변은 **반드시 한국어**로 작성하세요.\n"
            "6. **절대 `Query: ...` 나 `Action: ...` 같은 평문 형식으로 도구를 호출하지 마세요.** "
            "반드시 `<action_call>` XML 태그와 JSON 객체 포맷을 정확히 지켜야 합니다.\n"
            "7. **절대 도구 이름을 XML 태그로 사용하지 마세요. (예: <create_directory> 태그 금지).** "
            "오직 `<action_call>` 태그만 사용해야 합니다.\n"
            "8. **시간 인지 검색 (CRITICAL)**: 사용자가 '내일', '오늘', '어제' 날씨나 뉴스를 물어보면, "
            "반드시 현재 시스템 시간을 기준으로 **정확한 날짜(예: 2026년 5월 5일)**를 계산하여 "
            "검색어에 포함하세요. 절대 상대적인 단어('내일')로만 검색하지 마세요.\n"
            "9. **`<thought>` 블록 안에서 `<action_call>` 태그를 절대 사용하거나 언급하지 마세요.** "
            "`<action_call>`은 오직 `<thought>` 블록 바깥에서만 사용해야 합니다.\n"
            "10. **[CRITICAL] 사용자가 파일 생성, 수정, 또는 명령 실행을 요구하면 절대 코드만 텍스트로 보여주지 마세요.** "  # noqa: E501
            "당신은 스스로 컴퓨터와 상호작용할 수 있습니다. `write_file`, `run_bash_command` 등의 도구를 직접 호출하여 "
            "**반드시 물리적으로 파일을 생성하고 명령을 실행**해야 합니다.\n"
            "11. **[CRITICAL] 사용자의 명시적인 요구가 없다면, 도구를 실행하기 전에 허락이나 동의를 구하지 마세요.** "
            "스스로 판단하여 도구를 즉시 실행하고, 그 결과를 정리해서 사용자에게 보고하세요. "
            "안전한 파일 생성이나 폴더 생성 작업은 질문 없이 바로 실행해야 합니다.\n\n"
            "### 📊 출력 품질 게이트 (Output Quality Gate):\n"
            "12. **코드 요청에도 반드시 한국어 설명을 포함하세요.** 코드 블록만 단독으로 응답하는 것은 품질 부족입니다. "  # noqa: E501
            "최소한 '왜 이 방법을 선택했는지'와 '동작 원리'를 한국어로 설명하세요.\n"
            "13. **[CRITICAL] 시간/공간 복잡도(Big-O)는 사용자가 알고리즘이나 성능에 대해 명시적으로 물어볼 때만 포함하세요.** "  # noqa: E501
            "단순한 폴더 생성, HTML 작성, API 연동 같은 작업에는 절대 Big-O를 설명하지 마세요.\n"
            "14. **코드 블록 전후로 선택 근거를 제시하세요.** '왜 이 알고리즘/패턴을 선택했는지' 1~2문장으로 설명하세요.\n"  # noqa: E501
            "15. **3개 이상의 방법 비교 요청 시 반드시 비교 표(마크다운 테이블)를 포함하세요.** "
            "| 방법 | 시간복잡도 | 공간복잡도 | 특징 | 형태의 표를 사용하세요.\n"
            "16. **한 응답에서 같은 문단을 2회 이상 반복하지 마세요.** 반복 감지 시 해당 문단을 제거하세요.\n"
            "17. **응답이 지나치게 짧으면(200자 미만) 품질 부족입니다.** 추가 설명, 예시, 팁을 보완하세요.\n\n"
            "18. **[CRITICAL] 자기소개/능력 설명은 실제 등록된 도구와 Skills만 근거로 작성하세요.** "
            "WiFi, 볼륨, 클립보드, OS 제어처럼 현재 도구 목록에 없는 기능을 가진 것처럼 말하지 마세요.\n"
            "19. **[CRITICAL] 최신/최근/실시간 동향 질문은 반드시 검색 도구로 확인하거나, 검색 도구가 없으면 그 한계를 명확히 말하세요.** "  # noqa: E501
            "지식 cutoff나 오래된 일반론만으로 최신 정보를 답하지 마세요.\n"
            "20. **[CRITICAL] 내부 추론을 사용자에게 노출하지 마세요.** "
            "`Thinking Process`, `<think>`, `<thought>`, 영어 혼잣말, 계획 독백은 최종 답변에 포함될 수 없습니다.\n"
            "21. **한국어 답변에는 일본어/중국어가 섞이지 않게 하고 자연스러운 띄어쓰기를 유지하세요.**\n\n"
            "### 📑 Artifacts 및 Planning Mode (Google Tolaria Architecture):\n"
            "22. **대규모 아키텍처 변경이나 복잡한 요구사항 시, 코드를 바로 짜지 말고 계획안을 먼저 작성하세요.**\n"
            "  - `write_file` 도구를 사용하여 `artifacts/implementation_plan.md` 파일을 생성하세요.\n"
            "  - 파일 작성 완료 후 사용자에게 승인을 요청하는 **`[APPROVAL REQUIRED]`** 문자열을 응답에 포함하여 멈추세요.\n"  # noqa: E501
            "23. **승인을 받으면 `artifacts/task.md`를 생성하고 할 일 목록을 기록 및 갱신하며 작업하세요.**\n"
            "24. **Artifact 작성 시 마크다운 요소를 적극 활용하세요.**\n"
            "  - GitHub 스타일 경고 (`> [!NOTE]`, `> [!WARNING]`, `> [!IMPORTANT]`)\n"
            "  - 변경 사항을 한눈에 볼 수 있는 `render_diffs(절대경로)` 표기법\n"
            "  - 복잡한 아키텍처나 워크플로우를 시각화하는 `mermaid` 다이어그램\n\n"
            "### 💡 도구 호출 예시 (Example):\n"
            "사용자: 거제 날씨 알려줘\n"
            "Assistant:\n"
            "<thought>\n"
            "날씨 정보를 알기 위해서는 웹 검색이 필요합니다. web_search 도구를 사용하겠습니다.\n"
            "</thought>\n"
            "<action_call>\n"
            '{"name": "web_search", "arguments": {"query": "거제 오늘 날씨"}}\n'
            "</action_call>\n\n"
            "### 사용 가능한 도구 목록:\n"
        )

        for schema in tool_schemas:
            params = schema.get("input_schema", {})
            required = params.get("required") or []
            tool_section += f"- **{schema['name']}**: {schema['description']}\n"
            props = params.get("properties") or {}
            if props:
                param_strs = []
                for k, v in props.items():
                    p_type = v.get("type", "any")
                    p_req = "required" if k in required else "optional"
                    param_strs.append(f"{k} ({p_type}, {p_req})")
                tool_section += f"  Parameters: {', '.join(param_strs)}\n"

        return tool_section

    # ─── 계층형 프롬프트 아키텍처 (Structured & Segmented Prompts) ───
    def structured_prompt(
        self,
        role: str,
        task: str,
        context: str = "",
        constraints: list[str] | None = None,
        output_format: str = "",
        few_shot: list[dict[str, str]] | None = None,
    ) -> str:
        """계층화된 섹션으로 구성된 프롬프트를 생성합니다.

        소형 모델은 구조가 명확할수록 지시 이행률이 높아집니다.
        연구 근거: FabWebStudio 2025, RecursiveAI 2025

        Args:
            role: 역할 (예: "금융 분석 전문가")
            task: 수행할 작업 설명
            context: RAG 등에서 가져온 참고 자료
            constraints: 지켜야 할 제약 조건 목록
            output_format: 출력 형식 지정
            few_shot: 입출력 예시 목록 [{"input": "...", "output": "..."}]

        Returns:
            섹션으로 구분된 구조화 프롬프트

        """
        sections = []

        # [ROLE] 역할 정의
        sections.append(f"[ROLE]\n당신은 {role}입니다.")

        # [CONSTRAINTS] 제약 조건
        if constraints:
            constraint_lines = "\n".join(f"- {c}" for c in constraints)
            sections.append(f"[CONSTRAINTS]\n{constraint_lines}")
        else:
            sections.append(
                "[CONSTRAINTS]\n"
                "- 반드시 한국어로 답변하세요.\n"
                "- 불필요한 서론과 사족을 생략하고 핵심만 전달하세요.\n"
                "- 확실하지 않은 정보는 명확히 '확인 불가'라고 표시하세요.",
            )

        # [CONTEXT] 참고 자료 (RAG 문서, 검색 결과 등)
        if context:
            sections.append(f"[CONTEXT]\n{context}")

        # [EXAMPLES] Few-Shot 예시
        if few_shot:
            examples = []
            for i, ex in enumerate(few_shot, 1):
                examples.append(f"예시 {i}:\n  입력: {ex['input']}\n  출력: {ex['output']}")
            sections.append("[EXAMPLES]\n" + "\n\n".join(examples))

        # [OUTPUT FORMAT] 출력 형식
        if output_format:
            sections.append(f"[OUTPUT FORMAT]\n{output_format}")

        # [TASK] 수행할 작업 — 항상 마지막 (쿼리 후치 배치 원칙)
        sections.append(f"[TASK]\n{task}")

        return "\n\n".join(sections)

    def get_task_few_shots(self, task_type: str) -> list[dict[str, str]]:
        """작업 유형별 기본 Few-Shot 예시를 반환합니다.

        Args:
            task_type: SEARCH, CODE, ANALYSIS, CREATIVE, GENERAL

        Returns:
            입출력 예시 목록

        """
        _EXAMPLES: dict[str, list[dict[str, str]]] = {
            "SEARCH": [
                {
                    "input": "삼성전자 오늘 종가 알려줘",
                    "output": (
                        "## 삼성전자 (005930) 오늘 종가\n\n"
                        "| 항목 | 값 |\n|---|---|\n"
                        "| 종가 | 82,400원 |\n| 전일 대비 | +1,200원 (+1.48%) |\n"
                        "| 거래량 | 15,234,567주 |\n\n"
                        "*출처: 네이버 금융 [1]*"
                    ),
                },
            ],
            "CODE": [
                {
                    "input": "Python으로 피보나치 함수 만들어줘",
                    "output": (
                        "**메모이제이션** 기법을 사용하여 중복 계산을 제거한 효율적인 구현입니다.\n\n"
                        "```python\nfrom functools import lru_cache\n\n"
                        "@lru_cache(maxsize=None)\ndef fibonacci(n: int) -> int:\n"
                        "    if n < 2:\n        return n\n"
                        "    return fibonacci(n - 1) + fibonacci(n - 2)\n```\n\n"
                        "**동작 원리:** `@lru_cache`가 이전 계산 결과를 캐싱하여 O(n) 시간복잡도를 달성합니다."
                    ),
                },
            ],
        }
        return _EXAMPLES.get(task_type, [])

    def clear_cache(self):
        """캐시를 비웁니다 (프롬프트 파일 수정 후 리로드 시)."""
        self._cache.clear()
