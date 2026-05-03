#!/usr/bin/env bash
# ============================================================================
# Antigravity-K: M5 Max 개발 환경 자동 설정 스크립트
# ============================================================================
# 대상: macOS Apple Silicon (M5 Max, 128GB Unified Memory)
# 용도: 완전 로컬 AI 에이전트 환경 구축
# 사용법: chmod +x setup_env.sh && ./setup_env.sh
# ============================================================================

set -euo pipefail

# ─── 색상 정의 ────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ─── 유틸리티 함수 ────────────────────────────────────────────────────────────
log_info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
log_success() { echo -e "${GREEN}[✓]${NC} $*"; }
log_warn()    { echo -e "${YELLOW}[!]${NC} $*"; }
log_error()   { echo -e "${RED}[✗]${NC} $*"; }
log_step()    { echo -e "\n${CYAN}━━━ $* ━━━${NC}"; }

# ─── 사전 조건 확인 ───────────────────────────────────────────────────────────
check_prerequisites() {
    log_step "사전 조건 확인"

    # macOS 확인
    if [[ "$(uname)" != "Darwin" ]]; then
        log_error "이 스크립트는 macOS 전용입니다."
        exit 1
    fi
    log_success "macOS 감지됨"

    # Apple Silicon 확인
    if [[ "$(uname -m)" != "arm64" ]]; then
        log_error "Apple Silicon (ARM64)이 필요합니다. 현재: $(uname -m)"
        exit 1
    fi
    log_success "Apple Silicon (ARM64) 확인"

    # 칩셋 정보 출력
    local chip_info
    chip_info=$(sysctl -n machdep.cpu.brand_string 2>/dev/null || echo "Unknown")
    log_info "칩셋: ${chip_info}"

    # 메모리 확인
    local total_mem_gb
    total_mem_gb=$(( $(sysctl -n hw.memsize) / 1073741824 ))
    log_info "메모리: ${total_mem_gb}GB Unified Memory"

    if [[ ${total_mem_gb} -lt 32 ]]; then
        log_warn "32GB 미만입니다. 대형 모델(70B+)은 메모리 부족이 발생할 수 있습니다."
    else
        log_success "메모리 충분 (${total_mem_gb}GB)"
    fi

    # Xcode Command Line Tools 확인
    if ! xcode-select -p &>/dev/null; then
        log_warn "Xcode Command Line Tools 미설치. 설치를 시작합니다..."
        xcode-select --install
        log_info "설치 완료 후 이 스크립트를 다시 실행해 주세요."
        exit 0
    fi
    log_success "Xcode Command Line Tools 확인"
}

# ─── Homebrew 설치/업데이트 ───────────────────────────────────────────────────
setup_homebrew() {
    log_step "Homebrew 설치/업데이트"

    if ! command -v brew &>/dev/null; then
        log_info "Homebrew를 설치합니다..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

        # ARM64 Homebrew PATH 설정
        eval "$(/opt/homebrew/bin/brew shellenv)"

        # 쉘 프로필에 추가
        local shell_profile
        if [[ -n "${ZSH_VERSION:-}" ]]; then
            shell_profile="$HOME/.zshrc"
        else
            shell_profile="$HOME/.bash_profile"
        fi

        if ! grep -q '/opt/homebrew/bin/brew shellenv' "$shell_profile" 2>/dev/null; then
            echo '' >> "$shell_profile"
            echo '# Homebrew (Apple Silicon)' >> "$shell_profile"
            echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> "$shell_profile"
            log_info "Homebrew PATH를 ${shell_profile}에 추가했습니다."
        fi
    else
        log_info "Homebrew 업데이트 중..."
        brew update
    fi
    log_success "Homebrew $(brew --version | head -1)"
}

# ─── Python 3.12+ 설치 ───────────────────────────────────────────────────────
setup_python() {
    log_step "Python 3.12+ 설치"

    # Homebrew로 Python 3.12 설치
    if ! brew list python@3.12 &>/dev/null; then
        log_info "Python 3.12를 설치합니다..."
        brew install python@3.12
    fi

    # python3 버전 확인
    local py_version
    py_version=$(python3 --version 2>/dev/null | awk '{print $2}')
    local py_major py_minor
    py_major=$(echo "$py_version" | cut -d. -f1)
    py_minor=$(echo "$py_version" | cut -d. -f2)

    if [[ "$py_major" -lt 3 ]] || [[ "$py_major" -eq 3 && "$py_minor" -lt 12 ]]; then
        log_warn "Python ${py_version} 감지. 3.12+가 필요합니다."
        log_info "Homebrew Python 3.12를 기본으로 설정합니다..."
        brew link python@3.12 --force --overwrite 2>/dev/null || true
    fi

    log_success "Python $(python3 --version)"
}

# ─── Node.js 22+ 설치 ────────────────────────────────────────────────────────
setup_nodejs() {
    log_step "Node.js 22+ 설치"

    if ! command -v node &>/dev/null; then
        log_info "Node.js를 설치합니다..."
        brew install node@22
        brew link node@22 --force --overwrite 2>/dev/null || true
    else
        local node_major
        node_major=$(node --version | sed 's/v//' | cut -d. -f1)
        if [[ "$node_major" -lt 22 ]]; then
            log_info "Node.js v${node_major} → v22+ 업그레이드..."
            brew install node@22
            brew link node@22 --force --overwrite 2>/dev/null || true
        fi
    fi

    log_success "Node.js $(node --version)"
    log_success "npm $(npm --version)"
}

# ─── Docker Desktop 확인 ─────────────────────────────────────────────────────
setup_docker() {
    log_step "Docker Desktop 확인"

    if ! command -v docker &>/dev/null; then
        log_warn "Docker Desktop이 설치되어 있지 않습니다."
        log_info "Phase 6 (샌드박스)에서 필요합니다."
        log_info "설치 링크: https://docs.docker.com/desktop/setup/install/mac-install/"
        log_info "지금은 건너뜁니다. (Phase 1에서는 불필요)"
    else
        if docker info &>/dev/null 2>&1; then
            log_success "Docker $(docker --version | awk '{print $3}' | tr -d ',')"
        else
            log_warn "Docker가 설치되었지만 실행 중이 아닙니다. Docker Desktop을 시작해 주세요."
        fi
    fi
}

# ─── 프로젝트 디렉토리 & 가상환경 ────────────────────────────────────────────
setup_project() {
    log_step "프로젝트 디렉토리 및 가상환경 설정"

    # 프로젝트 루트 (스크립트가 있는 위치)
    local PROJECT_DIR
    PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    cd "$PROJECT_DIR"
    log_info "프로젝트 경로: ${PROJECT_DIR}"

    # 가상환경 생성
    local VENV_DIR="${PROJECT_DIR}/.venv"
    if [[ ! -d "$VENV_DIR" ]]; then
        log_info "Python 가상환경을 생성합니다..."
        python3 -m venv "$VENV_DIR"
        log_success "가상환경 생성: ${VENV_DIR}"
    else
        log_success "가상환경 이미 존재: ${VENV_DIR}"
    fi

    # 가상환경 활성화
    # shellcheck disable=SC1091
    source "${VENV_DIR}/bin/activate"
    log_success "가상환경 활성화 완료"

    # pip 업그레이드
    log_info "pip 업그레이드 중..."
    pip install --upgrade pip --quiet

    # 핵심 패키지 설치
    log_info "핵심 패키지 설치 중... (첫 실행 시 수 분 소요)"
    if [[ -f "${PROJECT_DIR}/requirements.txt" ]]; then
        pip install -r "${PROJECT_DIR}/requirements.txt" --quiet
        log_success "requirements.txt 패키지 설치 완료"
    else
        log_error "requirements.txt를 찾을 수 없습니다."
        exit 1
    fi
}

# ─── MLX 설치 검증 ────────────────────────────────────────────────────────────
verify_mlx_install() {
    log_step "MLX 설치 검증"

    python3 -c "
import sys

# MLX 코어
try:
    import mlx.core as mx
    print(f'  mlx        : {mx.__version__}  ✓')
except ImportError:
    print('  mlx        : NOT FOUND  ✗')
    sys.exit(1)

# MLX-LM
try:
    import mlx_lm
    ver = getattr(mlx_lm, '__version__', 'installed')
    print(f'  mlx-lm     : {ver}  ✓')
except ImportError:
    print('  mlx-lm     : NOT FOUND  ✗')

# MLX-VLM
try:
    import mlx_vlm
    ver = getattr(mlx_vlm, '__version__', 'installed')
    print(f'  mlx-vlm    : {ver}  ✓')
except ImportError:
    print('  mlx-vlm    : NOT FOUND  ✗')

# ChromaDB
try:
    import chromadb
    print(f'  chromadb   : {chromadb.__version__}  ✓')
except ImportError:
    print('  chromadb   : NOT FOUND  ✗')

# FastAPI
try:
    import fastapi
    print(f'  fastapi    : {fastapi.__version__}  ✓')
except ImportError:
    print('  fastapi    : NOT FOUND  ✗')

# Metal GPU 확인
try:
    default_device = mx.default_device()
    print(f'  기본 디바이스: {default_device}')
    if 'gpu' in str(default_device).lower():
        print('  Metal GPU : 활성화 ✓')
    else:
        print('  Metal GPU : 비활성 (CPU 모드)')
except Exception as e:
    print(f'  디바이스 확인 실패: {e}')
"

    if [[ $? -eq 0 ]]; then
        log_success "MLX 설치 검증 완료"
    else
        log_error "MLX 설치에 문제가 있습니다."
        exit 1
    fi
}

# ─── 디렉토리 구조 생성 ──────────────────────────────────────────────────────
create_directory_structure() {
    log_step "프로젝트 디렉토리 구조 생성"

    local PROJECT_DIR
    PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    local dirs=(
        "src/antigravity_k"
        "src/antigravity_k/engine"
        "src/antigravity_k/rag"
        "src/antigravity_k/agent"
        "src/antigravity_k/vision"
        "src/antigravity_k/security"
        "src/antigravity_k/tools"
        "models"
        "data/documents"
        "data/vectors"
        "logs"
        "tests"
        "scripts"
        "dashboard"
    )

    for dir in "${dirs[@]}"; do
        mkdir -p "${PROJECT_DIR}/${dir}"
    done

    # __init__.py 파일 생성
    find "${PROJECT_DIR}/src" -type d -exec sh -c '
        if [ ! -f "$1/__init__.py" ]; then
            touch "$1/__init__.py"
        fi
    ' _ {} \;

    log_success "디렉토리 구조 생성 완료"
}

# ─── 완료 요약 ────────────────────────────────────────────────────────────────
print_summary() {
    log_step "설치 완료 요약"

    echo -e ""
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${NC}  ${GREEN}Antigravity-K 환경 설정 완료!${NC}                          ${CYAN}║${NC}"
    echo -e "${CYAN}╠══════════════════════════════════════════════════════════╣${NC}"
    echo -e "${CYAN}║${NC}                                                          ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}  다음 단계:                                              ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}                                                          ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}  1. 가상환경 활성화:                                     ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}     ${YELLOW}source .venv/bin/activate${NC}                              ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}                                                          ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}  2. MLX 벤치마크 실행:                                   ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}     ${YELLOW}python verify_mlx.py${NC}                                   ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}                                                          ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}  3. Phase 1-2 진행 준비 완료                             ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}                                                          ${CYAN}║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════╝${NC}"
    echo -e ""
}

# ─── 메인 실행 ────────────────────────────────────────────────────────────────
main() {
    echo -e ""
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${NC}  ${GREEN}Antigravity-K${NC} — Local Engine for SHI                    ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}  M5 Max (128GB) 개발 환경 설정                            ${CYAN}║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════╝${NC}"
    echo -e ""

    check_prerequisites
    setup_homebrew
    setup_python
    setup_nodejs
    setup_docker
    create_directory_structure
    setup_project
    verify_mlx_install
    print_summary
}

main "$@"
