#!/usr/bin/env bash
# ============================================================================
# Antigravity-K — One-Click Installer
# ============================================================================
# Target: macOS Apple Silicon (M1–M5)
#
# Usage:
#   curl -fsSL https://agk.sh | bash                    # Default install
#   curl -fsSL https://agk.sh | bash -s -- --dev        # +dev deps
#   curl -fsSL https://agk.sh | bash -s -- --minimal    # Core only
#   curl -fsSL https://agk.sh | bash -s -- --pipx       # pipx install (global agk)
#   curl -fsSL https://agk.sh | bash -s -- --force      # Re-install
#
# Options:
#   --help, -h          Show this help message
#   --version, -v       Show version
#   --dev               Install dev dependencies (pytest, ruff, etc.)
#   --minimal           Core only (no MLX, no RAG, no dashboard)
#   --pipx              Install agk globally via pipx (requires pipx)
#   --no-dashboard      Skip dashboard build
#   --no-ollama         Skip Ollama installation
#   --no-mlx            Skip MLX extras (Apple Silicon)
#   --force, -f         Force re-install (overwrite existing)
#   --yes, -y           Non-interactive mode (auto-yes to prompts)
#   --dry-run           Preview actions without executing
#
# Environment:
#   AGK_INSTALL_DIR     Installation directory (default: ~/.antigravity-k)
#   AGK_BRANCH          Git branch (default: main)
#   AGK_REPO            Repository URL
#   AGK_DEBUG           Enable debug logging
# ============================================================================

set -euo pipefail

# ─── Version ──────────────────────────────────────────────────────────────────
VERSION="0.1.0"

# ─── Detect pipe mode ─────────────────────────────────────────────────────────
# When curl | bash, stdin is NOT a TTY — interactive read won't work.
# We auto-detect and default to non-interactive in pipe mode.
if [[ -t 0 ]]; then
    HAS_TTY=true
else
    HAS_TTY=false
fi

# ─── Color Definitions ────────────────────────────────────────────────────────
RESET='\033[0m'
BOLD='\033[1m'
DIM='\033[2m'
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
BG_GREEN='\033[42m'

# ─── Logging ──────────────────────────────────────────────────────────────────
log_info()    { echo -e "  ${BLUE}ℹ${RESET}  $*"; }
log_success() { echo -e "  ${GREEN}✔${RESET}  $*"; }
log_warn()    { echo -e "  ${YELLOW}⚠${RESET}  $*"; }
log_error()   { echo -e "  ${RED}✘${RESET}  $*"; }
log_step()    { echo -e "\n${BOLD}${CYAN}  ── $* ──${RESET}\n"; }
log_debug()   { if [[ -n "${AGK_DEBUG:-}" ]]; then echo -e "  ${DIM}DEBUG: $*${RESET}"; fi; }
log_dry()     { echo -e "  ${DIM}[DRY-RUN]${RESET} $*"; }

# ─── Prompt (TTY-safe) ────────────────────────────────────────────────────────
prompt_yes() {
    local question="$1"
    local default="${2:-Y}"
    if [[ "${NON_INTERACTIVE}" == "true" ]] || [[ "${HAS_TTY}" != "true" ]]; then
        # In pipe mode or non-interactive, default to yes
        return 0
    fi
    local yn
    read -r -p "  ${question} [${default}/n]: " yn
    case "${yn}" in
        n|N|no|NO) return 1 ;;
        *) return 0 ;;
    esac
}

# ─── Header ───────────────────────────────────────────────────────────────────
print_header() {
    echo -e ""
    echo -e "${CYAN}${BOLD}   ╔══════════════════════════════════════════════════╗${RESET}"
    echo -e "${CYAN}${BOLD}   ║${RESET}          ${WHITE}Antigravity-K${RESET} — One-Click Installer   ${CYAN}${BOLD}║${RESET}"
    echo -e "${CYAN}${BOLD}   ║${RESET}     ${DIM}Local Autonomous Engineering Agent${RESET}          ${CYAN}${BOLD}║${RESET}"
    echo -e "${CYAN}${BOLD}   ║${RESET}     ${DIM}for Apple Silicon${RESET}                           ${CYAN}${BOLD}║${RESET}"
    echo -e "${CYAN}${BOLD}   ╚══════════════════════════════════════════════════╝${RESET}"
    echo -e "   ${DIM}v${VERSION}  |  macOS Apple Silicon${RESET}"
    echo -e ""
}

# ─── Help ─────────────────────────────────────────────────────────────────────
print_help() {
    print_header
    echo -e " ${BOLD}USAGE${RESET}"
    echo -e "   curl -fsSL https://agk.sh | bash"
    echo -e "   curl -fsSL https://agk.sh | bash -s -- [OPTIONS]"
    echo -e ""
    echo -e " ${BOLD}OPTIONS${RESET}"
    echo -e "   ${GREEN}--help, -h${RESET}        Show this help"
    echo -e "   ${GREEN}--version, -v${RESET}     Show version"
    echo -e "   ${GREEN}--dev${RESET}             +dev dependencies (pytest, ruff)"
    echo -e "   ${GREEN}--minimal${RESET}         Core only (no MLX/RAG/dashboard)"
    echo -e "   ${GREEN}--pipx${RESET}            Global agk command via pipx"
    echo -e "   ${GREEN}--no-dashboard${RESET}    Skip dashboard build"
    echo -e "   ${GREEN}--no-ollama${RESET}       Skip Ollama install"
    echo -e "   ${GREEN}--no-mlx${RESET}          Skip MLX extras"
    echo -e "   ${GREEN}--force, -f${RESET}       Re-install (overwrite config)"
    echo -e "   ${GREEN}--yes, -y${RESET}         Non-interactive mode"
    echo -e "   ${GREEN}--dry-run${RESET}         Preview only"
    echo -e ""
    echo -e " ${BOLD}ENVIRONMENT${RESET}"
    echo -e "   ${DIM}AGK_INSTALL_DIR${RESET}   Install path (default: ~/.antigravity-k)"
    echo -e "   ${DIM}AGK_BRANCH${RESET}        Git branch (default: main)"
    echo -e "   ${DIM}AGK_REPO${RESET}          Repository URL"
    echo -e "   ${DIM}AGK_DEBUG${RESET}         Debug logging"
    echo -e ""
}

# ─── Parse Args ───────────────────────────────────────────────────────────────
parse_args() {
    INSTALL_DEV=false
    INSTALL_MINIMAL=false
    INSTALL_PIPX=false
    INSTALL_DASHBOARD=true
    INSTALL_OLLAMA=true
    INSTALL_MLX=true
    FORCE=false
    NON_INTERACTIVE=false
    DRY_RUN=false

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --help|-h) print_help; exit 0 ;;
            --version|-v) echo "${VERSION}"; exit 0 ;;
            --dev) INSTALL_DEV=true; shift ;;
            --minimal) INSTALL_MINIMAL=true; INSTALL_MLX=false; INSTALL_DASHBOARD=false; shift ;;
            --pipx) INSTALL_PIPX=true; shift ;;
            --no-dashboard) INSTALL_DASHBOARD=false; shift ;;
            --no-ollama) INSTALL_OLLAMA=false; shift ;;
            --no-mlx) INSTALL_MLX=false; shift ;;
            --force|-f) FORCE=true; shift ;;
            --yes|-y) NON_INTERACTIVE=true; shift ;;
            --dry-run) DRY_RUN=true; shift ;;
            *) log_error "Unknown: $1"; echo "  Use --help for usage."; exit 1 ;;
        esac
    done
}

# ─── Init Config ──────────────────────────────────────────────────────────────
init_config() {
    REPO_URL="${AGK_REPO:-https://github.com/sumkbs-kbs/antigravity-k.git}"
    BRANCH="${AGK_BRANCH:-main}"
    INSTALL_DIR="${AGK_INSTALL_DIR:-$HOME/.antigravity-k}"

    # Detect if running from within the repo.
    # In curl|bash mode, BASH_SOURCE is a temp fd like /dev/fd/63.
    # We use PWD + pyproject.toml check as fallback.
    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "")"

    if [[ -n "${script_dir}" && -f "${script_dir}/../pyproject.toml" ]]; then
        IN_REPO=true
        PROJECT_DIR="$(cd "${script_dir}/.." && pwd)"
        log_debug "In-repo mode: ${PROJECT_DIR}"
    elif [[ -f "${PWD}/pyproject.toml" ]] && grep -q 'name = "antigravity-k"' "${PWD}/pyproject.toml" 2>/dev/null; then
        IN_REPO=true
        PROJECT_DIR="${PWD}"
        log_debug "In-repo mode (PWD): ${PROJECT_DIR}"
    else
        IN_REPO=false
        PROJECT_DIR="${INSTALL_DIR}"
        log_debug "Standalone mode, target: ${PROJECT_DIR}"
    fi
}

# ─── Re-install check ─────────────────────────────────────────────────────────
check_existing() {
    if [[ "${FORCE}" == "true" ]]; then
        return
    fi

    local marker="${PROJECT_DIR}/.agk_installed"
    if [[ -f "${marker}" ]]; then
        local installed_ver
        installed_ver=$(cat "${marker}" 2>/dev/null || echo "unknown")
        echo ""
        log_warn "Antigravity-K ${installed_ver} is already installed at:"
        echo "  ${PROJECT_DIR}"
        echo ""
        if prompt_yes "Re-install?"; then
            FORCE=true
            log_info "Re-installing..."
        else
            log_info "To upgrade later, run with --force or --dry-run first."
            exit 0
        fi
    fi
}

# ─── System Check ─────────────────────────────────────────────────────────────
check_system() {
    log_step "System Check"

    if [[ "$(uname)" != "Darwin" ]]; then
        log_error "macOS only (detected: $(uname))"
        exit 1
    fi
    log_success "macOS detected"

    if [[ "$(uname -m)" != "arm64" ]]; then
        log_error "Apple Silicon required"
        exit 1
    fi
    log_success "Apple Silicon (ARM64)"

    local chip_info
    chip_info=$(sysctl -n machdep.cpu.brand_string 2>/dev/null || echo "Apple Silicon")
    log_info "Chip: ${chip_info}"

    local total_mem_gb=$(( $(sysctl -n hw.memsize) / 1073741824 ))
    log_info "Memory: ${total_mem_gb}GB"
    if [[ ${total_mem_gb} -lt 16 ]]; then
        log_warn "Less than 16GB RAM. 70B models may not fit."
    elif [[ ${total_mem_gb} -ge 32 ]]; then
        log_success "70B models supported"
    fi

    local free_gb
    free_gb=$(df -g /tmp 2>/dev/null | awk 'NR==2 {print $4}' || echo "?")
    if [[ "${free_gb}" != "?" ]]; then
        log_info "Free disk: ~${free_gb}GB"
    fi

    if ! xcode-select -p &>/dev/null; then
        if [[ "${DRY_RUN}" == "true" ]]; then
            log_dry "xcode-select --install"
        else
            log_info "Installing Xcode CLI Tools..."
            xcode-select --install 2>/dev/null || true
            echo "  ⏳ Complete the dialog, then re-run this installer."
            exit 0
        fi
    fi
    log_success "Xcode CLI Tools: installed"
}

# ─── Homebrew ─────────────────────────────────────────────────────────────────
setup_homebrew() {
    log_step "Homebrew"

    if command -v brew &>/dev/null; then
        log_success "Homebrew: $(brew --version 2>/dev/null | head -1 | awk '{print $1, $2}')"
        return
    fi

    log_info "Installing Homebrew..."
    if [[ "${DRY_RUN}" == "true" ]]; then
        log_dry "Install Homebrew"
        return
    fi

    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

    if [[ -f /opt/homebrew/bin/brew ]]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
        local profile="${HOME}/.zshrc"
        if [[ -z "${ZSH_VERSION:-}" ]]; then
            profile="${HOME}/.bash_profile"
        fi
        if ! grep -q '/opt/homebrew/bin/brew shellenv' "${profile}" 2>/dev/null; then
            echo "" >> "${profile}"
            echo '# Homebrew (Apple Silicon)' >> "${profile}"
            echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> "${profile}"
        fi
    fi
    log_success "Homebrew installed"
}

# ─── Python ───────────────────────────────────────────────────────────────────
setup_python() {
    log_step "Python 3.12+"

    local py_cmd=""
    local py_ver="" py_major="" py_minor=""

    if [[ -f /opt/homebrew/bin/python3 ]]; then
        py_cmd="/opt/homebrew/bin/python3"
        py_ver=$(${py_cmd} --version 2>&1 | awk '{print $2}')
    elif command -v python3 &>/dev/null; then
        py_cmd="$(command -v python3)"
        py_ver=$(python3 --version 2>&1 | awk '{print $2}')
    fi

    if [[ -n "${py_ver}" ]]; then
        py_major=$(echo "${py_ver}" | cut -d. -f1)
        py_minor=$(echo "${py_ver}" | cut -d. -f2)
    fi

    if [[ -z "${py_cmd}" ]] || [[ "${py_major}" -lt 3 ]] || { [[ "${py_major}" -eq 3 ]] && [[ "${py_minor}" -lt 12 ]]; }; then
        if [[ -n "${py_ver}" ]]; then
            log_warn "Python ${py_ver} is too old (3.12+ needed)"
        fi
        if [[ "${DRY_RUN}" == "true" ]]; then
            log_dry "brew install python@3.12"
            py_cmd="/opt/homebrew/bin/python3"
        else
            log_info "Installing Python 3.12 via Homebrew..."
            brew install python@3.12
            py_cmd="/opt/homebrew/bin/python3"
        fi
    fi

    PYTHON_CMD="${py_cmd}"
    PYTHON_VERSION=$(${PYTHON_CMD} --version 2>&1 | awk '{print $2}')
    log_success "Python ${PYTHON_VERSION}"

    if [[ "${DRY_RUN}" != "true" ]]; then
        "${PYTHON_CMD}" -m pip install --upgrade pip --quiet
    fi
}

# ─── pipx Setup ───────────────────────────────────────────────────────────────
setup_pipx() {
    if [[ "${INSTALL_PIPX}" != "true" ]]; then
        return
    fi

    log_step "pipx (Global agk Command)"

    if command -v pipx &>/dev/null; then
        log_success "pipx already installed"
    else
        log_info "Installing pipx..."
        if [[ "${DRY_RUN}" == "true" ]]; then
            log_dry "brew install pipx && pipx ensurepath"
        else
            brew install pipx
            pipx ensurepath
            log_success "pipx installed"
        fi
    fi

    PIPX_INSTALLED=true
}

# ─── Repository ───────────────────────────────────────────────────────────────
setup_repository() {
    log_step "Repository"

    if [[ "${IN_REPO}" == "true" ]]; then
        log_success "Inside repository: ${PROJECT_DIR}"
        return
    fi

    if [[ -d "${PROJECT_DIR}/.git" ]]; then
        log_success "Repository exists at ${PROJECT_DIR}"
        if [[ "${DRY_RUN}" != "true" ]]; then
            cd "${PROJECT_DIR}"
            log_info "Updating (fast-forward only)..."
            git fetch origin "${BRANCH}" 2>/dev/null || log_warn "Fetch failed"
            # Safe update: refuses if local changes exist
            if ! git diff --quiet HEAD 2>/dev/null; then
                log_warn "Local changes detected. Stashing..."
                git stash --include-untracked 2>/dev/null || true
            fi
            git pull --ff-only origin "${BRANCH}" 2>/dev/null || log_warn "Pull failed (may be up to date)"
        fi
    else
        log_info "Cloning ${BRANCH} branch..."
        if [[ "${DRY_RUN}" == "true" ]]; then
            log_dry "git clone --depth 1 --branch ${BRANCH} ${REPO_URL} ${PROJECT_DIR}"
        else
            mkdir -p "$(dirname "${PROJECT_DIR}")"
            git clone --depth 1 --branch "${BRANCH}" "${REPO_URL}" "${PROJECT_DIR}"
            log_success "Repository cloned"
        fi
    fi

    if [[ "${DRY_RUN}" != "true" ]]; then
        cd "${PROJECT_DIR}"
    fi

    local branch_actual
    branch_actual=$(cd "${PROJECT_DIR}" 2>/dev/null && git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "N/A")
    local commit
    commit=$(cd "${PROJECT_DIR}" 2>/dev/null && git rev-parse --short HEAD 2>/dev/null || echo "N/A")
    log_info "Branch: ${branch_actual}  |  Commit: ${commit}"
}

# ─── Package Install ──────────────────────────────────────────────────────────
install_package() {
    log_step "Package Installation"

    cd "${PROJECT_DIR}"

    local extras=""
    if [[ "${INSTALL_MINIMAL}" != "true" ]]; then
        extras="rag"
        if [[ "${INSTALL_MLX}" == "true" ]]; then
            extras="${extras},mlx"
        fi
        if [[ "${INSTALL_DEV}" == "true" ]]; then
            extras="${extras},dev"
        fi
    fi

    if [[ "${DRY_RUN}" == "true" ]]; then
        if [[ -n "${extras}" ]]; then
            log_dry "pip install -e \".[${extras}]\""
        else
            log_dry "pip install -e ."
        fi
        return
    fi

    # ---- pipx path ----
    if [[ "${INSTALL_PIPX}" == "true" ]]; then
        log_info "Installing via pipx (global agk command)..."
        if [[ -n "${extras}" ]]; then
            pipx install "${PROJECT_DIR}[${extras}]" 2>&1 | tail -3 || {
                log_warn "pipx install failed, falling back to venv"
                INSTALL_PIPX=false
                setup_venv_and_install "${extras}"
            }
        else
            pipx install "${PROJECT_DIR}" 2>&1 | tail -3 || {
                log_warn "pipx install failed, falling back to venv"
                INSTALL_PIPX=false
                setup_venv_and_install ""
            }
        fi
        if command -v agk &>/dev/null; then
            log_success "Global 'agk' command available!"
        fi
        return
    fi

    # ---- venv path (default) ----
    setup_venv_and_install "${extras}"
}

# ─── Venv + Install ──────────────────────────────────────────────────────────
setup_venv_and_install() {
    local extras="$1"
    local venv_dir="${PROJECT_DIR}/.venv"

    if [[ ! -d "${venv_dir}" ]]; then
        log_info "Creating virtual environment..."
        "${PYTHON_CMD}" -m venv "${venv_dir}"
    fi

    local vpip="${venv_dir}/bin/pip"
    "${vpip}" install --upgrade pip --quiet

    log_info "Installing package (this may take a few minutes)..."
    if [[ -n "${extras}" ]]; then
        "${vpip}" install -e ".[${extras}]" 2>&1 | tail -5
    else
        "${vpip}" install -e . 2>&1 | tail -5
    fi

    VENV_PYTHON="${venv_dir}/bin/python3"
    VENV_PIP="${vpip}"
}



# ─── Dashboard ────────────────────────────────────────────────────────────────
build_dashboard() {
    if [[ "${INSTALL_DASHBOARD}" != "true" ]]; then
        log_info "Dashboard: skipped"
        return
    fi
    log_step "Dashboard"

    local dd="${PROJECT_DIR}/dashboard"
    if [[ ! -d "${dd}" ]]; then
        log_warn "dashboard/ not found"
        return
    fi
    if [[ ! -f "${dd}/package.json" ]]; then
        log_warn "package.json not found"
        return
    fi

    if ! command -v node &>/dev/null; then
        if [[ "${DRY_RUN}" == "true" ]]; then
            log_dry "brew install node"
        else
            log_info "Installing Node.js..."
            brew install node 2>/dev/null || true
        fi
    fi
    if command -v node &>/dev/null; then
        log_success "Node.js $(node --version)"
    fi

    if [[ "${DRY_RUN}" == "true" ]]; then
        log_dry "cd dashboard && npm ci && npm run build"
        return
    fi

    cd "${dd}"
    log_info "Installing deps..."
    npm ci --quiet 2>&1 | tail -3 || npm install 2>&1 | tail -3
    log_info "Building..."
    npm run build 2>&1 | tail -3
    if [[ -d "${dd}/dist" ]]; then
        log_success "Dashboard built: ${dd}/dist/"
    fi
    cd "${PROJECT_DIR}"
}

# ─── Config ───────────────────────────────────────────────────────────────────
init_config_file() {
    log_step "Configuration"

    local cfg="${PROJECT_DIR}/config.yaml"
    local cfg_example="${PROJECT_DIR}/config.yaml.example"

    if [[ -f "${cfg}" ]] && [[ "${FORCE}" != "true" ]]; then
        log_success "config.yaml exists"
    elif [[ -f "${cfg_example}" ]]; then
        if [[ "${DRY_RUN}" == "true" ]]; then
            log_dry "cp config.yaml.example → config.yaml"
        else
            cp "${cfg_example}" "${cfg}"
            log_success "config.yaml created"
        fi
    fi
}

# ─── Ollama ───────────────────────────────────────────────────────────────────
setup_ollama() {
    if [[ "${INSTALL_OLLAMA}" != "true" ]]; then
        return
    fi
    log_step "Ollama (Local LLM Runtime)"

    if command -v ollama &>/dev/null; then
        local ver
        ver=$(ollama --version 2>/dev/null | head -1 || echo "installed")
        log_success "Ollama: ${ver}"
        if curl -s http://localhost:11434/api/tags &>/dev/null 2>&1; then
            log_success "Ollama service: running"
        else
            log_info "Start with: ollama serve"
        fi
        return
    fi

    if [[ "${DRY_RUN}" == "true" ]]; then
        log_dry "brew install ollama  (or: curl -fsSL https://ollama.com/install.sh | sh)"
        return
    fi

    if prompt_yes "Install Ollama for local inference?"; then
        if command -v brew &>/dev/null; then
            brew install ollama 2>/dev/null
        else
            curl -fsSL https://ollama.com/install.sh | sh
        fi
        log_success "Ollama installed"
    else
        log_info "Skipped (install later: brew install ollama)"
    fi
}

# ─── Shell Integration ────────────────────────────────────────────────────────
setup_shell_integration() {
    log_step "Shell Integration"

    local profile="${HOME}/.zshrc"
    if [[ -z "${ZSH_VERSION:-}" ]]; then
        profile="${HOME}/.bash_profile"
    fi

    if [[ "${INSTALL_PIPX}" == "true" ]]; then
        # pipx path: agk is already globally available
        if command -v agk &>/dev/null; then
            log_success "'agk' globally available (pipx)"
        fi
        return
    fi

    # venv path: add a shell function that auto-activates
    local snippet
    snippet=$(cat <<'FNSNIP'
# Antigravity-K: auto-activating shell function
agk() {
    local _agk_dir="${HOME}/.antigravity-k"
    if [[ -f "${_agk_dir}/.venv/bin/activate" ]]; then
        # shellcheck disable=SC1091
        source "${_agk_dir}/.venv/bin/activate"
        command agk "$@"
        deactivate 2>/dev/null || true
    else
        echo "Antigravity-K not found at ${_agk_dir}. Re-run the installer."
        return 1
    fi
}
FNSNIP
)

    if grep -q "Antigravity-K" "${profile}" 2>/dev/null; then
        log_success "Shell integration exists"
    else
        if [[ "${DRY_RUN}" == "true" ]]; then
            log_dry "Add agk() function to ${profile}"
        else
            echo "" >> "${profile}"
            echo "# Antigravity-K: auto-activating shell function" >> "${profile}"
            echo "${snippet}" >> "${profile}"
            log_success "Added 'agk' function to ${profile}"
            log_info "  Run: source ${profile}  (or open new terminal)"
        fi
    fi
}

# ─── Verify ───────────────────────────────────────────────────────────────────
verify_installation() {
    if [[ "${DRY_RUN}" == "true" ]]; then
        log_dry "Verification skipped (dry-run)"
        return
    fi
    log_step "Verification"

    local errors=0

    if "${VENV_PYTHON:-python3}" -c "import antigravity_k; print(f'  antigravity-k: {antigravity_k.__version__}')" 2>/dev/null; then
        log_success "Package import OK"
    else
        log_error "Package import failed"
        errors=$((errors + 1))
    fi

    if [[ "${INSTALL_MLX}" == "true" ]] && [[ "${INSTALL_MINIMAL}" != "true" ]]; then
        if "${VENV_PYTHON:-python3}" -c "import mlx.core as mx; print(f'  mlx: {mx.__version__}')" 2>/dev/null; then
            log_success "MLX OK"
            "${VENV_PYTHON:-python3}" -c "
import mlx.core as mx
print('  Metal GPU: Active' if 'gpu' in str(mx.default_device()).lower() else '  ${YELLOW}Metal GPU: CPU mode${RESET}')
" 2>/dev/null || true
        else
            log_warn "MLX not available"
        fi
    fi

    if [[ -d "${PROJECT_DIR}/dashboard/dist" ]]; then
        log_success "Dashboard: built"
    fi

    if [[ ${errors} -gt 0 ]]; then
        log_error "${errors} error(s) found."
    fi
}

# ─── Summary ──────────────────────────────────────────────────────────────────
print_summary() {
    echo -e ""
    echo -e "${BG_GREEN}${WHITE}${BOLD}  ✔ INSTALLATION COMPLETE  ${RESET}"
    echo -e ""
    echo -e " ${BOLD}Quick Start${RESET}"
    echo -e ""

    if [[ "${INSTALL_PIPX}" == "true" ]]; then
        echo -e "  ${CYAN}1.${RESET} Run ${GREEN}agk serve${RESET} to start the API server"
        echo -e "  ${CYAN}2.${RESET} Open ${GREEN}http://localhost:8000${RESET} for the dashboard"
        echo -e "  ${CYAN}3.${RESET} Run ${GREEN}agk status${RESET} to check system state"
    else
        echo -e "  ${CYAN}1.${RESET} Activate: ${GREEN}source ${PROJECT_DIR}/.venv/bin/activate${RESET}"
        echo -e "  ${CYAN}2.${RESET} Server:  ${GREEN}agk serve${RESET}"
        echo -e "  ${CYAN}3.${RESET} Open:    ${GREEN}http://localhost:8000${RESET}"
    fi
    echo -e ""
    echo -e " ${BOLD}Details${RESET}"
    echo -e "  ${DIM}Location:${RESET}  ${PROJECT_DIR}"
    echo -e "  ${DIM}Python:${RESET}    ${PYTHON_VERSION}"
    echo -e "  ${DIM}Config:${RESET}    ${PROJECT_DIR}/config.yaml"
    echo -e ""
    echo -e " ${BOLD}Next${RESET}"
    echo -e "  ${YELLOW}→ Models:${RESET}  ${PROJECT_DIR}/scripts/download_models.sh"
    echo -e "  ${YELLOW}→ Tests:${RESET}   make test-quick  (inside project)"
    echo -e ""
}

# ─── Main ─────────────────────────────────────────────────────────────────────
main() {
    parse_args "$@"

    if [[ "${DRY_RUN}" == "true" ]]; then
        echo -e "  ${YELLOW}═══ DRY RUN ═══${RESET}\n"
    fi
    if [[ "${HAS_TTY}" != "true" ]] && [[ "${DRY_RUN}" != "true" ]]; then
        log_info "Pipe mode detected — running non-interactively"
    fi

    print_header
    init_config
    check_existing
    check_system
    setup_homebrew
    setup_python
    setup_pipx

    command -v git &>/dev/null || { log_info "Installing git..."; brew install git 2>/dev/null || true; }
    log_success "Git: $(git --version 2>/dev/null | head -1 || echo 'ok')"

    setup_repository

    # install_package handles both venv and pipx paths
    install_package

    build_dashboard
    init_config_file
    setup_ollama
    setup_shell_integration
    verify_installation

    if [[ "${DRY_RUN}" == "true" ]]; then
        echo -e "\n  ${YELLOW}═══ DRY RUN — No changes made ═══${RESET}\n"
    else
        echo "${VERSION}" > "${PROJECT_DIR}/.agk_installed" 2>/dev/null || true
        print_summary
    fi
}

main "$@"
