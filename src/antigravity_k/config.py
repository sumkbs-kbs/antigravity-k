"""Antigravity-K: 전역 설정 (Config).

===================================
모든 설정은 환경변수 또는 config.yaml에서 로드됩니다.
Apple Silicon M5 Max (128GB) 기준 기본값이 설정되어 있습니다.
"""

import logging
import os
from pathlib import Path

import yaml
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# 프로젝트 루트 경로 자동 감지
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# 모듈 레벨 로거 (config 검증 및 .env 로드 메시지용)
logger = logging.getLogger("antigravity_k.config")


def _load_dotenv_once() -> None:
    """프로젝트 루트의 .env 파일을 환경변수로 로드합니다.

    python-dotenv가 설치되어 있으면 사용하고, 없으면 경량 파서로 폴백합니다.
    이미 환경변수에 설정된 값은 덮어쓰지 않습니다(override=False).
    모든 엔트리포인트(CLI, 직접 실행, 서버)에서 API 키를 일관되게 로드하기 위해
    config 모듈 로드 시점에 한 번만 실행됩니다.
    """
    env_path = Path(os.environ.get("AGK_ENV_FILE", PROJECT_ROOT / ".env"))
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path, override=False)
        return
    except ImportError:
        logger.debug("python-dotenv 미설치 — 경량 폴백 파서 사용")

    # 경량 폴백 파서 — python-dotenv 미설치 환경 지원
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("\"'")
            if key and key not in os.environ:
                os.environ[key] = value
    except OSError:
        logger.warning(".env 파일 읽기 실패 (non-critical)", exc_info=True)


# config 모듈 import 시점에 .env를 로드 — server.py의 load_dotenv()보다 먼저 실행됨
_load_dotenv_once()


def _load_yaml_config() -> dict:
    """Load repository config.yaml when present; environment variables still win."""
    config_path = Path(os.environ.get("AGK_CONFIG_FILE", PROJECT_ROOT / "config.yaml"))
    if not config_path.exists():
        return {}
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def _section_overrides(raw_config: dict, section: str, config_cls: type[BaseSettings]) -> dict:
    section_data = raw_config.get(section, {})
    if not isinstance(section_data, dict):
        return {}

    env_prefix = config_cls.model_config.get("env_prefix", "")
    overrides = {}
    for key, value in section_data.items():
        if key not in config_cls.model_fields:
            continue
        env_name = f"{env_prefix}{key}".upper()
        if env_name in os.environ:
            continue
        overrides[key] = value
    return overrides


class ModelConfig(BaseSettings):
    """LLM 모델 관련 설정."""

    # 메인 추론 모델 (70B급)
    main_model: str = Field(
        default="mlx-community/Qwen3-72B-4bit",
        description="메인 추론 모델 (HuggingFace repo 또는 로컬 경로)",
    )

    # 코딩 전용 모델
    code_model: str = Field(
        default="mlx-community/Qwen2.5-Coder-32B-Instruct-4bit",
        description="코드 생성 전용 모델",
    )

    # 임베딩 모델
    embedding_model: str = Field(
        default="mlx-community/bge-m3-4bit",
        description="문서 임베딩 모델",
    )

    # 비전 모델
    vision_model: str = Field(
        default="mlx-community/Qwen2-VL-7B-Instruct-4bit",
        description="이미지 분석 모델",
    )

    # 구동 엔진 선택 (ollama, lm_studio 등)
    api_engine: str = Field(
        default="ollama",
        description="구동 엔진 선택 (ollama, lm_studio, openrouter)",
    )

    # 로컬/외부 OpenAI 호환 API 주소 (LM Studio, Ollama, vLLM, OpenRouter 등)
    api_base: str = Field(
        default="",  # 엔진에 따라 자동 설정됨
        description="로컬/원격 호환 API 베이스 주소 (예: http://localhost:11434/v1)",
    )
    api_key: str = Field(
        default="",  # 엔진에 따라 자동 설정됨
        description="API 키 (OpenRouter의 경우 AGK_API_KEY 또는 OPENROUTER_API_KEY 환경변수)",
    )
    force_api: bool = Field(
        default=True,
        description="MLX 대신 무조건 로컬 API(LM Studio 등)를 사용할지 여부",
    )

    @model_validator(mode="after")
    def set_defaults_by_engine(self):
        """Set defaults by engine.

        엔진(openrouter/ollama/lm_studio)에 따라 api_base, api_key 기본값을 설정합니다.
        API 키는 다음 순서로 해석합니다 (env_prefix와 무관하게 널리 쓰이는 변수명들을 인식):
          OpenRouter: OPENROUTER_API_KEY → AGK_OPENROUTER_KEY → AGK_API_KEY
          Ollama:    "ollama" (또는 OLLAMA_API_KEY가 있으면 사용)
        """
        engine = self.api_engine.lower()

        # ─── .env에서 provider/engine을 덮어쓰기 위해 환경변수 인식 ───
        # AGK_PROVIDER / AGK_MODEL_API_ENGINE / AGK_API_ENGINE 모두 허용
        env_provider = (
            os.environ.get("AGK_PROVIDER") or os.environ.get("AGK_API_ENGINE") or os.environ.get("AGK_MODEL_API_ENGINE")
        )
        if env_provider:
            engine = env_provider.lower()
            self.api_engine = engine

        if not self.api_base:
            if engine == "ollama":
                self.api_base = "http://localhost:11434/v1"
            elif engine == "lm_studio":
                self.api_base = "http://localhost:1234/v1"
            elif engine == "openrouter":
                self.api_base = "https://openrouter.ai/api/v1"
            elif engine == "openai":
                self.api_base = "https://api.openai.com/v1"
            elif engine == "gemini":
                self.api_base = "https://generativelanguage.googleapis.com/v1beta/openai"
            elif engine == "zai":
                self.api_base = "https://open.bigmodel.cn/api/paas/v4"
            elif engine == "nim":
                self.api_base = "https://integrate.api.nvidia.com/v1"
            else:
                self.api_base = "http://localhost:11434/v1"  # fallback

        if not self.api_key or self.api_key == "none":
            if engine == "ollama":
                self.api_key = os.environ.get("OLLAMA_API_KEY", "") or "ollama"
            elif engine == "lm_studio":
                self.api_key = "lm-studio"
            elif engine == "openrouter":
                # OPENROUTER_API_KEY → AGK_OPENROUTER_KEY → AGK_API_KEY → OPENAI_API_KEY 순서
                self.api_key = (
                    os.environ.get("OPENROUTER_API_KEY")
                    or os.environ.get("AGK_OPENROUTER_KEY")
                    or os.environ.get("AGK_API_KEY")
                    or os.environ.get("OPENAI_API_KEY", "")
                )
            elif engine == "openai":
                self.api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("AGK_OPENAI_KEY", "")
            elif engine == "gemini":
                self.api_key = os.environ.get("GEMINI_API_KEY", "")
            elif engine == "zai":
                self.api_key = os.environ.get("ZAI_API_KEY", "")
            elif engine == "nim":
                self.api_key = os.environ.get("NVIDIA_API_KEY", "")
            else:
                self.api_key = os.environ.get("AGK_API_KEY", "") or "none"

        # OpenRouter 사용 시 키 누락 경고 (설정 검증 강화)
        if engine == "openrouter" and (not self.api_key or self.api_key == "none"):
            import logging

            logging.getLogger("antigravity_k.config").warning(
                "OpenRouter 엔진이 선택되었지만 API 키가 설정되지 않았습니다. "
                "OPENROUTER_API_KEY, AGK_OPENROUTER_KEY 또는 AGK_API_KEY 환경변수를 확인하세요.",
            )

        return self

    # KV 캐시 양자화 (메모리 절약)
    kv_cache_bits: int = Field(default=8, description="KV 캐시 양자화 비트")
    kv_cache_group_size: int = Field(default=64, description="KV 캐시 그룹 크기")

    # 생성 설정
    max_tokens: int = Field(default=4096, description="최대 생성 토큰 수")
    temperature: float = Field(default=0.7, description="생성 온도")
    top_p: float = Field(default=0.9, description="top-p 샘플링")

    model_config = SettingsConfigDict(env_prefix="AGK_MODEL_")


class ServerConfig(BaseSettings):
    """API 서버 설정."""

    host: str = Field(default="127.0.0.1", description="바인딩 호스트")
    port: int = Field(default=8400, description="API 서버 포트")
    inference_port: int = Field(default=8401, description="추론 엔진 포트")

    model_config = SettingsConfigDict(env_prefix="AGK_SERVER_")


class PathConfig(BaseSettings):
    """경로 설정."""

    project_root: Path = Field(default=PROJECT_ROOT)
    models_dir: Path = Field(default=PROJECT_ROOT / "models")
    data_dir: Path = Field(default=PROJECT_ROOT / "data")
    documents_dir: Path = Field(default=PROJECT_ROOT / "data" / "documents")
    vectors_dir: Path = Field(default=PROJECT_ROOT / "data" / "vectors")
    logs_dir: Path = Field(default=PROJECT_ROOT / "logs")
    wiki_dir: Path = Field(
        default=PROJECT_ROOT / "data" / "wiki_entries",
        description="마크다운 위키 저장 경로",
    )

    model_config = SettingsConfigDict(env_prefix="AGK_PATH_")


class SecurityConfig(BaseSettings):
    """보안 설정."""

    sandbox_enabled: bool = Field(default=True, description="Docker 샌드박스 활성화")
    sandbox_network: str = Field(default="none", description="샌드박스 네트워크 모드")
    max_execution_time: int = Field(default=30, description="명령 실행 타임아웃(초)")
    audit_log_enabled: bool = Field(default=True, description="감사 로그 활성화")
    max_tool_risk: str = Field(
        # P2 수정: 환경 프로파일 분리 — production에서는 medium이 기본
        default=("medium" if os.environ.get("AGK_ENV", "development") == "production" else "high"),
        description="자동 승인 없이 사용 가능한 최대 도구 위험도 (safe/low/medium/high/critical)",
    )
    # 추가: LintAI strict 모드 플래그
    lintai_strict: bool = Field(
        default=os.environ.get("AGK_ENV", "development") == "production",
        description="프로덕션 환경에서 LintAI 미설치 시 Fail-Closed 적용",
    )
    # 추가: 외부 접속 보호용 PIN
    access_pin: str = Field(
        default="0000",
        description="외부(또는 로컬) 프론트엔드 접속용 보안 PIN (부트스트랩용; 해시화 후 auth_hash_file에 저장)",
    )
    # 인증 토큰 수명(시간)
    token_ttl_hours: int = Field(
        default=12,
        description="발급된 액세스 토큰의 수명(시간)",
    )
    # PIN 무차별 대입 방지용 로그인 레이트리밋
    login_rate_limit: str = Field(
        default="5/minute",
        description="/api/auth/login 엔드포인트의 레이트리밋 (PIN 무차별 대입 방지)",
    )
    # PIN 해시 저장 파일 경로
    pin_hash_file: str = Field(
        default="data/auth_hash",
        description="PIN 해시가 저장되는 파일 경로",
    )
    # JWT 서명 비밀키 저장 파일 경로
    token_secret_file: str = Field(
        default="data/token_secret",
        description="JWT 서명 비밀키가 저장되는 파일 경로",
    )

    model_config = SettingsConfigDict(env_prefix="AGK_SEC_")


class WorkflowConfig(BaseSettings):
    """자율 진행 워크플로우 설정."""

    autopilot: bool = Field(default=False, description="자율 진행 모드")
    auto_commit: bool = Field(default=False, description="자동 Git 커밋 활성화")
    auto_artifacts: bool = Field(default=False, description="산출물 자동 생성")

    model_config = SettingsConfigDict(env_prefix="AGK_WORKFLOW_")


class I18nConfig(BaseSettings):
    """다국어(i18n) 설정."""

    locale: str = Field(default="auto", description="언어 설정 (auto/ko/en/ja)")
    fallback_locale: str = Field(default="en", description="폴백 언어")

    model_config = SettingsConfigDict(env_prefix="AGK_I18N_")


class RouterConfig(BaseSettings):
    """모델 라우터 설정 (9Router 패턴)."""

    default_strategy: str = Field(
        default="fallback",
        description="기본 라우팅 전략 (fallback/round-robin/load-balance)",
    )
    cooldown_base_sec: int = Field(default=60, description="폴백 쿨다운 기본값(초)")
    max_cooldown_sec: int = Field(default=3600, description="최대 쿨다운(초)")
    max_retries: int = Field(default=3, description="최대 재시도 횟수")
    usage_tracking: bool = Field(default=True, description="사용량 추적 활성화")
    usage_db_path: str = Field(default="", description="사용량 DB 경로 (빈 문자열=자동)")

    model_config = SettingsConfigDict(env_prefix="AGK_ROUTER_")


class ComputerUseConfig(BaseSettings):
    """데스크탑 자동화 (Computer Use) 설정."""

    enabled: bool = Field(default=True, description="Computer Use 기능 활성화")
    hitl_required: bool = Field(default=True, description="위험 액션 시 사용자 승인 필요")
    force_stub: bool = Field(default=False, description="테스트용 Stub 드라이버 강제 사용")
    screenshot_dir: Path = Field(
        default=PROJECT_ROOT / "data" / "screenshots",
        description="스크린샷 저장 디렉토리",
    )
    audit_log_path: Path = Field(
        default=PROJECT_ROOT / "logs" / "computer_use_audit.jsonl",
        description="액션 감사 로그 파일 경로",
    )

    model_config = SettingsConfigDict(env_prefix="AGK_CU_")


class AppConfig:
    """전체 애플리케이션 설정을 통합합니다."""

    def __init__(self):
        """Initialize the AppConfig."""
        raw_config = _load_yaml_config()
        self._raw = raw_config
        self.model = ModelConfig(**_section_overrides(raw_config, "model", ModelConfig))
        self.server = ServerConfig(**_section_overrides(raw_config, "server", ServerConfig))
        self.paths = PathConfig(**_section_overrides(raw_config, "paths", PathConfig))
        self.security = SecurityConfig(**_section_overrides(raw_config, "security", SecurityConfig))
        self.workflow = WorkflowConfig(**_section_overrides(raw_config, "workflow", WorkflowConfig))
        self.i18n = I18nConfig(**_section_overrides(raw_config, "i18n", I18nConfig))
        self.router = RouterConfig(**_section_overrides(raw_config, "router", RouterConfig))
        self.computer_use = ComputerUseConfig(
            **_section_overrides(raw_config, "computer_use", ComputerUseConfig),
        )

    def ensure_directories(self):
        """필요한 디렉토리를 생성합니다."""
        for path in [
            self.paths.models_dir,
            self.paths.data_dir,
            self.paths.documents_dir,
            self.paths.vectors_dir,
            self.paths.logs_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)

    def validate(self) -> list[str]:
        """시작 시 설정을 검증하고 문제 목록을 반환합니다 (fail-fast, 작업 D).

        빈 리스트 = 문제 없음. 문제가 있으면 서버 시작 전에 로깅/표시하여
        "왜 안 되지?" 디버깅 시간을 줄입니다.

        검증 항목:
          - API 엔진별 필수 API 키 존재 여부
          - 핵심 디렉토리 쓰기 권한
          - 모델 레지스트리 로드 가능 여부
          - 포트 충돌 위험 (포트가 0 이하인지)
          - 비용 예산 양수 여부
        """
        problems: list[str] = []
        log = logging.getLogger("antigravity_k.config")

        # 1. API 엔진별 필수 키
        engine = (self.model.api_engine or "").lower()
        if engine == "openrouter":
            if not self.model.api_key or self.model.api_key == "none":
                problems.append(
                    "OpenRouter 엔진이 선택되었지만 API 키가 없습니다. "
                    "OPENROUTER_API_KEY, AGK_OPENROUTER_KEY 또는 AGK_API_KEY 환경변수를 설정하세요."
                )
        elif engine == "nim" or engine == "nvidia":
            if not os.environ.get("NVIDIA_API_KEY"):
                problems.append(
                    "NIM 엔진이 선택되었지만 NVIDIA_API_KEY가 없습니다. "
                    "build.nvidia.com에서 무료 키를 발급받아 설정하세요."
                )

        # 2. 포트 유효성
        if self.server.port <= 0 or self.server.port > 65535:
            problems.append(f"잘못된 서버 포트: {self.server.port} (1-65535 범위여야 함)")
        if self.server.inference_port <= 0 or self.server.inference_port > 65535:
            problems.append(f"잘못된 추론 포트: {self.server.inference_port}")

        # 3. 핵심 디렉토리 쓰기 권한
        for label, path in [
            ("data_dir", self.paths.data_dir),
            ("logs_dir", self.paths.logs_dir),
        ]:
            try:
                path.mkdir(parents=True, exist_ok=True)
                test_file = path / ".agk_write_test"
                test_file.write_text("test", encoding="utf-8")
                test_file.unlink()
            except OSError as e:
                problems.append(f"{label}({path})에 쓰기 권한이 없습니다: {e}")

        # 4. config.yaml 모델 레지스트리 로드 확인
        try:
            from antigravity_k.engine.model_registry import ModelRegistry

            registry = ModelRegistry()
            if not registry.list_models():
                problems.append("config.yaml에 등록된 모델이 없습니다.")
        except Exception as e:
            problems.append(f"모델 레지스트리 로드 실패: {e}")

        # 5. 비용 예산 양수
        raw = getattr(self, "_raw", {})
        cost_cfg = raw.get("cost", {}) if isinstance(raw, dict) else {}
        budget = float(cost_cfg.get("daily_budget_usd", 50.0))
        if budget <= 0:
            problems.append(f"일일 비용 예산이 {budget}입니다 (양수여야 함)")

        if problems:
            log.warning("설정 검증 %d개 문제 발견:", len(problems))
            for p in problems:
                log.warning("  - %s", p)
        else:
            log.info("설정 검증 통과: 문제 없음")

        return problems

    def summary(self) -> str:
        """설정 요약을 문자열로 반환합니다."""
        return (
            f"=== Antigravity-K Config ===\n"
            f"메인 모델    : {self.model.main_model}\n"
            f"코드 모델    : {self.model.code_model}\n"
            f"임베딩 모델  : {self.model.embedding_model}\n"
            f"비전 모델    : {self.model.vision_model}\n"
            f"로컬 API Base: {self.model.api_base}\n"
            f"API 서버     : {self.server.host}:{self.server.port}\n"
            f"추론 서버    : {self.server.host}:{self.server.inference_port}\n"
            f"프로젝트 루트: {self.paths.project_root}\n"
            f"샌드박스     : {'활성' if self.security.sandbox_enabled else '비활성'}\n"
            f"도구 위험 한도: {self.security.max_tool_risk}\n"
            f"언어         : {self.i18n.locale}\n"
            f"Autopilot    : {'활성' if self.workflow.autopilot else '비활성'}\n"
            f"Computer Use : {'활성' if self.computer_use.enabled else '비활성'}"
            f" (HITL={'필수' if self.computer_use.hitl_required else '선택'})\n"
            f"라우터 전략  : {self.router.default_strategy}\n"
            f"사용량 추적  : {'활성' if self.router.usage_tracking else '비활성'}\n"
        )


# 싱글턴 인스턴스
config = AppConfig()
