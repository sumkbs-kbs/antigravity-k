"""
Antigravity-K: 전역 설정 (Config)
===================================
모든 설정은 환경변수 또는 config.yaml에서 로드됩니다.
Apple Silicon M5 Max (128GB) 기준 기본값이 설정되어 있습니다.
"""

from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field, model_validator, ConfigDict
import os


# 프로젝트 루트 경로 자동 감지
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


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
        description="구동 엔진 선택 (ollama, lm_studio)",
    )

    # 로컬/외부 OpenAI 호환 API 주소 (LM Studio, Ollama, vLLM 등)
    api_base: str = Field(
        default="",  # 엔진에 따라 자동 설정됨
        description="로컬/원격 호환 API 베이스 주소 (예: http://localhost:11434/v1)",
    )
    api_key: str = Field(
        default="",  # 엔진에 따라 자동 설정됨
        description="API 키",
    )
    force_api: bool = Field(
        default=True,
        description="MLX 대신 무조건 로컬 API(LM Studio 등)를 사용할지 여부",
    )

    @model_validator(mode="after")
    def set_defaults_by_engine(self):
        engine = self.api_engine.lower()
        if not self.api_base:
            if engine == "ollama":
                self.api_base = "http://localhost:11434/v1"
            elif engine == "lm_studio":
                self.api_base = "http://localhost:1234/v1"
            else:
                self.api_base = "http://localhost:11434/v1"  # fallback
        if not self.api_key:
            if engine == "ollama":
                self.api_key = "ollama"
            elif engine == "lm_studio":
                self.api_key = "lm-studio"
            else:
                self.api_key = "none"
        return self

    # KV 캐시 양자화 (메모리 절약)
    kv_cache_bits: int = Field(default=8, description="KV 캐시 양자화 비트")
    kv_cache_group_size: int = Field(default=64, description="KV 캐시 그룹 크기")

    # 생성 설정
    max_tokens: int = Field(default=4096, description="최대 생성 토큰 수")
    temperature: float = Field(default=0.7, description="생성 온도")
    top_p: float = Field(default=0.9, description="top-p 샘플링")

    model_config = ConfigDict(env_prefix="AGK_MODEL_")


class ServerConfig(BaseSettings):
    """API 서버 설정."""

    host: str = Field(default="127.0.0.1", description="바인딩 호스트")
    port: int = Field(default=8400, description="API 서버 포트")
    inference_port: int = Field(default=8401, description="추론 엔진 포트")

    model_config = ConfigDict(env_prefix="AGK_SERVER_")


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

    model_config = ConfigDict(env_prefix="AGK_PATH_")


class SecurityConfig(BaseSettings):
    """보안 설정."""

    sandbox_enabled: bool = Field(default=True, description="Docker 샌드박스 활성화")
    sandbox_network: str = Field(default="none", description="샌드박스 네트워크 모드")
    max_execution_time: int = Field(default=30, description="명령 실행 타임아웃(초)")
    audit_log_enabled: bool = Field(default=True, description="감사 로그 활성화")
    max_tool_risk: str = Field(
        # P2 수정: 환경 프로파일 분리 — production에서는 medium이 기본
        default=(
            "medium"
            if os.environ.get("AGK_ENV", "development") == "production"
            else "high"
        ),
        description="자동 승인 없이 사용 가능한 최대 도구 위험도 (safe/low/medium/high/critical)",
    )
    # 추가: LintAI strict 모드 플래그
    lintai_strict: bool = Field(
        default=os.environ.get("AGK_ENV", "development") == "production",
        description="프로덕션 환경에서 LintAI 미설치 시 Fail-Closed 적용",
    )

    model_config = ConfigDict(env_prefix="AGK_SEC_")


class WorkflowConfig(BaseSettings):
    """자율 진행 워크플로우 설정."""

    autopilot: bool = Field(default=False, description="자율 진행 모드")
    auto_commit: bool = Field(default=False, description="자동 Git 커밋 활성화")
    auto_artifacts: bool = Field(default=False, description="산출물 자동 생성")

    model_config = ConfigDict(env_prefix="AGK_WORKFLOW_")


class I18nConfig(BaseSettings):
    """다국어(i18n) 설정."""

    locale: str = Field(default="auto", description="언어 설정 (auto/ko/en/ja)")
    fallback_locale: str = Field(default="en", description="폴백 언어")

    model_config = ConfigDict(env_prefix="AGK_I18N_")


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
    usage_db_path: str = Field(
        default="", description="사용량 DB 경로 (빈 문자열=자동)"
    )

    model_config = ConfigDict(env_prefix="AGK_ROUTER_")


class ComputerUseConfig(BaseSettings):
    """데스크탑 자동화 (Computer Use) 설정."""

    enabled: bool = Field(default=True, description="Computer Use 기능 활성화")
    hitl_required: bool = Field(
        default=True, description="위험 액션 시 사용자 승인 필요"
    )
    force_stub: bool = Field(
        default=False, description="테스트용 Stub 드라이버 강제 사용"
    )
    screenshot_dir: Path = Field(
        default=PROJECT_ROOT / "data" / "screenshots",
        description="스크린샷 저장 디렉토리",
    )
    audit_log_path: Path = Field(
        default=PROJECT_ROOT / "logs" / "computer_use_audit.jsonl",
        description="액션 감사 로그 파일 경로",
    )

    model_config = ConfigDict(env_prefix="AGK_CU_")


class AppConfig:
    """전체 애플리케이션 설정을 통합합니다."""

    def __init__(self):
        self.model = ModelConfig()
        self.server = ServerConfig()
        self.paths = PathConfig()
        self.security = SecurityConfig()
        self.workflow = WorkflowConfig()
        self.i18n = I18nConfig()
        self.router = RouterConfig()
        self.computer_use = ComputerUseConfig()

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
