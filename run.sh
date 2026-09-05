#!/bin/bash
# Ssak-Ai 실행 스크립트
# 사용법: ./run.sh [옵션]
#   옵션 없음: API 서버 + SearxNG 시작
#   stop:      서버 종료
#   status:    실행 상태 확인
#   logs:      실시간 로그 보기

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"

VENV="$PROJECT_ROOT/.venv"
PYTHON="$VENV/bin/python"
UVICORN="$VENV/bin/uvicorn"
PORT=8000
LOG_FILE="/tmp/agk_server.log"
SEARXNG_NAME="searxng"

# 색상
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

print_status() { echo -e "${CYAN}[$(date +%H:%M:%S)]${NC} $1"; }
print_ok()     { echo -e "${GREEN}[$(date +%H:%M:%S)] ✅${NC} $1"; }
print_warn()   { echo -e "${YELLOW}[$(date +%H:%M:%S)] ⚠️${NC} $1"; }
print_err()    { echo -e "${RED}[$(date +%H:%M:%S)] ❌${NC} $1"; }

# ─── 명령어 처리 ───

case "${1:-start}" in

  stop)
    print_status "Ssak-Ai 종료 중..."
    # API 서버 종료
    PID=$(lsof -ti:$PORT 2>/dev/null || true)
    if [ -n "$PID" ]; then
      kill $PID 2>/dev/null || true
      print_ok "API 서버 종료 (PID $PID)"
    else
      print_warn "API 서버가 실행 중이 아님"
    fi
    # SearxNG는 계속 실행 (재부팅 시 자동 시작)
    echo ""
    echo "SearxNG 컨테이너는 계속 실행됩니다 (재부팅 시 자동 시작)."
    echo "완전히 종료하려면: docker stop $SEARXNG_NAME"
    ;;

  status)
    echo ""
    echo "╔══════════════════════════════════════════════╗"
    echo "║            Ssak-Ai 실행 상태                 ║"
    echo "╠══════════════════════════════════════════════╣"

    # API 서버
    PID=$(lsof -ti:$PORT 2>/dev/null || true)
    if [ -n "$PID" ]; then
      echo -e "║  API 서버:    ${GREEN}실행 중${NC} (PID $PID, 포트 $PORT)     ║"
    else
      echo -e "║  API 서버:    ${RED}중지${NC}                              ║"
    fi

    # SearxNG
    if docker ps --filter name=$SEARXNG_NAME --format '{{.Status}}' 2>/dev/null | grep -q "Up"; then
      echo -e "║  SearxNG:     ${GREEN}실행 중${NC} (포트 8080)                ║"
    else
      echo -e "║  SearxNG:     ${YELLOW}중지${NC}                              ║"
    fi

    # 헬스체크
    HEALTH=$(curl -s --max-time 2 http://127.0.0.1:$PORT/v1/health 2>/dev/null || echo "")
    if echo "$HEALTH" | grep -q '"ok"' 2>/dev/null || echo "$HEALTH" | grep -q '"status"' 2>/dev/null; then
      echo -e "║  헬스체크:    ${GREEN}정상${NC}                               ║"
    else
      echo -e "║  헬스체크:    ${RED}응답 없음${NC}                            ║"
    fi

    echo "╠══════════════════════════════════════════════╣"
    echo "║  접속: http://127.0.0.1:$PORT                   ║"
    echo "╚══════════════════════════════════════════════╝"
    echo ""
    ;;

  logs)
    print_status "실시간 로그 (Ctrl+C로 종료)..."
    tail -f "$LOG_FILE"
    ;;

  start|"")
    # ─── 시작 ───
    echo ""
    echo "╔══════════════════════════════════════════════╗"
    echo "║            Ssak-Ai 시작 중...                ║"
    echo "╚══════════════════════════════════════════════╝"
    echo ""

    # 1. venv 확인
    if [ ! -f "$UVICORN" ]; then
      print_err ".venv를 찾을 수 없습니다. python3 -m venv .venv && pip install -e . 실행 필요"
      exit 1
    fi

    # 2. 이미 실행 중인지 확인
    EXISTING_PID=$(lsof -ti:$PORT 2>/dev/null || true)
    if [ -n "$EXISTING_PID" ]; then
      print_warn "포트 $PORT가 이미 사용 중 (PID $EXISTING_PID). 기존 프로세스를 종료합니다."
      kill $EXISTING_PID 2>/dev/null || true
      sleep 2
    fi

    # 3. SearxNG 컨테이너 확인/시작
    print_status "SearxNG 확인 중..."
    if ! docker ps --filter name=$SEARXNG_NAME --format '{{.Names}}' 2>/dev/null | grep -q $SEARXNG_NAME; then
      if docker ps -a --filter name=$SEARXNG_NAME --format '{{.Names}}' 2>/dev/null | grep -q $SEARXNG_NAME; then
        docker start $SEARXNG_NAME >/dev/null 2>&1
        print_ok "SearxNG 컨테이너 재시작"
      else
        print_status "SearxNG 컨테이너 생성 중..."
        docker run -d --name $SEARXNG_NAME --restart=unless-stopped \
          -p 8080:8080 \
          -e SEARXNG_BASE_URL=http://localhost:8080/ \
          -e SEARXNG_SECRET=$(openssl rand -hex 16) \
          searxng/searxng:latest >/dev/null 2>&1
        sleep 3
        # JSON API 활성화
        docker exec $SEARXNG sh -c 'cat >> /etc/searxng/settings.yml << EOF

search:
  formats:
    - html
    - json
EOF' 2>/dev/null
        docker restart $SEARXNG_NAME >/dev/null 2>&1
        sleep 3
        print_ok "SearxNG 컨테이너 생성 + JSON API 활성화"
      fi
    else
      print_ok "SearxNG 이미 실행 중"
    fi

    # 4. .env에서 환경 변수 로드
    if [ -f "$PROJECT_ROOT/.env" ]; then
      set -a
      source "$PROJECT_ROOT/.env" 2>/dev/null || true
      set +a
    fi

    # 5. API 서버 시작
    print_status "API 서버 시작 중 (포트 $PORT)..."
    export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
    nohup "$UVICORN" antigravity_k.api.server:app \
      --host 127.0.0.1 --port $PORT \
      > "$LOG_FILE" 2>&1 &
    SERVER_PID=$!

    # 6. 서버 기동 대기
    print_status "서버 기동 대기 중..."
    for i in $(seq 1 15); do
      if curl -s --max-time 2 http://127.0.0.1:$PORT/v1/health 2>/dev/null | grep -q '"ok"\|"status"'; then
        print_ok "서버 기동 완료 (${i}초)"
        break
      fi
      sleep 1
    done

    # 7. 최종 상태 출력
    echo ""
    echo "╔══════════════════════════════════════════════════╗"
    echo "║                                                  ║"
    echo -e "║  ${GREEN}Ssak-Ai 실행 완료${NC}                             ║"
    echo "║                                                  ║"
    echo "║  🌐 대시보드:  http://127.0.0.1:$PORT               ║"
    echo "║  🔌 API:       http://127.0.0.1:$PORT/v1            ║"
    echo "║  🔍 SearxNG:   http://localhost:8080              ║"
    echo "║  📋 로그:      ./run.sh logs                     ║"
    echo "║  ⏹️  종료:      ./run.sh stop                     ║"
    echo "║  📊 상태:      ./run.sh status                   ║"
    echo "║                                                  ║"
    echo "╚══════════════════════════════════════════════════╝"
    echo ""
    ;;

  *)
    echo "사용법: ./run.sh [start|stop|status|logs]"
    echo ""
    echo "  start   (기본) API 서버 + SearxNG 시작"
    echo "  stop    서버 종료"
    echo "  status  실행 상태 확인"
    echo "  logs    실시간 로그 보기"
    ;;

esac
