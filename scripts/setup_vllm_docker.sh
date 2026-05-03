#!/usr/bin/env bash
# ============================================================================
# Antigravity-K: vLLM Docker 기반 구동 설정 (대량 처리용)
# ============================================================================
# vLLM = 고성능 배치 추론 서버 (continuous batching, PagedAttention)
# Apple Silicon에서는 vllm-mlx 또는 vllm-metal 플러그인 사용
# ============================================================================

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'

log_info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
log_success() { echo -e "${GREEN}[✓]${NC} $*"; }
log_warn()    { echo -e "${YELLOW}[!]${NC} $*"; }
log_step()    { echo -e "\n${CYAN}━━━ $* ━━━${NC}"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# ─── Docker 확인 ─────────────────────────────────────────────────────────────
check_docker() {
    log_step "1. Docker 확인"

    if ! command -v docker &>/dev/null; then
        log_warn "Docker가 설치되어 있지 않습니다."
        log_info "Docker Desktop 설치: https://docs.docker.com/desktop/setup/install/mac-install/"
        exit 1
    fi

    if ! docker info &>/dev/null 2>&1; then
        log_warn "Docker Desktop이 실행되고 있지 않습니다."
        log_info "Docker Desktop을 먼저 시작해 주세요."
        exit 1
    fi

    log_success "Docker $(docker --version | awk '{print $3}' | tr -d ',')"
}

# ─── docker-compose 파일 생성 ────────────────────────────────────────────────
create_compose_file() {
    log_step "2. docker-compose.yml 생성"

    cat > "${PROJECT_DIR}/docker-compose.vllm.yml" << 'COMPOSE_EOF'
# ============================================================================
# Antigravity-K: vLLM 서버 Docker Compose
# ============================================================================
# 사용법:
#   docker compose -f docker-compose.vllm.yml up -d
#   docker compose -f docker-compose.vllm.yml logs -f
#   docker compose -f docker-compose.vllm.yml down
# ============================================================================

services:
  vllm-server:
    image: vllm/vllm-openai:latest
    container_name: agk-vllm
    ports:
      - "8000:8000"
    volumes:
      # 로컬 모델 캐시 마운트 (다운로드 시간 절약)
      - "${HOME}/.cache/huggingface:/root/.cache/huggingface"
      - "./models:/models"
    environment:
      # Apple Silicon Metal 가속 (vllm-metal 플러그인)
      - VLLM_WORKER_MULTIPROC_METHOD=spawn
    command: >
      --model /models/deepseek-r1-70b
      --host 0.0.0.0
      --port 8000
      --max-model-len 8192
      --dtype float16
      --trust-remote-code
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 80G  # 128GB 중 80GB 할당
COMPOSE_EOF

    log_success "docker-compose.vllm.yml 생성 완료"
}

# ─── vmlx 네이티브 설치 (Docker 대안) ────────────────────────────────────────
setup_vmlx_native() {
    log_step "3. vmlx 네이티브 설치 (Docker 대안, 추천)"

    log_info "vmlx는 Apple Silicon 네이티브 vLLM 대안입니다."
    log_info "Docker 없이 직접 Metal GPU를 활용합니다."
    echo ""

    # 가상환경이 활성화되어 있는지 확인
    if [[ -z "${VIRTUAL_ENV:-}" ]]; then
        if [[ -d "${PROJECT_DIR}/.venv" ]]; then
            # shellcheck disable=SC1091
            source "${PROJECT_DIR}/.venv/bin/activate"
        else
            log_warn ".venv를 먼저 setup_env.sh로 생성해 주세요."
            return
        fi
    fi

    log_info "vmlx 설치 중..."
    pip install vmlx --quiet 2>/dev/null || {
        log_info "vmlx가 PyPI에 없으면 GitHub에서 직접 설치합니다..."
        pip install git+https://github.com/nicholaschenai/vmlx.git --quiet 2>/dev/null || {
            log_warn "vmlx 설치 실패. mlx_lm.server로 대체합니다."
            return
        }
    }

    log_success "vmlx 설치 완료"

    echo ""
    log_info "사용법:"
    echo "  # vmlx로 모델 서빙 (OpenAI 호환)"
    echo "  vmlx serve --model mlx-community/DeepSeek-R1-0528-Qwen3-8B-MLX-4bit --port 8000"
    echo ""
    echo "  # mlx_lm.server 대안"
    echo "  mlx_lm.server --model mlx-community/Qwen2.5-Coder-32B-Instruct-4bit --port 8401"
}

# ─── LM Studio 가이드 ────────────────────────────────────────────────────────
lm_studio_guide() {
    log_step "4. LM Studio 설치 가이드"

    cat << 'GUIDE'

    ┌─────────────────────────────────────────────────────────┐
    │  LM Studio — GUI 기반 로컬 LLM 관리 (빠른 테스트용)     │
    ├─────────────────────────────────────────────────────────┤
    │                                                         │
    │  1. 다운로드: https://lmstudio.ai                       │
    │     → macOS Apple Silicon (ARM64) 버전 선택             │
    │                                                         │
    │  2. 설치 후 앱 실행                                     │
    │                                                         │
    │  3. 모델 검색 & 다운로드:                               │
    │     - "deepseek-r1" 검색 → GGUF 포맷 다운로드          │
    │     - "qwen2.5-coder" 검색 → 32B Q8_0 다운로드         │
    │     - "glm-5" 검색 → 사용 가능한 양자화 선택           │
    │                                                         │
    │  4. Local Server 탭 → Start Server                     │
    │     → 기본 포트: http://localhost:1234/v1               │
    │                                                         │
    │  5. API 테스트:                                         │
    │     curl http://localhost:1234/v1/models                │
    │                                                         │
    │  * LM Studio는 자체적으로 OpenAI 호환 API를 제공합니다  │
    │  * GGUF 포맷을 사용하며, MLX와는 별도 경로입니다       │
    └─────────────────────────────────────────────────────────┘

GUIDE
}

# ─── 완료 요약 ────────────────────────────────────────────────────────────────
print_summary() {
    log_step "추론 엔진 구성 완료"

    echo -e ""
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${NC}  추론 엔진 API 엔드포인트 정리                           ${CYAN}║${NC}"
    echo -e "${CYAN}╠══════════════════════════════════════════════════════════╣${NC}"
    echo -e "${CYAN}║${NC}                                                          ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}  mlx_lm.server  → ${YELLOW}http://localhost:8401/v1${NC}              ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}  Ollama         → ${YELLOW}http://localhost:11434/v1${NC}             ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}  vLLM (Docker)  → ${YELLOW}http://localhost:8000/v1${NC}              ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}  LM Studio      → ${YELLOW}http://localhost:1234/v1${NC}              ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}                                                          ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}  통합 프록시    → ${GREEN}http://localhost:1234/v1${NC}              ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}  (api_forwarder.py 실행 시)                              ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}                                                          ${CYAN}║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════╝${NC}"
    echo -e ""
}

# ─── 메인 ─────────────────────────────────────────────────────────────────────
main() {
    echo -e "\n${CYAN}Antigravity-K — vLLM / vmlx / LM Studio 설치 & 구성${NC}\n"

    check_docker
    create_compose_file
    setup_vmlx_native
    lm_studio_guide
    print_summary
}

main "$@"
