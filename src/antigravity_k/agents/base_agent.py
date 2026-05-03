import logging
from typing import List, Dict, Any, Optional

from ..i18n import get_i18n

logger = logging.getLogger(__name__)

class BaseAgent:
    """
    기본 에이전트 클래스. Hermes 방식의 명시적 추론(Reasoning) 블록을 강제하여
    에이전트가 행동하기 전 사고 과정(Chain of Thought)을 가지도록 합니다.
    """
    def __init__(self, name: str, role: str, system_prompt: str, model_id: str):
        self.name = name
        self.role = role
        self.system_prompt = system_prompt
        self.model_id = model_id
        self.history: List[Dict[str, str]] = []

    def _build_system_prompt(self) -> str:
        """
        GStack 기반의 페르소나와 Hermes 추론 구조를 결합한 시스템 프롬프트 생성.
        I18n을 통해 사용자 언어에 맞는 응답 지시문을 자동 구성합니다.
        """
        i18n = get_i18n()
        locale = i18n.locale

        # 언어별 추론 지시문
        reasoning_templates = {
            "ko": (
                "당신은 고도로 능력 있는 에이전트입니다. 답변하기 전에 반드시 <thought>...</thought> 태그 안에 "
                "내부 사고 과정을 작성하세요. 문제를 분석하고 엣지 케이스를 고려한 후 최종 응답을 제공하세요. "
                "한국어로 답변하세요."
            ),
            "en": (
                "You are a highly capable agent. Before taking any action or providing a final answer, "
                "you MUST explicitly write down your internal reasoning process within <thought>...</thought> XML tags. "
                "Use this space to break down the problem, consider edge cases, and plan your approach. "
                "After your thought process, output your final response or action."
            ),
            "ja": (
                "あなたは非常に有能なエージェントです。回答する前に、必ず <thought>...</thought> タグ内に"
                "内部的な思考過程を記述してください。問題を分析し、エッジケースを考慮した後、"
                "最終的な回答を提供してください。日本語で回答してください。"
            ),
        }

        reasoning_instruction = reasoning_templates.get(locale, reasoning_templates["en"])
        return f"{self.system_prompt}\n\n{reasoning_instruction}"

    def add_message(self, role: str, content: str):
        self.history.append({"role": role, "content": content})

    def get_messages(self) -> List[Dict[str, str]]:
        messages = [{"role": "system", "content": self._build_system_prompt()}]
        messages.extend(self.history)
        return messages

    def run(self, context: str, model_manager=None, tools: Optional[List[Any]] = None) -> str:
        """
        주어진 컨텍스트를 처리하고 모델을 통해 응답을 생성합니다.
        <think> 또는 <thought> 태그 내의 추론과 <tool_call> 태그를 파싱하여 도구를 실행하는 재귀적 루프를 포함합니다.
        """
        self.add_message("user", context)
        
        if not model_manager:
            logger.warning("ModelManager not provided. Running in mock mode.")
            return self._mock_run()
            
        loaded_model = model_manager.get(self.model_id)
        
        if hasattr(loaded_model.model, 'name') and 'Dummy' in repr(loaded_model.model):
            return self._mock_run()
            
        MAX_ITERATIONS = 5
        iteration = 0
        
        while iteration < MAX_ITERATIONS:
            iteration += 1
            messages = self.get_messages()
            
            try:
                # Use model_manager's standard routing and generation instead of direct mlx_lm
                # Since prompt format might differ per model, we rely on model_manager (or just pass messages)
                if hasattr(model_manager, 'generate'):
                    response = model_manager.generate(
                        prompt=messages[-1]["content"] if messages else "",
                        target=self.model_id,
                        raw_messages=messages,
                        max_tokens=2048,
                        temperature=0.7
                    )
                else:
                    # Fallback if generate not fully compatible with raw_messages
                    from mlx_lm import generate
                    prompt = loaded_model.tokenizer.apply_chat_template(
                        messages, tokenize=False, add_generation_prompt=True
                    )
                    response = generate(
                        loaded_model.model,
                        loaded_model.tokenizer,
                        prompt=prompt,
                        max_tokens=2048,
                        verbose=False
                    )
                
                self.add_message("assistant", response)
                
                # 도구 호출 파싱 로직 (<tool_call> JSON </tool_call>)
                import re
                tool_call_match = re.search(r"<tool_call>(.*?)</tool_call>", response, re.DOTALL)
                
                if tool_call_match and tools:
                    tool_call_text = tool_call_match.group(1).strip()
                    try:
                        import json
                        tool_req = json.loads(tool_call_text)
                        tool_name = tool_req.get("name")
                        tool_args = tool_req.get("arguments", {})
                        
                        tool_result = f"Error: Tool {tool_name} not found"
                        for t in tools:
                            if t.name == tool_name:
                                tool_result = t(**tool_args)
                                break
                                
                        self.add_message("tool", f"<tool_response>\n{tool_result}\n</tool_response>")
                        continue  # 도구 실행 결과를 바탕으로 다시 모델 호출
                    except Exception as e:
                        self.add_message("tool", f"<tool_response>\nError parsing tool call: {e}\n</tool_response>")
                        continue
                
                return response
                
            except Exception as e:
                logger.error(f"Error during model generation: {e}")
                return f"Error: {e}"
                
        return "Error: Maximum iterations reached."

    def _mock_run(self) -> str:
        """테스트 및 Windows 개발 환경을 위한 더미 실행"""
        response = (
            "<thought>\n"
            "This is a dummy thought process for testing.\n"
            "</thought>\n"
            "이것은 더미 응답입니다."
        )
        self.add_message("assistant", response)
        return response
