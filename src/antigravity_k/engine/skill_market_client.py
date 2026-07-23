"""Skill Market Client — npm Registry 기반 Skill Marketplace 클라이언트.

==========================================================
Phase 1: npm 레지스트리에서 @antigravity-k/skill-* 패키지를
검색/조회/설치상태 관리합니다.

사용법:
    client = SkillMarketClient()
    results = client.search("code review")
    detail = client.get_detail("@antigravity-k/skill-code-review")
    installed = client.get_installed()
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ─── 상수 ─────────────────────────────────────────────────────────────

AGK_SKILL_SCOPE = "@antigravity-k/skill-"
"""npm 스킬 패키지 스코프 프리픽스."""

MARKET_STATE_DIR = ".agent/skills/market"
"""프로젝트 내 마켓 스킬 설치 디렉토리."""

GLOBAL_STATE_FILE = "~/.antigravity-k/skills-market.json"
"""전역 설치 상태 파일."""


# ─── 데이터 모델 ──────────────────────────────────────────────────────


@dataclass
class SkillListing:
    """npm search 결과 하나의 스킬 리스팅."""

    name: str  # "@antigravity-k/skill-code-review"
    version: str  # "1.2.3"
    description: str  # "자동 코드 리뷰 — 품질 피드백 제공"
    keywords: list[str] = field(default_factory=list)
    publisher: str = ""
    date: str = ""
    npm_url: str = ""
    homepage: str = ""
    repository: str = ""

    @property
    def skill_name(self) -> str:
        """스킬 짧은 이름 (e.g. 'code-review')."""
        return self.name[len(AGK_SKILL_SCOPE) :] if self.name.startswith(AGK_SKILL_SCOPE) else self.name

    @property
    def is_agk_skill(self) -> bool:
        """AGK 스킬 패키지 여부."""
        return self.name.startswith(AGK_SKILL_SCOPE)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "skill_name": self.skill_name,
            "version": self.version,
            "description": self.description,
            "keywords": self.keywords,
            "publisher": self.publisher,
            "date": self.date,
        }


@dataclass
class SkillDetail:
    """npm view로 조회한 스킬 상세 정보.

    npm view는 package.json 전체를 JSON으로 반환합니다.
    antigravityK 필드에서 AGK 전용 메타데이터를 추출합니다.
    """

    name: str
    version: str
    description: str
    keywords: list[str] = field(default_factory=list)

    # package.json 원본
    raw_package_json: dict[str, Any] = field(default_factory=dict)

    # AGK 전용 메타데이터 (antigravityK 필드)
    agk_skill: bool = False
    agk_display_name: str = ""
    agk_categories: list[str] = field(default_factory=list)
    agk_min_agent_version: str = ""
    agk_platforms: list[str] = field(default_factory=list)
    agk_required_tools: list[str] = field(default_factory=list)
    agk_optional_tools: list[str] = field(default_factory=list)
    agk_risk_level: str = "medium"
    agk_trust_level: str = "experimental"
    agk_requires_approval: bool = False
    agk_auto_match_keywords: list[str] = field(default_factory=list)

    # MCP 설정 (선택)
    agk_mcp_server_id: str = ""
    agk_mcp_transport: str = ""

    # 메타
    license: str = ""
    homepage: str = ""
    repository: str = ""
    npm_url: str = ""
    last_published: str = ""
    readme_filename: str = ""
    has_readme: bool = False

    @property
    def skill_name(self) -> str:
        return self.name[len(AGK_SKILL_SCOPE) :] if self.name.startswith(AGK_SKILL_SCOPE) else self.name

    @property
    def is_agk_skill(self) -> bool:
        return self.agk_skill or self.name.startswith(AGK_SKILL_SCOPE)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "skill_name": self.skill_name,
            "version": self.version,
            "description": self.description,
            "keywords": self.keywords,
            "agk": {
                "skill": self.agk_skill,
                "display_name": self.agk_display_name,
                "categories": self.agk_categories,
                "min_agent_version": self.agk_min_agent_version,
                "platforms": self.agk_platforms,
                "required_tools": self.agk_required_tools,
                "risk_level": self.agk_risk_level,
                "trust_level": self.agk_trust_level,
                "auto_match_keywords": self.agk_auto_match_keywords,
                "mcp_server_id": self.agk_mcp_server_id,
            },
            "license": self.license,
            "homepage": self.homepage,
        }


@dataclass
class InstalledSkill:
    """로컬에 설치된 스킬의 상태 정보."""

    name: str
    version: str
    skill_name: str
    description: str = ""
    install_path: str = ""
    installed_at: str = ""
    updated_at: str = ""
    risk_level: str = "safe"
    trust_level: str = "verified"
    requires_approval: bool = False
    mcp_server_id: str = ""
    """연결된 MCP 서버 ID (MCP 스킬인 경우, .agk_meta.json에서 읽음)."""

    @property
    def is_outdated(self) -> bool:
        """업데이트 필요 여부 (최신 버전과 비교)."""
        return False  # 최신 버전은 별도 조회 필요

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "skill_name": self.skill_name,
            "description": self.description,
            "install_path": self.install_path,
            "installed_at": self.installed_at,
            "updated_at": self.updated_at,
            "risk_level": self.risk_level,
            "trust_level": self.trust_level,
            "mcp_server_id": self.mcp_server_id,
        }


# ─── 메인 클라이언트 ──────────────────────────────────────────────────


class SkillMarketClient:
    """npm Registry 기반 Skill Marketplace 클라이언트.

    npm CLI를 통해 @antigravity-k/skill-* 패키지를 검색/조회하고,
    로컬 설치 상태를 파일 기반으로 관리합니다.
    """

    def __init__(self, project_root: str | None = None):
        """Initialize the SkillMarketClient.

        Args:
            project_root: 프로젝트 루트 (설치 상태 파일 위치 결정)
        """
        self.project_root = project_root or os.getcwd()
        self._market_dir = Path(self.project_root) / MARKET_STATE_DIR
        self._state_file = Path(self.project_root) / GLOBAL_STATE_FILE.replace("~", str(Path.home()))

    # ─── 검색 ───────────────────────────────────────────────────────

    def search(self, query: str, limit: int = 20) -> list[SkillListing]:
        """npm 레지스트리에서 스킬을 검색합니다.

        검색 전략:
        1. `npm search <query>` 실행
        2. 결과 중 @antigravity-k/skill-* 프리픽스 매칭
        3. 매칭된 결과가 부족하면 키워드 "antigravity-k skill"로 재검색

        Args:
            query: 검색어 (e.g. "code review", "rag", "testing")
            limit: 최대 결과 수

        Returns:
            SkillListing 리스트
        """
        # 1차: 일반 검색
        results = self._run_npm_search(query, limit)

        # 2차: AGK 스킬이 충분하지 않으면 키워드 검색
        agk_results = [r for r in results if r.is_agk_skill]
        if len(agk_results) < 5:
            keyword_results = self._run_npm_search(f"keywords:antigravity-k,skill,{query}", limit)
            for kr in keyword_results:
                if kr.is_agk_skill and kr.name not in {r.name for r in results}:
                    results.append(kr)

        # 점수 정렬: AGK 스킬 우선, 설명 일치도
        query_lower = query.lower()
        scored = []
        for r in results:
            score = 0
            if r.is_agk_skill:
                score += 10
            if query_lower in r.description.lower():
                score += 5
            if query_lower in r.name.lower():
                score += 3
            if query_lower in " ".join(r.keywords).lower():
                score += 2
            scored.append((score, r))

        scored.sort(key=lambda x: -x[0])
        return [r for _, r in scored[:limit]]

    def search_by_category(self, category: str, limit: int = 20) -> list[SkillListing]:
        """카테고리별 스킬 검색.

        Args:
            category: 카테고리명 (e.g. "code-quality", "data", "devops")
            limit: 최대 결과 수

        Returns:
            SkillListing 리스트
        """
        return self.search(f"keywords:{category}", limit)

    def get_detail(self, package_name: str) -> SkillDetail | None:
        """npm 레지스트리에서 패키지 상세 정보를 조회합니다.

        Args:
            package_name: 패키지 전체 이름 (e.g. "@antigravity-k/skill-code-review")

        Returns:
            SkillDetail 객체 (실패 시 None)
        """
        try:
            result = subprocess.run(
                ["npm", "view", package_name, "--json"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                logger.warning(
                    "[SkillMarket] npm view failed for '%s': %s",
                    package_name,
                    result.stderr.strip(),
                )
                return None

            raw = json.loads(result.stdout)
            return self._parse_view_result(package_name, raw)

        except json.JSONDecodeError as e:
            logger.warning("[SkillMarket] Failed to parse npm view output: %s", e)
            return None
        except subprocess.TimeoutExpired:
            logger.warning("[SkillMarket] npm view timed out for '%s'", package_name)
            return None
        except FileNotFoundError:
            logger.error("[SkillMarket] npm CLI not found")
            return None
        except Exception as e:
            logger.exception("[SkillMarket] npm view error for '%s': %s", package_name, e)
            return None

    # ─── 설치 상태 관리 ─────────────────────────────────────────────

    def get_installed(self, project_root: str | None = None) -> list[InstalledSkill]:
        """로컬에 설치된 스킬 목록을 반환합니다.

        project_root가 지정되면 해당 프로젝트의 .agent/skills/market/ 스캔,
        없으면 현재 프로젝트 + 글로벌 상태 파일 조회.

        Args:
            project_root: 검색할 프로젝트 루트 (기본: 현재 프로젝트)

        Returns:
            InstalledSkill 리스트
        """
        installed: dict[str, InstalledSkill] = {}

        # 1. 프로젝트 market 디렉토리 스캔
        market_dir = Path(project_root or self.project_root) / MARKET_STATE_DIR
        if market_dir.exists():
            for skill_dir in market_dir.iterdir():
                if not skill_dir.is_dir():
                    continue
                meta_file = skill_dir / ".agk_meta.json"
                if meta_file.exists():
                    try:
                        meta = json.loads(meta_file.read_text(encoding="utf-8"))
                        skill = InstalledSkill(
                            name=meta.get("name", skill_dir.name),
                            version=meta.get("version", "0.0.0"),
                            skill_name=skill_dir.name,
                            description=meta.get("description", ""),
                            install_path=str(skill_dir),
                            installed_at=meta.get("installed_at", ""),
                            updated_at=meta.get("updated_at", ""),
                            risk_level=meta.get("risk_level", "safe"),
                            trust_level=meta.get("trust_level", "verified"),
                            mcp_server_id=meta.get("mcp_server_id", ""),
                        )
                        installed[skill.skill_name] = skill
                    except Exception:
                        continue

        # 2. 글로벌 상태 파일 조회
        state_file = self._state_file
        if state_file.exists():
            try:
                global_state = json.loads(state_file.read_text(encoding="utf-8"))
                for skill_name, data in global_state.get("installed", {}).items():
                    if skill_name not in installed:
                        skill = InstalledSkill(
                            name=data.get("name", f"{AGK_SKILL_SCOPE}{skill_name}"),
                            version=data.get("version", "0.0.0"),
                            skill_name=skill_name,
                            description=data.get("description", ""),
                            install_path=data.get("install_path", ""),
                            installed_at=data.get("installed_at", ""),
                            updated_at=data.get("updated_at", ""),
                            risk_level=data.get("risk_level", "safe"),
                            trust_level=data.get("trust_level", "verified"),
                        )
                        installed[skill_name] = skill
            except Exception:
                logger.warning("예외 발생 (silent swallow 제거)", exc_info=True)

        return list(installed.values())

    def is_installed(self, skill_name: str, project_root: str | None = None) -> bool:
        """특정 스킬이 설치되어 있는지 확인합니다.

        Args:
            skill_name: 스킬 이름 (e.g. "code-review")
            project_root: 확인할 프로젝트 루트

        Returns:
            설치 여부
        """
        installed = self.get_installed(project_root)
        return any(s.skill_name == skill_name for s in installed)

    def record_installation(self, package_name: str, version: str, install_path: str):
        """스킬 설치를 상태 파일에 기록합니다.

        Args:
            package_name: 패키지 전체 이름
            version: 설치된 버전
            install_path: 설치 경로
        """
        skill_name = package_name[len(AGK_SKILL_SCOPE) :] if package_name.startswith(AGK_SKILL_SCOPE) else package_name

        state: dict[str, Any] = {"installed": {}}
        state_file = self._state_file

        # 기존 상태 로드
        if state_file.exists():
            try:
                state = json.loads(state_file.read_text(encoding="utf-8"))
            except Exception:
                state = {"installed": {}}

        now = datetime.now().isoformat()
        state.setdefault("installed", {})[skill_name] = {
            "name": package_name,
            "version": version,
            "install_path": install_path,
            "installed_at": state.get("installed", {}).get(skill_name, {}).get("installed_at", now),
            "updated_at": now,
        }

        try:
            state_file.parent.mkdir(parents=True, exist_ok=True)
            state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.info("[SkillMarket] Installation recorded: %s@%s", package_name, version)
        except Exception as e:
            logger.warning("[SkillMarket] Failed to record installation: %s", e)

    def remove_installation(self, skill_name: str):
        """스킬 설치 기록을 제거합니다.

        Args:
            skill_name: 스킬 이름 (e.g. "code-review")
        """
        state_file = self._state_file
        if not state_file.exists():
            return

        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
            state.get("installed", {}).pop(skill_name, None)
            state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.info("[SkillMarket] Installation removed: %s", skill_name)
        except Exception as e:
            logger.warning("[SkillMarket] Failed to remove installation: %s", e)

    # ─── 유틸리티 ───────────────────────────────────────────────────

    @staticmethod
    def is_valid_package_name(name: str) -> bool:
        """유효한 AGK 스킬 패키지명인지 확인합니다."""
        return bool(name.startswith(AGK_SKILL_SCOPE) and len(name) > len(AGK_SKILL_SCOPE))

    def format_search_results(self, results: list[SkillListing]) -> str:
        """검색 결과를 사용자 친화적인 마크다운으로 포맷팅합니다."""
        if not results:
            return "🔍 검색 결과가 없습니다. 다른 검색어를 시도해보세요."

        lines = [
            "🔍 **Skill Marketplace 검색 결과**",
            "",
        ]

        for i, r in enumerate(results[:15], 1):
            installed_mark = "✅" if self.is_installed(r.skill_name) else "📦"
            version = r.version
            desc = (r.description[:80] + "...") if len(r.description) > 80 else r.description
            lines.append(f"  {installed_mark} `{r.name}@{version}`")
            lines.append(f"     {desc}")
            lines.append("")

        if len(results) > 15:
            lines.append(f"  ... 외 {len(results) - 15}개 결과")

        return "\n".join(lines)

    # ─── 내부 ───────────────────────────────────────────────────────

    def _run_npm_search(self, query: str, limit: int = 20) -> list[SkillListing]:
        """npm search 명령어를 실행하고 결과를 파싱합니다."""
        try:
            result = subprocess.run(
                ["npm", "search", query, "--json", f"--searchlimit={limit}"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                logger.debug("[SkillMarket] npm search error: %s", result.stderr.strip()[:200])
                return []

            raw_results = json.loads(result.stdout)
            if not isinstance(raw_results, list):
                return []

            listings = []
            for item in raw_results:
                if not isinstance(item, dict):
                    continue
                name = item.get("name", "")
                links = item.get("links", {}) or {}
                listing = SkillListing(
                    name=name,
                    version=item.get("version", "0.0.0"),
                    description=item.get("description", ""),
                    keywords=item.get("keywords", []) or [],
                    publisher=item.get("publisher", {}).get("username", "")
                    if isinstance(item.get("publisher"), dict)
                    else "",
                    date=item.get("date", ""),
                    npm_url=links.get("npm", ""),
                    homepage=links.get("homepage", ""),
                    repository=links.get("repository", ""),
                )
                listings.append(listing)

            return listings

        except json.JSONDecodeError as e:
            logger.debug("[SkillMarket] npm search JSON parse error: %s", e)
            return []
        except subprocess.TimeoutExpired:
            logger.warning("[SkillMarket] npm search timed out")
            return []
        except FileNotFoundError:
            logger.error("[SkillMarket] npm CLI not found. Install Node.js/npm first.")
            return []
        except Exception as e:
            logger.exception("[SkillMarket] npm search error: %s", e)
            return []

    def _parse_view_result(self, package_name: str, raw: dict[str, Any]) -> SkillDetail:
        """npm view JSON 출력에서 SkillDetail 객체를 생성합니다.

        Args:
            package_name: 패키지 이름
            raw: npm view --json 출력 (딕셔너리)

        Returns:
            SkillDetail 객체
        """
        agk = raw.get("antigravityK", {}) or {}
        if not isinstance(agk, dict):
            agk = {}

        # 최신 버전 정보 (npm view는 여러 버전을 포함할 수 있음)
        version = raw.get("version", "0.0.0")
        if isinstance(version, dict):
            # 다중 버전인 경우 가장 최신 태그
            version = raw.get("dist-tags", {}).get("latest", "0.0.0")

        description = raw.get("description", "")
        if isinstance(description, dict):
            description = next(iter(description.values()), "")

        keywords = raw.get("keywords", []) or []
        if isinstance(keywords, str):
            keywords = [keywords]

        mcp = agk.get("mcp", {}) or {}
        if not isinstance(mcp, dict):
            mcp = {}

        return SkillDetail(
            name=package_name,
            version=str(version),
            description=str(description),
            keywords=list(keywords),
            raw_package_json=raw,
            # antigravityK 필드
            agk_skill=bool(agk.get("skill", False) or package_name.startswith(AGK_SKILL_SCOPE)),
            agk_display_name=str(agk.get("displayName", "")),
            agk_categories=list(agk.get("categories", []) or []),
            agk_min_agent_version=str(agk.get("minAgentVersion", "") or ""),
            agk_platforms=list(agk.get("platforms", []) or []),
            agk_required_tools=list(agk.get("requiredTools", []) or []),
            agk_optional_tools=list(agk.get("optionalTools", []) or []),
            agk_risk_level=str(agk.get("riskLevel", "medium") or "medium"),
            agk_trust_level=str(agk.get("trustLevel", "experimental") or "experimental"),
            agk_requires_approval=bool(agk.get("requiresApproval", False)),
            agk_auto_match_keywords=list(agk.get("autoMatchKeywords", []) or []),
            agk_mcp_server_id=str(mcp.get("serverId", "")),
            agk_mcp_transport=str(mcp.get("transport", "stdio")),
            # 공통 메타데이터
            license=str(raw.get("license", "") or ""),
            homepage=str(raw.get("homepage", "") or ""),
            repository=str(
                raw.get("repository", {}).get("url", "")
                if isinstance(raw.get("repository"), dict)
                else raw.get("repository", "")
            ),
            npm_url=f"https://www.npmjs.com/package/{package_name}",
            last_published=str(raw.get("time", {}).get(version, "")) if isinstance(raw.get("time"), dict) else "",
            readme_filename=str(raw.get("readmeFilename", "")),
            has_readme=bool(raw.get("readme")),
        )
