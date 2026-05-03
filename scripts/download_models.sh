#!/usr/bin/env bash
# ============================================================================
# Antigravity-K: Phase 2, Step 3 — 메인 모델 다운로드
# ============================================================================
# 사용법:
#   chmod +x scripts/download_models.sh
#   ./scripts/download_models.sh              # 전체 다운로드
#   ./scripts/download_models.sh --model glm  # GLM만 다운로드
#   ./scripts/download_models.sh --model deepseek
#   ./scripts/download_models.sh --model coder
#   ./scripts/download_models.sh --list        # 모델 목록만 출력
# ============================================================================

set -euo pipefail

# ─── 색상 ────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

log_info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_ok()    { echo -e "${GREEN}[✓]${NC}     $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[✗]${NC}     $*"; }
log_step()  { echo -e "\n${CYAN}${BOLD}━━━ $* ━━━${NC}"; }

# ─── 경로 설정 ──────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
MODELS_DIR="${PROJECT_DIR}/models"
FINETUNE_DIR="${MODELS_DIR}/finetuned"

mkdir -p "${MODELS_DIR}" "${FINETUNE_DIR}"

# ─── 모델 레지스트리 ────────────────────────────────────────────────
# 128GB Unified Memory 기준 최적 양자화 전략
#
# | 모델                    | 파라미터 | 양자화  | 예상 VRAM | 용도           |
# |------------------------|---------|---------|----------|----------------|
# | GLM-5.1-Reasoning-1M   | 9B      | Q8_0    | ~10GB    | 코드 분석/추론  |
# | DeepSeek-R1-Distill     | 70B     | Q4_K_M  | ~40GB    | 고급 추론       |
# | Qwen2.5-Coder           | 32B     | Q8_0    | ~34GB    | 코딩 특화       |
# | Qwen2-VL                | 7B      | Q8_0    | ~8GB     | 비전           |
#
# 동시 로드 시나리오:
#   GLM-5.1(10GB) + Qwen2.5-Coder(34GB) = ~44GB → 여유 84GB
#   DeepSeek-R1(40GB) 단독 → 여유 88GB
# ────────────────────────────────────────────────────────────────────

declare -A MODEL_NAMES=(
    [glm]="mlx-community/GLM-4-9B-0414-8bit"
    [deepseek]="mlx-community/DeepSeek-R1-Distill-Qwen-70B-4bit"
    [coder]="mlx-community/Qwen2.5-Coder-32B-Instruct-8bit"
    [vision]="mlx-community/Qwen2-VL-7B-Instruct-8bit"
)

declare -A MODEL_DESCRIPTIONS=(
    [glm]="GLM-4 9B (8-bit) — 코드 분석 및 장문 추론"
    [deepseek]="DeepSeek-R1 70B (4-bit) — 고급 수학/논리 추론"
    [coder]="Qwen2.5-Coder 32B (8-bit) — 코딩 특화"
    [vision]="Qwen2-VL 7B (8-bit) — 멀티모달 비전"
)

declare -A MODEL_SIZES=(
    [glm]="~10GB"
    [deepseek]="~40GB"
    [coder]="~34GB"
    [vision]="~8GB"
)

# ─── Ollama 모델 레지스트리 (빠른 테스트용) ──────────────────────────
declare -A OLLAMA_MODELS=(
    [glm]="glm4:9b"
    [deepseek]="deepseek-r1:70b"
    [coder]="qwen2.5-coder:32b"
    [vision]="llava:13b"
)

# ─── 사전 검사 ──────────────────────────────────────────────────────
check_prerequisites() {
    log_step "사전 검사"
    
    # Python + pip 확인
    if ! command -v python3 &>/dev/null; then
        log_error "Python3이 설치되지 않았습니다. setup_env.sh를 먼저 실행하세요."
        exit 1
    fi
    log_ok "Python3: $(python3 --version)"
    
    # 가상환경 확인
    if [[ -z "${VIRTUAL_ENV:-}" ]]; then
        if [[ -d "${PROJECT_DIR}/.venv" ]]; then
            log_warn "가상환경 활성화 중..."
            source "${PROJECT_DIR}/.venv/bin/activate"
        else
            log_error "가상환경을 찾을 수 없습니다. setup_env.sh를 먼저 실행하세요."
            exit 1
        fi
    fi
    log_ok "가상환경: ${VIRTUAL_ENV}"
    
    # huggingface-cli 확인
    if ! command -v huggingface-cli &>/dev/null; then
        log_info "huggingface-cli 설치 중..."
        pip install -q huggingface_hub[cli]
    fi
    log_ok "huggingface-cli 사용 가능"
    
    # mlx-lm 확인
    if ! python3 -c "import mlx_lm" &>/dev/null; then
        log_warn "mlx-lm이 설치되지 않았습니다. 설치 중..."
        pip install -q mlx-lm
    fi
    log_ok "mlx-lm 사용 가능"
    
    # 디스크 여유 공간 확인
    local free_gb
    free_gb=$(df -g "${MODELS_DIR}" 2>/dev/null | awk 'NR==2 {print $4}' || echo "?")
    log_info "디스크 여유 공간: ${free_gb}GB (models/ 디렉토리)"
    
    if [[ "${free_gb}" != "?" ]] && (( free_gb < 50 )); then
        log_warn "⚠ 디스크 공간이 부족할 수 있습니다 (최소 100GB 권장)"
    fi
}

# ─── MLX 모델 다운로드 ──────────────────────────────────────────────
download_mlx_model() {
    local key="$1"
    local model_id="${MODEL_NAMES[$key]}"
    local desc="${MODEL_DESCRIPTIONS[$key]}"
    local size="${MODEL_SIZES[$key]}"
    local target_dir="${MODELS_DIR}/${key}"
    
    log_step "${desc}"
    log_info "모델: ${model_id}"
    log_info "예상 크기: ${size}"
    log_info "저장 경로: ${target_dir}"
    
    # 이미 다운로드됨?
    if [[ -d "${target_dir}" ]] && [[ -f "${target_dir}/config.json" ]]; then
        log_ok "이미 다운로드됨: ${target_dir}"
        return 0
    fi
    
    echo ""
    log_info "다운로드 시작... (크기에 따라 수십 분 소요될 수 있습니다)"
    
    # huggingface-cli로 다운로드 (resume 지원)
    huggingface-cli download "${model_id}" \
        --local-dir "${target_dir}" \
        --local-dir-use-symlinks False \
        --resume-download \
        2>&1 | tail -5
    
    if [[ -f "${target_dir}/config.json" ]]; then
        log_ok "다운로드 완료: ${key}"
    else
        log_error "다운로드 실패: ${key}"
        return 1
    fi
}

# ─── Ollama 모델 다운로드 (대안) ────────────────────────────────────
download_ollama_model() {
    local key="$1"
    local model_name="${OLLAMA_MODELS[$key]}"
    
    log_info "Ollama 모델 다운로드: ${model_name}"
    
    if ! command -v ollama &>/dev/null; then
        log_warn "Ollama가 설치되지 않았습니다. MLX 모드로만 진행합니다."
        return 0
    fi
    
    ollama pull "${model_name}" 2>&1 | tail -3
    log_ok "Ollama 모델 준비 완료: ${model_name}"
}

# ─── 모델 검증 ──────────────────────────────────────────────────────
verify_model() {
    local key="$1"
    local target_dir="${MODELS_DIR}/${key}"
    
    log_info "모델 검증: ${key}"
    
    python3 << PYEOF
import json, os, sys

model_dir = "${target_dir}"
config_path = os.path.join(model_dir, "config.json")

if not os.path.exists(config_path):
    print(f"  ⚠ config.json 없음: {model_dir}")
    sys.exit(1)

with open(config_path) as f:
    config = json.load(f)

model_type = config.get("model_type", "unknown")
hidden_size = config.get("hidden_size", "?")
num_layers = config.get("num_hidden_layers", "?")
vocab_size = config.get("vocab_size", "?")

# 파일 크기 계산
total_size = 0
for root, dirs, files in os.walk(model_dir):
    for f in files:
        total_size += os.path.getsize(os.path.join(root, f))

size_gb = total_size / (1024**3)

print(f"  ✓ 모델 타입: {model_type}")
print(f"  ✓ Hidden Size: {hidden_size}")
print(f"  ✓ Layers: {num_layers}")
print(f"  ✓ Vocab Size: {vocab_size:,}" if isinstance(vocab_size, int) else f"  ✓ Vocab Size: {vocab_size}")
print(f"  ✓ 디스크 크기: {size_gb:.1f}GB")
PYEOF
}

# ─── 모델 목록 출력 ─────────────────────────────────────────────────
list_models() {
    log_step "사용 가능한 모델 목록"
    echo ""
    printf "%-12s %-50s %-8s %s\n" "키" "모델 ID" "크기" "설명"
    printf "%-12s %-50s %-8s %s\n" "────" "──────────────────────────────────────────" "────" "──────────────────"
    for key in glm deepseek coder vision; do
        local status="❌"
        if [[ -d "${MODELS_DIR}/${key}" ]] && [[ -f "${MODELS_DIR}/${key}/config.json" ]]; then
            status="✅"
        fi
        printf "${status} %-10s %-50s %-8s %s\n" \
            "${key}" "${MODEL_NAMES[$key]}" "${MODEL_SIZES[$key]}" "${MODEL_DESCRIPTIONS[$key]}"
    done
    echo ""
    
    # 파인튜닝 모델
    if [[ -d "${FINETUNE_DIR}" ]] && [[ "$(ls -A "${FINETUNE_DIR}" 2>/dev/null)" ]]; then
        log_info "파인튜닝 모델:"
        for dir in "${FINETUNE_DIR}"/*/; do
            if [[ -d "$dir" ]]; then
                echo "  🎯 $(basename "$dir")"
            fi
        done
    fi
}

# ─── MLX 빠른 테스트 ────────────────────────────────────────────────
quick_test() {
    local key="$1"
    local target_dir="${MODELS_DIR}/${key}"
    
    log_step "빠른 추론 테스트: ${key}"
    
    python3 << PYEOF
from mlx_lm import load, generate

print("  모델 로딩 중...")
model, tokenizer = load("${target_dir}")
print("  ✓ 모델 로드 완료")

prompt = "다음 Python 함수의 버그를 찾아주세요:\ndef fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)"

response = generate(
    model, 
    tokenizer, 
    prompt=prompt,
    max_tokens=200,
    temp=0.7,
)
print(f"\n  📝 응답:\n{response[:500]}")
PYEOF
}

# ─── 메인 실행 ──────────────────────────────────────────────────────
main() {
    echo ""
    echo -e "${CYAN}${BOLD}"
    echo "  ╔══════════════════════════════════════════╗"
    echo "  ║   Antigravity-K: 모델 다운로드 매니저     ║"
    echo "  ║   Phase 2, Step 3                        ║"
    echo "  ╚══════════════════════════════════════════╝"
    echo -e "${NC}"
    
    local target_model="${1:-all}"
    
    case "${target_model}" in
        --list|-l)
            list_models
            exit 0
            ;;
        --test)
            local test_key="${2:-glm}"
            quick_test "${test_key}"
            exit 0
            ;;
        --help|-h)
            echo "사용법: $0 [옵션]"
            echo ""
            echo "옵션:"
            echo "  (없음)         모든 모델 다운로드"
            echo "  --model KEY    특정 모델만 (glm, deepseek, coder, vision)"
            echo "  --list         모델 목록 출력"
            echo "  --test KEY     모델 빠른 테스트"
            echo "  --help         도움말"
            exit 0
            ;;
        --model|-m)
            target_model="${2:-}"
            if [[ -z "${target_model}" ]] || [[ -z "${MODEL_NAMES[$target_model]+x}" ]]; then
                log_error "유효하지 않은 모델 키: ${target_model}"
                log_info "사용 가능: glm, deepseek, coder, vision"
                exit 1
            fi
            ;;
    esac
    
    check_prerequisites
    
    if [[ "${target_model}" == "all" ]]; then
        # 전체 다운로드 (권장 순서: 작은 것부터)
        for key in vision glm coder deepseek; do
            download_mlx_model "${key}"
            verify_model "${key}"
        done
    else
        download_mlx_model "${target_model}"
        verify_model "${target_model}"
    fi
    
    echo ""
    list_models
    
    log_step "완료"
    log_ok "모든 모델이 준비되었습니다!"
    log_info ""
    log_info "빠른 테스트:  ./scripts/download_models.sh --test glm"
    log_info "API 프록시:   python scripts/api_forwarder.py --port 1234"
    log_info "대시보드:     cd dashboard && npm run dev"
}

main "$@"
