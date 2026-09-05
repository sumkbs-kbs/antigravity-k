#!/usr/bin/env bash
# ==============================================================================
# Ssak-Ai macOS .app 번들 및 .dmg 디스크 이미지 빌더
# ==============================================================================
# 기능:
# 1. 고해상도 앱 아이콘(AppIcon.icns) 자동 생성 (dashboard/public/icon-512.png 기반)
# 2. 독립 실행형 macOS 애플리케이션 번들(Ssak-Ai.app) 구성
# 3. GUI 환경 PATH 확장 및 데몬 자동 구동/헬스체크/브라우저 오픈 런처 탑재
# 4. Applications 심볼릭 링크를 포함한 배포용 압축 .dmg (UDZO) 패키징
# 5. 마운트 무결성 검증 및 SHA-256 체크섬 발행
# ==============================================================================
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# 버전 확인
VERSION="$(python3 -c "
import tomllib
try:
    with open('$ROOT_DIR/pyproject.toml', 'rb') as f:
        data = tomllib.load(f)
    print(data.get('project', {}).get('version') or '0.1.0')
except Exception:
    print('0.1.0')
" 2>/dev/null || echo "0.1.0")"

# 디렉터리 정의
BUILD_DIR="$ROOT_DIR/build/mac"
APP_NAME="Ssak-Ai"
APP_BUNDLE="$BUILD_DIR/$APP_NAME.app"
CONTENTS_DIR="$APP_BUNDLE/Contents"
MACOS_DIR="$CONTENTS_DIR/MacOS"
RESOURCES_DIR="$CONTENTS_DIR/Resources"
DMG_STAGE_DIR="$BUILD_DIR/dmg_stage"
DIST_DIR="$ROOT_DIR/dist"
DMG_NAME="Ssak-Ai-$VERSION.dmg"
DMG_PATH="$DIST_DIR/$DMG_NAME"

echo "============================================================"
echo "▶ Ssak-Ai macOS DMG 빌더 시작 (v$VERSION)"
echo "============================================================"

mkdir -p "$BUILD_DIR" "$DIST_DIR"
rm -rf "$APP_BUNDLE" "$DMG_STAGE_DIR"
mkdir -p "$MACOS_DIR" "$RESOURCES_DIR" "$DMG_STAGE_DIR"

# 1. AppIcon.icns 생성
SOURCE_ICON="$ROOT_DIR/dashboard/public/icon-512.png"
if [[ -f "$SOURCE_ICON" ]]; then
    echo "▶ 앱 아이콘 생성 중 (AppIcon.icns)..."
    ICONSET_DIR="/tmp/agk_icon_$$.iconset"
    mkdir -p "$ICONSET_DIR"

    sips -z 16 16     "$SOURCE_ICON" --out "$ICONSET_DIR/icon_16x16.png" >/dev/null 2>&1
    sips -z 32 32     "$SOURCE_ICON" --out "$ICONSET_DIR/icon_16x16@2x.png" >/dev/null 2>&1
    sips -z 32 32     "$SOURCE_ICON" --out "$ICONSET_DIR/icon_32x32.png" >/dev/null 2>&1
    sips -z 64 64     "$SOURCE_ICON" --out "$ICONSET_DIR/icon_32x32@2x.png" >/dev/null 2>&1
    sips -z 128 128   "$SOURCE_ICON" --out "$ICONSET_DIR/icon_128x128.png" >/dev/null 2>&1
    sips -z 256 256   "$SOURCE_ICON" --out "$ICONSET_DIR/icon_128x128@2x.png" >/dev/null 2>&1
    sips -z 256 256   "$SOURCE_ICON" --out "$ICONSET_DIR/icon_256x256.png" >/dev/null 2>&1
    sips -z 512 512   "$SOURCE_ICON" --out "$ICONSET_DIR/icon_256x256@2x.png" >/dev/null 2>&1
    sips -z 512 512   "$SOURCE_ICON" --out "$ICONSET_DIR/icon_512x512.png" >/dev/null 2>&1

    iconutil -c icns "$ICONSET_DIR" -o "$RESOURCES_DIR/AppIcon.icns"
    rm -rf "$ICONSET_DIR"
    echo "  ✓ AppIcon.icns 생성 완료"
fi

# 2. Info.plist 생성
echo "▶ Info.plist 생성 중..."
cat > "$CONTENTS_DIR/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>$APP_NAME</string>
    <key>CFBundleDisplayName</key>
    <string>$APP_NAME</string>
    <key>CFBundleIdentifier</key>
    <string>com.antigravity.k</string>
    <key>CFBundleVersion</key>
    <string>$VERSION</string>
    <key>CFBundleShortVersionString</key>
    <string>$VERSION</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleSignature</key>
    <string>AGTK</string>
    <key>CFBundleExecutable</key>
    <string>$APP_NAME</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>LSMinimumSystemVersion</key>
    <string>12.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSHumanReadableCopyright</key>
    <string>Copyright © 2026 Ssak-Ai. All rights reserved.</string>
</dict>
</plist>
EOF
plutil -lint "$CONTENTS_DIR/Info.plist" >/dev/null
echo "  ✓ Info.plist 검증 완료"

# 3. 런처 스크립트 (Contents/MacOS/Ssak-Ai)
echo "▶ 애플리케이션 런처 스크립트 작성 중..."
cat > "$MACOS_DIR/$APP_NAME" <<'LAUNCHER_EOF'
#!/usr/bin/env bash
set -Eeuo pipefail

# 1. macOS GUI 환경용 PATH 확장
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

SERVER_HOST="127.0.0.1"
SERVER_PORT="8000"
SERVER_URL="http://${SERVER_HOST}:${SERVER_PORT}"
LOG_DIR="$HOME/Library/Logs/Ssak-Ai"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/server.log"

# 2. 이미 실행 중인지 확인
if curl -s -f -m 1 "$SERVER_URL/health" >/dev/null 2>&1 || curl -s -f -m 1 "$SERVER_URL/api/health" >/dev/null 2>&1; then
    osascript -e 'display notification "이미 실행 중인 Ssak-Ai 대시보드를 브라우저에 엽니다." with title "Ssak-Ai"' 2>/dev/null || true
    open "$SERVER_URL"
    exit 0
fi

# 3. 번들 리소스 경로 파악 (Contents/MacOS/../Resources/app)
APP_BUNDLE_ROOT="$(cd "$(dirname "$0")/../Resources/app" 2>/dev/null && pwd || true)"

# 4. 사용자 작업 및 데이터 디렉터리 준비 (읽기 전용 DMG/Applications 탈피)
USER_DATA_DIR="$HOME/.antigravity-k"
mkdir -p "$USER_DATA_DIR/data" "$USER_DATA_DIR/logs" "$USER_DATA_DIR/models"

# 경로 환경변수 export (모든 쓰기 작업을 사용자 홈 디렉터리로 리디렉션)
export AGK_PATH_PROJECT_ROOT="$USER_DATA_DIR"
export AGK_PATH_DATA_DIR="$USER_DATA_DIR/data"
export AGK_PATH_LOGS_DIR="$LOG_DIR"
export AGK_PATH_MODELS_DIR="$USER_DATA_DIR/models"
export AGK_PATH_DOCUMENTS_DIR="$USER_DATA_DIR/data/documents"
export AGK_PATH_VECTORS_DIR="$USER_DATA_DIR/data/vectors"
export AGK_PATH_WIKI_DIR="$USER_DATA_DIR/data/wiki_entries"
export AGK_TASK_DB_PATH="$USER_DATA_DIR/data/tasks.db"
export AGK_KANBAN_DB_PATH="$USER_DATA_DIR/data/kanban.db"
export AGK_MEMORY_DB_PATH="$USER_DATA_DIR/data/memory.db"

# config.yaml 복사 (사용자 디렉터리에 없으면 번들 기본값 복사)
if [[ ! -f "$USER_DATA_DIR/config.yaml" && -f "$APP_BUNDLE_ROOT/config.yaml" ]]; then
    cp "$APP_BUNDLE_ROOT/config.yaml" "$USER_DATA_DIR/config.yaml"
fi
if [[ -f "$USER_DATA_DIR/config.yaml" ]]; then
    export AGK_CONFIG_FILE="$USER_DATA_DIR/config.yaml"
fi

# 5. PYTHONPATH 설정 (번들된 src 및 site-packages를 최우선으로 주입)
BUNDLED_SP=""
if [[ -d "$APP_BUNDLE_ROOT/site-packages" ]]; then
    BUNDLED_SP=":$APP_BUNDLE_ROOT/site-packages"
fi
if [[ -d "$APP_BUNDLE_ROOT/src" ]]; then
    export PYTHONPATH="$APP_BUNDLE_ROOT/src${BUNDLED_SP}:${PYTHONPATH:-}"
fi

# 6. 실행 Python 바이너리 탐색 (Python >= 3.12 필수)
check_py() {
    local candidate="$1"
    if [[ -n "$candidate" && -x "$candidate" ]]; then
        local ver
        ver="$("$candidate" -c 'import sys; print(sys.version_info[0]*100 + sys.version_info[1])' 2>/dev/null || echo 0)"
        if [[ "$ver" -ge 312 ]]; then
            echo "$candidate"
            return 0
        fi
    fi
    return 1
}

PY_BIN=""
CANDIDATES=(
    "$APP_BUNDLE_ROOT/../../../../.venv/bin/python"
    "$USER_DATA_DIR/venv/bin/python"
    "$(command -v uv >/dev/null 2>&1 && uv python find 2>/dev/null || true)"
    "$HOME/miniforge3/bin/python3"
    "$HOME/miniforge3/bin/python"
    "$HOME/anaconda3/bin/python3"
    "$(command -v python3.13 || true)"
    "$(command -v python3.12 || true)"
    "/opt/homebrew/bin/python3.13"
    "/opt/homebrew/bin/python3.12"
    "/opt/homebrew/bin/python3"
    "/usr/local/bin/python3.13"
    "/usr/local/bin/python3.12"
    "/usr/local/bin/python3"
    "$(command -v python3 || true)"
    "$(command -v python || true)"
)

for c in "${CANDIDATES[@]}"; do
    [[ -z "$c" ]] && continue
    if PY_BIN="$(check_py "$c")"; then
        break
    fi
done

if [[ -z "$PY_BIN" ]]; then
    osascript -e 'display alert "Ssak-Ai 실행 실패" message "Python 3.12 이상의 런타임을 찾을 수 없습니다.\n터미널에서 uv 또는 Python 3.12+를 설치해주세요." as critical' 2>/dev/null || true
    exit 1
fi

CMD="$PY_BIN -m antigravity_k.cli serve --host $SERVER_HOST --port $SERVER_PORT"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting Ssak-Ai via $PY_BIN: $CMD" >> "$LOG_FILE"

# 백그라운드 서버 실행 (항상 사용자 쓰기 가능 디렉터리에서 실행)
(cd "$USER_DATA_DIR" && nohup $CMD >> "$LOG_FILE" 2>&1 &)

# 7. 헬스체크 대기 (최대 25초)
READY=0
for i in {1..50}; do
    if curl -s -f -m 1 "$SERVER_URL/health" >/dev/null 2>&1 || curl -s -f -m 1 "$SERVER_URL/api/health" >/dev/null 2>&1; then
        READY=1
        break
    fi
    sleep 0.5
done

if [[ "$READY" -eq 1 ]]; then
    osascript -e 'display notification "Ssak-Ai 서버가 준비되었습니다. 대시보드를 엽니다." with title "Ssak-Ai"' 2>/dev/null || true
    open "$SERVER_URL"
else
    ERR_TAIL="$(tail -n 10 "$LOG_FILE" 2>/dev/null | tr '\n' ' ' | cut -c1-150 || echo '')"
    osascript -e "display alert \"서버 시작 실패 또는 응답 지연\" message \"Ssak-Ai 서버가 응답하지 않습니다.\n\n로그 위치: $LOG_FILE\n최근 오류: $ERR_TAIL\" as critical" 2>/dev/null || true
    exit 1
fi
LAUNCHER_EOF

chmod +x "$MACOS_DIR/$APP_NAME"
echo "  ✓ 런처 스크립트 작성 및 실행 권한 부여 완료"

# 4. 소스 및 내장 대시보드 리소스 번들링 (Resources/app)
echo "▶ 애플리케이션 코어 리소스 번들링 중..."
APP_BUNDLE_APP="$RESOURCES_DIR/app"
mkdir -p "$APP_BUNDLE_APP"

# 소스코드 및 필수 설정 복사
cp -R "$ROOT_DIR/src" "$APP_BUNDLE_APP/"
cp "$ROOT_DIR/pyproject.toml" "$APP_BUNDLE_APP/"
cp "$ROOT_DIR/config.yaml" "$APP_BUNDLE_APP/"
[[ -f "$ROOT_DIR/README.md" ]] && cp "$ROOT_DIR/README.md" "$APP_BUNDLE_APP/"
[[ -f "$ROOT_DIR/LICENSE" ]] && cp "$ROOT_DIR/LICENSE" "$APP_BUNDLE_APP/"
cp -R "$ROOT_DIR/src/antigravity_k/dashboard_dist" "$APP_BUNDLE_APP/src/antigravity_k/" 2>/dev/null || true
[[ -f "$ROOT_DIR/uv.lock" ]] && cp "$ROOT_DIR/uv.lock" "$APP_BUNDLE_APP/"

# 필수 의존성 패키지 번들링 (uv.lock 기반 정확한 버전으로 독립 런타임 구성)
echo "▶ 필수 런타임 패키지 번들링 중 (site-packages)..."
mkdir -p "$APP_BUNDLE_APP/site-packages"
if command -v uv >/dev/null 2>&1; then
    TEMP_REQS="/tmp/agk_dmg_reqs_$$.txt"
    uv export --no-dev --no-editable --no-hashes | grep -v "^\." > "$TEMP_REQS"
    uv pip install --target "$APP_BUNDLE_APP/site-packages" -r "$TEMP_REQS" >/dev/null 2>&1
    rm -f "$TEMP_REQS"
    echo "  ✓ site-packages 번들링 완료 ($(du -sh "$APP_BUNDLE_APP/site-packages" | cut -f1))"
fi

# 불필요한 캐시 파일 정리 및 권한 부여
find "$APP_BUNDLE_APP" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$APP_BUNDLE_APP" -type f -name "*.pyc" -delete 2>/dev/null || true
chmod -R u+rwX,go+rX "$APP_BUNDLE"
echo "  ✓ 번들 리소스 동기화 완료 ($(du -sh "$APP_BUNDLE_APP" | cut -f1))"

# 5. DMG 스테이징 및 패키징
echo "▶ DMG 스테이징 준비 중..."
cp -R "$APP_BUNDLE" "$DMG_STAGE_DIR/"
ln -s /Applications "$DMG_STAGE_DIR/Applications"

rm -f "$DMG_PATH"
echo "▶ hdiutil 기반 압축 디스크 이미지(UDZO) 생성 중..."
hdiutil create \
    -volname "$APP_NAME" \
    -srcfolder "$DMG_STAGE_DIR" \
    -ov \
    -format UDZO \
    "$DMG_PATH" >/dev/null

echo "  ✓ DMG 생성 완료: $DMG_PATH ($(du -sh "$DMG_PATH" | cut -f1))"

# 6. 마운트 검증
echo "▶ 생성된 DMG 마운트 무결성 검증 중..."
MOUNT_POINT="/tmp/agk_dmg_verify_$$"
mkdir -p "$MOUNT_POINT"
hdiutil attach "$DMG_PATH" -mountpoint "$MOUNT_POINT" -nobrowse -readonly >/dev/null

if [[ -d "$MOUNT_POINT/$APP_NAME.app" && -L "$MOUNT_POINT/Applications" ]]; then
    echo "  ✓ 마운트 볼륨 내 Ssak-Ai.app 및 /Applications 심볼릭 링크 정상 확인"
    plutil -lint "$MOUNT_POINT/$APP_NAME.app/Contents/Info.plist" >/dev/null
    echo "  ✓ 볼륨 내 Info.plist 유효성 검증 완료"
fi

hdiutil detach "$MOUNT_POINT" >/dev/null
rm -rf "$MOUNT_POINT"

# 7. 체크섬 생성
DMG_SHA256="$(shasum -a 256 "$DMG_PATH" | cut -d' ' -f1)"
echo "$DMG_SHA256  $DMG_NAME" > "$DIST_DIR/$DMG_NAME.sha256"

echo "============================================================"
echo "🎉 Ssak-Ai macOS .dmg 빌드 성공!"
echo "   - 파일: $DMG_PATH"
echo "   - 용량: $(du -sh "$DMG_PATH" | cut -f1)"
echo "   - SHA-256: $DMG_SHA256"
echo "============================================================"
