"""ToolRegistry — 도구 자동 발견 및 등록 시스템.

============================================

tiptap-vuetify의 TiptapVuetifyPlugin.install() 패턴에서 영감:
- 플러그인이 install() 메서드로 자기 자신을 프레임워크에 자동 등록
- 확장(Extension)이 각자의 availableActions를 선언적으로 노출
- 테마/아이콘이 글로벌 설정으로 일괄 관리

이를 Antigravity-K에 적용:
- BaseTool 서브클래스를 자동 발견하여 레지스트리에 등록
- 도구를 카테고리/위험도/렌더위치별로 필터링하여 에이전트에 할당
- 신규 도구 플러그인은 install()만 구현하면 자동 통합
"""

import importlib
import logging
import pkgutil
from typing import Any

from antigravity_k.engine.capability_policy import (
    AutonomousCapabilityPolicy,
    CapabilityDecision,
)

from .base_tool import BaseTool, RenderIn, RiskLevel, ToolCategory
from .permission_gate import Permission, PermissionGate

logger = logging.getLogger(__name__)


class ToolRegistry:
    """도구(Tool) 중앙 레지스트리.

    tiptap-vuetify의 Plugin 패턴을 차용:
    - install()로 자동 등록
    - 카테고리/위험도/렌더위치별 필터링
    - 이름 충돌 방지 및 감사 로그

    사용 예:
        registry = ToolRegistry()
        registry.install(ReadFileTool)        # 클래스로 등록
        registry.install(ReadFileTool())      # 인스턴스로 등록
        registry.auto_discover("antigravity_k.tools")  # 패키지 자동 탐색
    """

    def __init__(
        self,
        project_root: str | None = None,
        capability_policy_config: dict[str, Any] | None = None,
    ):
        """Initialize the ToolRegistry.

        Args:
            project_root (str | None): str | None project root.
            capability_policy_config (dict[str, Any] | None): dict[str, Any] | None capability policy config.

        """
        self._tools: dict[str, BaseTool] = {}
        self._installed_classes: set[str] = set()
        self._permission_gate = PermissionGate(project_root=project_root)
        policy_config = capability_policy_config or {}
        self._capability_policy = AutonomousCapabilityPolicy(
            project_root=project_root,
            max_autonomous_risk=str(policy_config.get("max_autonomous_risk", "high")),
            allow_critical_autonomy=bool(policy_config.get("allow_critical_autonomy", False)),
        )

    def set_project_root(self, new_root: str):
        """런타임 중에 PermissionGate의 프로젝트 루트를 갱신합니다."""
        self._permission_gate.set_project_root(new_root)
        self._capability_policy.set_project_root(new_root)

    # ─────────────────── 등록 API ───────────────────

    def install(self, tool_or_class, **kwargs) -> "ToolRegistry":
        """도구를 레지스트리에 등록합니다 (tiptap-vuetify의 Plugin.install 패턴).

        Args:
            tool_or_class: BaseTool 인스턴스 또는 BaseTool 서브클래스
            **kwargs: 클래스인 경우 생성자에 전달할 인자

        Returns:
            self (체이닝 가능)

        """
        if isinstance(tool_or_class, type) and issubclass(tool_or_class, BaseTool):
            # 클래스 → 인스턴스 생성
            tool = tool_or_class(**kwargs)
        elif isinstance(tool_or_class, BaseTool):
            # 이미 인스턴스
            tool = tool_or_class
        else:
            raise TypeError(
                f"Expected BaseTool class or instance, got {type(tool_or_class).__name__}",
            )

        # 중복 등록 방지
        class_name = type(tool).__name__
        if tool.name in self._tools:
            logger.warning("Tool '%s' already registered. Overwriting.", tool.name)

        self._tools[tool.name] = tool
        self._installed_classes.add(class_name)
        logger.info(
            "Installed tool: %s [%s/%s] icon=%s",
            tool.name,
            tool.category.value,
            tool.risk_level.value,
            tool.icon,
        )
        return self

    def install_many(self, *tools) -> "ToolRegistry":
        """여러 도구를 한번에 등록합니다."""
        for t in tools:
            self.install(t)
        return self

    def auto_discover(self, package_name: str) -> int:
        """지정된 패키지에서 BaseTool 서브클래스를 자동 발견합니다.

        tiptap-vuetify의 autoInstall() 패턴에서 영감:
        window.Vue가 있으면 자동으로 플러그인 설치.

        Returns:
            발견/등록된 도구 수

        """
        count = 0
        try:
            package = importlib.import_module(package_name)
        except ImportError:
            logger.warning("Package '%s' not found for auto-discovery.", package_name)
            return 0

        if not hasattr(package, "__path__"):
            logger.warning("'%s' is not a package.", package_name)
            return 0

        for importer, module_name, is_pkg in pkgutil.iter_modules(package.__path__):
            if module_name.startswith("_") or module_name == "base_tool":
                continue

            try:
                module = importlib.import_module(f"{package_name}.{module_name}")
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, BaseTool)
                        and attr is not BaseTool
                        and attr.__name__ not in self._installed_classes
                    ):
                        try:
                            self.install(attr)
                            count += 1
                        except Exception as e:
                            logger.exception("Unhandled exception")
                            logger.debug("Could not auto-install %s: %s", attr.__name__, e)
            except Exception as e:
                logger.exception("Unhandled exception")
                logger.debug("Error importing %s.%s: %s", package_name, module_name, e)

        logger.info("Auto-discovered %s tools from '%s'", count, package_name)
        return count

    # ─────────────────── 조회 API ───────────────────

    def get(self, name: str) -> BaseTool | None:
        """이름으로 도구를 조회합니다."""
        return self._tools.get(name)

    def get_all(self) -> list[BaseTool]:
        """등록된 모든 도구 목록을 반환합니다."""
        return list(self._tools.values())

    def get_names(self) -> list[str]:
        """등록된 모든 도구 이름을 반환합니다."""
        return list(self._tools.keys())

    def get_by_names(self, names: list[str]) -> list[BaseTool]:
        """이름 목록으로 도구들을 조회합니다."""
        result = []
        for n in names:
            tool = self._tools.get(n)
            if tool:
                result.append(tool)
            else:
                logger.warning("Tool '%s' not found in registry.", n)
        return result

    # ─────────────────── 필터링 API ───────────────────
    # tiptap-vuetify의 Extension RenderIn, Category 기반 필터링

    def filter_by_category(self, category: ToolCategory) -> list[BaseTool]:
        """카테고리별 도구 필터링."""
        return [t for t in self._tools.values() if t.category == category]

    def filter_by_risk(self, max_risk: RiskLevel) -> list[BaseTool]:
        """지정된 위험도 이하의 도구만 반환합니다."""
        risk_order = [
            RiskLevel.SAFE,
            RiskLevel.LOW,
            RiskLevel.MEDIUM,
            RiskLevel.HIGH,
            RiskLevel.CRITICAL,
        ]
        max_idx = risk_order.index(max_risk)
        return [t for t in self._tools.values() if risk_order.index(t.risk_level) <= max_idx]

    def filter_by_render(self, render_in: RenderIn) -> list[BaseTool]:
        """렌더 위치별 도구 필터링."""
        return [t for t in self._tools.values() if t.render_in == render_in]

    def get_toolbar_tools(self) -> list[BaseTool]:
        """항상 노출되는 주요 도구만 반환합니다."""
        return self.filter_by_render(RenderIn.TOOLBAR)

    def get_safe_tools(self) -> list[BaseTool]:
        """읽기 전용/안전한 도구만 반환합니다."""
        return self.filter_by_risk(RiskLevel.SAFE)

    # ─────────────────── 권한 게이트 API ───────────────────

    @property
    def permission_gate(self) -> PermissionGate:
        """Permission Gate.

        Returns:
            PermissionGate: The permissiongate result.

        """
        return self._permission_gate

    def execute_with_permission(
        self,
        tool_name: str,
        args: dict[str, Any],
        objective: str = "",
    ) -> tuple[Permission, str]:
        """권한 검증 후 도구를 실행합니다 (Claw Code PermissionPolicy 패턴).

        Returns:
            (permission, result) 튜플:
            - Permission.ALLOW + 실행 결과
            - Permission.PROMPT + 승인 요청 메시지
            - Permission.DENY + 차단 사유

        """
        tool = self.get(tool_name)
        if not tool:
            return Permission.DENY, f"Error: Tool '{tool_name}' not found."

        # 자율 capability 정책: MCP/Skills/로컬 PC 도구를 한 정책 언어로 판정합니다.
        capability_decision = self._capability_policy.decide_tool(
            tool,
            args=args,
            objective=objective,
        )
        if capability_decision.is_blocked:
            return (
                Permission.DENY,
                f"[DENIED] {capability_decision.reason}",
            )
        if capability_decision.requires_approval:
            return Permission.PROMPT, (
                f"[APPROVAL REQUIRED] '{tool_name}' needs your permission.\n"
                f"Args: {args}\n"
                f"Risk: {tool.risk_level.value}\n"
                f"Reason: {capability_decision.reason}"
            )

        # 권한 검증
        permission = self._permission_gate.check(tool_name, args, risk_level=tool.risk_level.value)

        if permission == Permission.DENY:
            return (
                Permission.DENY,
                f"[DENIED] Tool '{tool_name}' blocked by permission policy.",
            )

        if permission == Permission.PROMPT:
            return Permission.PROMPT, (
                f"[APPROVAL REQUIRED] '{tool_name}' needs your permission.\nArgs: {args}\nRisk: {tool.risk_level.value}"
            )

        # Permission.ALLOW — 즉시 실행
        if tool_name == "run_bash_command":
            args = {**args, "approved": True}
        result = tool(**args)
        return Permission.ALLOW, result

    def decide_tool_use(
        self,
        tool_name: str,
        args: dict[str, Any] | None = None,
        objective: str = "",
    ) -> CapabilityDecision | None:
        """도구 실행 전 자율 판단 결과를 반환합니다."""
        tool = self.get(tool_name)
        if not tool:
            return None
        return self._capability_policy.decide_tool(tool, args=args or {}, objective=objective)

    def get_autonomous_manifest(self, objective: str = "") -> list[CapabilityDecision]:
        """현재 등록된 모든 도구의 자율 사용 가능성을 반환합니다."""
        return [
            self._capability_policy.decide_tool(tool, args={}, objective=objective) for tool in self._tools.values()
        ]

    def render_autonomous_policy(self) -> str:
        """LLM 시스템 프롬프트에 주입할 capability 정책 요약."""
        return self._capability_policy.render_policy_prompt()

    def execute_approved(self, tool_name: str, args: dict[str, Any]) -> str:
        """승인된 도구를 실행하고 캐시에 기록합니다."""
        tool = self.get(tool_name)
        if not tool:
            return f"Error: Tool '{tool_name}' not found."

        self._permission_gate.record_approval(tool_name, tool.risk_level.value)
        return tool(**args)

    # ─────────────────── 스키마 API ───────────────────

    def to_llm_schemas(self, names: list[str] | None = None) -> list[dict]:
        """LLM에 전달할 도구 스키마 목록을 생성합니다."""
        tools = self.get_by_names(names) if names else self.get_all()
        return [t.to_tool_call_schema() for t in tools]

    def to_metadata_list(self) -> list[dict]:
        """UI 대시보드용 도구 메타데이터 목록."""
        return [t.to_metadata() for t in self._tools.values()]

    # ─────────────────── 정보 ───────────────────

    def summary(self) -> str:
        """레지스트리 상태 요약."""
        lines = [f"ToolRegistry: {len(self._tools)} tools installed"]

        # 카테고리별 통계
        cats: dict[str, int] = {}
        for t in self._tools.values():
            cats[t.category.value] = cats.get(t.category.value, 0) + 1

        for cat, count in sorted(cats.items()):
            lines.append(f"  [{cat}] {count} tools")

        return "\n".join(lines)

    def __len__(self) -> int:
        """Return the length.

        Returns:
            int: The int result.

        """
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        """Check if contains item.

        Args:
            name (str): str name.

        Returns:
            bool: The bool result.

        """
        return name in self._tools

    def __repr__(self) -> str:
        """Return a formal string representation.

        Returns:
            str: The str result.

        """
        return f"<ToolRegistry tools={list(self._tools.keys())}>"
