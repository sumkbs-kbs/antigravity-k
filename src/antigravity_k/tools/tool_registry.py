"""
ToolRegistry — 도구 자동 발견 및 등록 시스템
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

import logging
import importlib
import pkgutil
from typing import Dict, List, Optional, Type, Set, Any, Tuple

from .base_tool import BaseTool, ToolCategory, RenderIn, RiskLevel
from .permission_gate import PermissionGate, Permission

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    도구(Tool) 중앙 레지스트리.
    
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
    
    def __init__(self, project_root: Optional[str] = None):
        self._tools: Dict[str, BaseTool] = {}
        self._installed_classes: Set[str] = set()
        self._permission_gate = PermissionGate(project_root=project_root)
    
    def set_project_root(self, new_root: str):
        """런타임 중에 PermissionGate의 프로젝트 루트를 갱신합니다."""
        self._permission_gate.set_project_root(new_root)
        
    # ─────────────────── 등록 API ───────────────────
    
    def install(self, tool_or_class, **kwargs) -> "ToolRegistry":
        """
        도구를 레지스트리에 등록합니다 (tiptap-vuetify의 Plugin.install 패턴).
        
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
                f"Expected BaseTool class or instance, got {type(tool_or_class).__name__}"
            )
        
        # 중복 등록 방지
        class_name = type(tool).__name__
        if tool.name in self._tools:
            logger.warning(f"Tool '{tool.name}' already registered. Overwriting.")
        
        self._tools[tool.name] = tool
        self._installed_classes.add(class_name)
        logger.info(
            f"Installed tool: {tool.name} "
            f"[{tool.category.value}/{tool.risk_level.value}] "
            f"icon={tool.icon}"
        )
        return self
    
    def install_many(self, *tools) -> "ToolRegistry":
        """여러 도구를 한번에 등록합니다."""
        for t in tools:
            self.install(t)
        return self
    
    def auto_discover(self, package_name: str) -> int:
        """
        지정된 패키지에서 BaseTool 서브클래스를 자동 발견합니다.
        
        tiptap-vuetify의 autoInstall() 패턴에서 영감:
        window.Vue가 있으면 자동으로 플러그인 설치.
        
        Returns:
            발견/등록된 도구 수
        """
        count = 0
        try:
            package = importlib.import_module(package_name)
        except ImportError:
            logger.warning(f"Package '{package_name}' not found for auto-discovery.")
            return 0
        
        if not hasattr(package, "__path__"):
            logger.warning(f"'{package_name}' is not a package.")
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
                            logger.debug(
                                f"Could not auto-install {attr.__name__}: {e}"
                            )
            except Exception as e:
                logger.debug(f"Error importing {package_name}.{module_name}: {e}")
        
        logger.info(f"Auto-discovered {count} tools from '{package_name}'")
        return count
    
    # ─────────────────── 조회 API ───────────────────
    
    def get(self, name: str) -> Optional[BaseTool]:
        """이름으로 도구를 조회합니다."""
        return self._tools.get(name)
    
    def get_all(self) -> List[BaseTool]:
        """등록된 모든 도구 목록을 반환합니다."""
        return list(self._tools.values())
    
    def get_names(self) -> List[str]:
        """등록된 모든 도구 이름을 반환합니다."""
        return list(self._tools.keys())
    
    def get_by_names(self, names: List[str]) -> List[BaseTool]:
        """이름 목록으로 도구들을 조회합니다."""
        result = []
        for n in names:
            tool = self._tools.get(n)
            if tool:
                result.append(tool)
            else:
                logger.warning(f"Tool '{n}' not found in registry.")
        return result
    
    # ─────────────────── 필터링 API ───────────────────
    # tiptap-vuetify의 Extension RenderIn, Category 기반 필터링
    
    def filter_by_category(self, category: ToolCategory) -> List[BaseTool]:
        """카테고리별 도구 필터링."""
        return [t for t in self._tools.values() if t.category == category]
    
    def filter_by_risk(self, max_risk: RiskLevel) -> List[BaseTool]:
        """지정된 위험도 이하의 도구만 반환합니다."""
        risk_order = [
            RiskLevel.SAFE, RiskLevel.LOW, RiskLevel.MEDIUM,
            RiskLevel.HIGH, RiskLevel.CRITICAL
        ]
        max_idx = risk_order.index(max_risk)
        return [
            t for t in self._tools.values()
            if risk_order.index(t.risk_level) <= max_idx
        ]
    
    def filter_by_render(self, render_in: RenderIn) -> List[BaseTool]:
        """렌더 위치별 도구 필터링."""
        return [t for t in self._tools.values() if t.render_in == render_in]
    
    def get_toolbar_tools(self) -> List[BaseTool]:
        """항상 노출되는 주요 도구만 반환합니다."""
        return self.filter_by_render(RenderIn.TOOLBAR)
    
    def get_safe_tools(self) -> List[BaseTool]:
        """읽기 전용/안전한 도구만 반환합니다."""
        return self.filter_by_risk(RiskLevel.SAFE)
    
    # ─────────────────── 권한 게이트 API ───────────────────
    
    @property
    def permission_gate(self) -> PermissionGate:
        return self._permission_gate
    
    def execute_with_permission(
        self, tool_name: str, args: Dict[str, Any]
    ) -> Tuple[Permission, str]:
        """
        권한 검증 후 도구를 실행합니다 (Claw Code PermissionPolicy 패턴).
        
        Returns:
            (permission, result) 튜플:
            - Permission.ALLOW + 실행 결과
            - Permission.PROMPT + 승인 요청 메시지
            - Permission.DENY + 차단 사유
        """
        tool = self.get(tool_name)
        if not tool:
            return Permission.DENY, f"Error: Tool '{tool_name}' not found."
        
        # 권한 검증
        permission = self._permission_gate.check(
            tool_name, args, risk_level=tool.risk_level.value
        )
        
        if permission == Permission.DENY:
            return Permission.DENY, f"[DENIED] Tool '{tool_name}' blocked by permission policy."
        
        if permission == Permission.PROMPT:
            return Permission.PROMPT, (
                f"[APPROVAL REQUIRED] '{tool_name}' needs your permission.\n"
                f"Args: {args}\n"
                f"Risk: {tool.risk_level.value}"
            )
        
        # Permission.ALLOW — 즉시 실행
        result = tool(**args)
        return Permission.ALLOW, result
    
    def execute_approved(self, tool_name: str, args: Dict[str, Any]) -> str:
        """승인된 도구를 실행하고 캐시에 기록합니다."""
        tool = self.get(tool_name)
        if not tool:
            return f"Error: Tool '{tool_name}' not found."
        
        self._permission_gate.record_approval(tool_name, tool.risk_level.value)
        return tool(**args)
    
    # ─────────────────── 스키마 API ───────────────────
    
    def to_llm_schemas(self, names: Optional[List[str]] = None) -> List[Dict]:
        """LLM에 전달할 도구 스키마 목록을 생성합니다."""
        tools = self.get_by_names(names) if names else self.get_all()
        return [t.to_tool_call_schema() for t in tools]
    
    def to_metadata_list(self) -> List[Dict]:
        """UI 대시보드용 도구 메타데이터 목록."""
        return [t.to_metadata() for t in self._tools.values()]
    
    # ─────────────────── 정보 ───────────────────
    
    def summary(self) -> str:
        """레지스트리 상태 요약."""
        lines = [f"ToolRegistry: {len(self._tools)} tools installed"]
        
        # 카테고리별 통계
        cats: Dict[str, int] = {}
        for t in self._tools.values():
            cats[t.category.value] = cats.get(t.category.value, 0) + 1
        
        for cat, count in sorted(cats.items()):
            lines.append(f"  [{cat}] {count} tools")
        
        return "\n".join(lines)
    
    def __len__(self) -> int:
        return len(self._tools)
    
    def __contains__(self, name: str) -> bool:
        return name in self._tools
    
    def __repr__(self) -> str:
        return f"<ToolRegistry tools={list(self._tools.keys())}>"
