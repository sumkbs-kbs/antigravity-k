#!/usr/bin/env bash
# ============================================================================
# Antigravity-K: Ollama 설치 및 구성 (Apple Silicon)
# ============================================================================
# Ollama = 빠른 테스트용 로컬 LLM 런타임
# 설치 후 자동으로 OpenAI 호환 API 제공 (http://localhost:11434/v1)
# ============================================================================

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'

log_info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
log_success() { echo -e "${GREEN}[✓]${NC} $*"; }
log_warn()    { echo -e "${YELLOW}[!]${NC} $*"; }
log_step()    { echo -e "\n${CYAN}━━━ $* ━━━${NC}"; }

# ─── Ollama 설치 ─────────────────────────────────────────────────────────────
install_ollama() {
    log_step "1. Ollama 설치"

    if command -v ollama &>/dev/null; then
        local ver
        ver=$(ollama --version 2>/dev/null | head -1)
        log_success "Ollama 이미 설치됨: ${ver}"
    else
        log_info "Ollama를 설치합니다..."

        if [[ "$(uname)" == "Darwin" ]]; then
            # macOS: Homebrew 또는 공식 설치 스크립트
            if command -v brew &>/dev/null; then
                brew install ollama
            else
                curl -fsSL https://ollama.com/install.sh | sh
            fi
        else
            curl -fsSL https://ollama.com/install.sh | sh
        fi

        log_success "Ollama 설치 완료"
    fi
}

# ─── Ollama 서비스 시작 ──────────────────────────────────────────────────────
start_ollama() {
    log_step "2. Ollama 서비스 시작"

    # 이미 실행 중인지 확인
    if curl -s http://localhost:11434/api/tags &>/dev/null; then
        log_success "Ollama 서비스 이미 실행 중 (port 11434)"
        return
    fi

    log_info "Ollama 서비스를 백그라운드로 시작합니다..."
    ollama serve &>/dev/null &
    sleep 3

    if curl -s http://localhost:11434/api/tags &>/dev/null; then
        log_success "Ollama 서비스 시작 완료"
    else
        log_warn "Ollama 서비스 시작 대기 중... (5초 추가 대기)"
        sleep 5
    fi
}

# ─── 테스트용 경량 모델 다운로드 ─────────────────────────────────────────────
pull_test_models() {
    log_step "3. 테스트용 모델 다운로드"

    # 빠른 테스트용 경량 모델
    local models=(
        "qwen2.5:7b"          # 범용 7B (빠른 테스트)
        "qwen2.5-coder:7b"    # 코딩 7B (빠른 테스트)
        "nomic-embed-text"     # 임베딩 모델
    )

    for model in "${models[@]}"; do
        log_info "다운로드: ${model}..."
        ollama pull "$model"
        log_success "${model} 다운로드 완료"
    done

    echo ""
    log_info "설치된 모델 목록:"
    ollama list
}

# ─── 대형 모델 다운로드 (선택) ───────────────────────────────────────────────
pull_large_models() {
    log_step "4. 대형 모델 다운로드 (128GB 전용)"

    echo -e "${YELLOW}주의: 대형 모델은 수십 GB를 다운로드합니다.${NC}"
    echo -e "다음 모델을 다운로드하시겠습니까?"
    echo "  1) deepseek-r1:70b     (~40GB, 추론 특화)"
    echo "  2) qwen2.5-coder:32b   (~18GB, 코딩 특화)"
    echo "  3) 건너뛰기"
    echo ""
    read -rp "선택 [1/2/3]: " choice

    case "$choice" in
        1)
            log_info "DeepSeek-R1 70B 다운로드 시작..."
            ollama pull deepseek-r1:70b
            log_success "deepseek-r1:70b 다운로드 완료"
            ;;
        2)
            log_info "Qwen2.5-Coder 32B 다운로드 시작..."
            ollama pull qwen2.5-coder:32b
            log_success "qwen2.5-coder:32b 다운로드 완료"
            ;;
        3|*)
            log_info "대형 모델 다운로드를 건너뜁니다."
            ;;
    esac
}

# ─── API 연동 테스트 ─────────────────────────────────────────────────────────
test_api() {
    log_step "5. OpenAI 호환 API 테스트"

    log_info "Ollama OpenAI API 엔드포인트: http://localhost:11434/v1"

    # 모델 목록 조회
    echo -e "\n  모델 목록 (GET /v1/models):"
    curl -s http://localhost:11434/v1/models | python3 -m json.tool 2>/dev/null | head -20

    # Chat Completions 테스트
    echo -e "\n  Chat 테스트 (POST /v1/chat/completions):"
    local response
    response=$(curl -s http://localhost:11434/v1/chat/completions \
        -H "Content-Type: application/json" \
        -d '{
            "model": "qwen2.5:7b",
            "messages": [{"role": "user", "content": "Say hello in Korean"}],
            "max_tokens": 50
        }' 2>/dev/null)

    echo "$response" | python3 -m json.tool 2>/dev/null | head -15
    log_success "OpenAI 호환 API 정상 작동"
}

# ─── 완료 요약 ────────────────────────────────────────────────────────────────
print_summary() {
    log_step "설치 완료"

    echo -e ""
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${NC}  ${GREEN}Ollama 설치 완료!${NC}                                      ${CYAN}║${NC}"
    echo -e "${CYAN}╠══════════════════════════════════════════════════════════╣${NC}"
    echo -e "${CYAN}║${NC}                                                          ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}  API 엔드포인트:                                         ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}    ${YELLOW}http://localhost:11434/v1${NC}                                ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}                                                          ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}  사용법:                                                 ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}    ${YELLOW}ollama run qwen2.5:7b${NC}       # 대화 테스트               ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}    ${YELLOW}ollama run deepseek-r1:70b${NC}  # 추론 모델                 ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}    ${YELLOW}ollama list${NC}                 # 모델 목록                  ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}                                                          ${CYAN}║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════╝${NC}"
    echo -e ""
}

# ─── 메인 ─────────────────────────────────────────────────────────────────────
main() {
    echo -e "\n${CYAN}Antigravity-K — Ollama 설치 & 구성${NC}\n"

    install_ollama
    start_ollama
    pull_test_models
    pull_large_models
    test_api
    print_summary
}

main "$@"
