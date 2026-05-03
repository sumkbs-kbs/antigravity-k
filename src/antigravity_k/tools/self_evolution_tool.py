import os
import json
import ast
import logging
import threading
from typing import Any, Dict
from antigravity_k.tools.base_tool import BaseTool, ToolCategory, RenderIn, RiskLevel

logger = logging.getLogger(__name__)

class SelfEvolutionTool(BaseTool):
    """
    SelfEvolutionTool: 자체 진화 도구
    =================================
    Antigravity-K가 자기 자신의 코드베이스를 분석하고 개선하는 메타-도구입니다.
    
    워크플로우:
      1. 진화 목표 분석 (LLM)
      2. 현재 코드베이스 스캔 (관련 파일 자동 탐색)
      3. 웹 검색으로 최신 기술/패턴 학습
      4. 개선 코드 생성 (LLM)
      5. _drafts/ 저장 → AST 검증 → 사용자 승인 대기
      6. 승인 시 적용 + Git 커밋 + Vault 스냅샷
    """
    category = ToolCategory.CODE_EXEC
    render_in = RenderIn.CONTEXTUAL
    risk_level = RiskLevel.HIGH
    icon = "🧬"
    tags = ["evolve", "meta", "self_healing", "refactor"]

    def __init__(self):
        super().__init__()
        self._name = "trigger_self_evolution"
        self._description = (
            "Triggers the Self-Evolution Engine to analyze and improve the Antigravity-K codebase. "
            "Use when the user asks to 'evolve', 'upgrade yourself', 'refactor your core engine', "
            "or 'create a new tool/skill'. Supports two modes:\n"
            "  - mode='evolve': Improve existing code\n"
            "  - mode='generate_skill': Create a brand new tool"
        )
        self._schema = {
            "type": "object",
            "properties": {
                "evolution_goal": {
                    "type": "string",
                    "description": "A detailed explanation of what to optimize, add, or create."
                },
                "mode": {
                    "type": "string",
                    "enum": ["evolve", "generate_skill"],
                    "description": "Evolution mode: 'evolve' to improve existing code, 'generate_skill' to create a new tool."
                },
                "target_files": {
                    "type": "string",
                    "description": "Optional comma-separated list of files to focus on (e.g., 'orchestrator.py,model_manager.py')"
                }
            },
            "required": ["evolution_goal"]
        }

    @property
    def name(self) -> str: return self._name
    @property
    def description(self) -> str: return self._description
    @property
    def parameters_schema(self) -> Dict[str, Any]: return self._schema

    def execute(self, **kwargs) -> Any:
        goal = kwargs.get("evolution_goal")
        mode = kwargs.get("mode", "evolve")
        target_files = kwargs.get("target_files", "")

        if not goal:
            return "Error: Missing evolution_goal parameter."

        if mode == "generate_skill":
            return self._generate_new_skill(goal)
        else:
            return self._evolve_codebase(goal, target_files)

    def _generate_new_skill(self, goal: str) -> str:
        """새로운 도구를 자동 생성합니다."""
        try:
            from antigravity_k.engine.skill_generator import SkillGenerator
            
            project_root = self._find_project_root()
            generator = SkillGenerator(project_root=project_root)
            result = generator.generate_skill(goal)
            
            if result["success"]:
                return result["message"]
            else:
                return f"❌ 스킬 생성 실패: {result['message']}"
        except Exception as e:
            logger.error(f"Skill generation error: {e}", exc_info=True)
            return f"❌ 스킬 생성 중 오류: {e}"

    def _evolve_codebase(self, goal: str, target_files: str) -> str:
        """기존 코드베이스를 분석하고 개선합니다."""
        project_root = self._find_project_root()
        drafts_dir = os.path.join(project_root, "_drafts", "evolution")
        os.makedirs(drafts_dir, exist_ok=True)

        try:
            # 1. 대상 파일 탐색
            targets = self._find_target_files(project_root, target_files, goal)
            if not targets:
                return "⚠️ 진화 대상 파일을 찾을 수 없습니다."

            # 2. 현재 코드 읽기
            code_context = {}
            for fpath in targets[:5]:  # 최대 5개 파일
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        content = f.read()
                    # 파일이 너무 크면 첫 200줄만
                    lines = content.split("\n")
                    if len(lines) > 200:
                        content = "\n".join(lines[:200]) + f"\n... ({len(lines)-200} more lines)"
                    code_context[os.path.relpath(fpath, project_root)] = content
                except Exception:
                    pass

            # 3. 웹에서 최신 패턴 학습 (선택적)
            web_context = ""
            try:
                from antigravity_k.tools.web_search import WebSearchTool
                search = WebSearchTool()
                web_context = search.execute(query=f"{goal} best practices Python 2025")
            except Exception:
                pass

            # 4. LLM으로 개선 코드 생성
            patches = self._generate_patches(goal, code_context, web_context)
            
            if not patches:
                return "⚠️ LLM이 개선 사항을 생성하지 못했습니다."

            # 5. _drafts/에 저장 + AST 검증
            results = []
            for filename, patch_code in patches.items():
                # AST 검증
                try:
                    ast.parse(patch_code)
                    valid = True
                except SyntaxError as e:
                    valid = False
                    results.append(f"❌ {filename}: 구문 오류 — {e}")
                    continue

                # 저장
                draft_path = os.path.join(drafts_dir, filename)
                os.makedirs(os.path.dirname(draft_path), exist_ok=True)
                with open(draft_path, "w", encoding="utf-8") as f:
                    f.write(patch_code)
                results.append(f"✅ {filename}: 패치 저장 ({len(patch_code)} bytes)")

            # 메타데이터 저장
            meta = {
                "goal": goal,
                "target_files": list(code_context.keys()),
                "patches": list(patches.keys()),
                "generated_at": __import__("datetime").datetime.now().isoformat(),
                "status": "pending_review",
            }
            with open(os.path.join(drafts_dir, "_evolution_meta.json"), "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)

            report = "\n".join(results)
            return (
                f"🧬 **[자체 진화 완료]** 목표: {goal}\n\n"
                f"📋 결과:\n{report}\n\n"
                f"📁 패치 위치: {drafts_dir}\n"
                f"⚠️ 패치는 `_drafts/evolution/`에 저장되었습니다.\n"
                f"사용자가 검토 후 승인해야 실제 적용됩니다."
            )
        except Exception as e:
            logger.error(f"Evolution error: {e}", exc_info=True)
            return f"❌ 진화 프로세스 오류: {e}"

    def _find_project_root(self) -> str:
        """프로젝트 루트를 찾습니다."""
        # 현재 파일 기준으로 탐색
        current = os.path.dirname(os.path.abspath(__file__))
        for _ in range(5):
            if os.path.exists(os.path.join(current, "config.yaml")):
                return current
            current = os.path.dirname(current)
        return os.getcwd()

    def _find_target_files(self, project_root: str, target_files: str, goal: str) -> list:
        """진화 대상 파일을 탐색합니다."""
        targets = []
        
        # 명시적 대상 파일이 있으면 우선 사용
        if target_files:
            for tf in target_files.split(","):
                tf = tf.strip()
                full_path = os.path.join(project_root, "src", "antigravity_k", "engine", tf)
                if os.path.exists(full_path):
                    targets.append(full_path)
                else:
                    # 전체 프로젝트에서 검색
                    for root, dirs, files in os.walk(os.path.join(project_root, "src")):
                        if tf in files:
                            targets.append(os.path.join(root, tf))
                            break
        
        # 명시적 대상이 없으면 goal 키워드로 관련 파일 탐색
        if not targets:
            keywords = goal.lower().split()
            engine_dir = os.path.join(project_root, "src", "antigravity_k", "engine")
            tools_dir = os.path.join(project_root, "src", "antigravity_k", "tools")
            
            for search_dir in [engine_dir, tools_dir]:
                if not os.path.exists(search_dir):
                    continue
                for fname in os.listdir(search_dir):
                    if not fname.endswith(".py"):
                        continue
                    basename = fname[:-3].lower()
                    if any(kw in basename for kw in keywords):
                        targets.append(os.path.join(search_dir, fname))
        
        return targets

    def _generate_patches(self, goal: str, code_context: dict, web_context: str) -> dict:
        """LLM으로 개선 패치를 생성합니다."""
        import urllib.request
        import re
        
        files_text = ""
        for fname, content in code_context.items():
            files_text += f"\n--- {fname} ---\n{content}\n"

        prompt = (
            "You are an expert Python developer evolving the Antigravity-K AI framework.\n\n"
            f"Evolution Goal: {goal}\n\n"
            f"Current Code:\n{files_text}\n"
        )
        if web_context:
            prompt += f"\nWeb Research (latest patterns):\n{web_context[:2000]}\n"
        
        prompt += (
            "\nGenerate improved versions of the files. Return ONLY a JSON object where:\n"
            "- keys are filenames (e.g., 'orchestrator.py')\n"
            "- values are the complete improved Python code\n\n"
            "Return ONLY valid JSON. No markdown, no explanation."
        )

        try:
            data = {
                "model": "qwen3.6:latest",
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": 4096, "temperature": 0.3}
            }
            req = urllib.request.Request(
                "http://localhost:11434/api/generate",
                data=json.dumps(data).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                text = result.get("response", "")

            # <think> 태그 제거
            text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
            
            # JSON 추출
            decoder = json.JSONDecoder()
            for i, ch in enumerate(text):
                if ch == '{':
                    try:
                        obj, _ = decoder.raw_decode(text, i)
                        if isinstance(obj, dict) and all(
                            isinstance(v, str) for v in obj.values()
                        ):
                            return obj
                    except json.JSONDecodeError:
                        continue

        except Exception as e:
            logger.error(f"Patch generation failed: {e}")
        
        return {}
