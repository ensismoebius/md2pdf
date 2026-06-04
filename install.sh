#!/usr/bin/env bash
# md2pdf installer
# Installs Python dependencies, Node dependencies, and the Chromium headless
# binary required by the Mermaid CLI (mmdc).
#
# Usage:
#   bash install.sh           # install everything
#   bash install.sh --check   # only check what is already present
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHROME_VERSION="148.0.7778.97"
CHROME_DIR="$HOME/.cache/puppeteer/chrome-headless-shell/linux-${CHROME_VERSION}/chrome-headless-shell-linux64"
CHROME_BIN="$CHROME_DIR/chrome-headless-shell"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
ok()   { echo -e "${GREEN}  ✔${NC} $*"; }
warn() { echo -e "${YELLOW}  !${NC} $*"; }
err()  { echo -e "${RED}  ✘${NC} $*"; }
info() { echo -e "${CYAN}  →${NC} $*"; }

CHECK_ONLY=false
[[ "${1:-}" == "--check" ]] && CHECK_ONLY=true

echo ""
echo "  md2pdf installer"
echo "  ════════════════"
echo ""

# ── 1. Python ────────────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    err "python3 not found. Install Python 3.9+ first."
    exit 1
fi
PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
ok "Python $PY_VER found"

# ── 2. pip ───────────────────────────────────────────────────────────────────
if ! command -v pip3 &>/dev/null && ! python3 -m pip --version &>/dev/null 2>&1; then
    err "pip not found. Install pip first."
    exit 1
fi

if $CHECK_ONLY; then
    for pkg in weasyprint markdown pymdownx pygments; do
        if python3 -c "import ${pkg/pymdownx/pymdownx.superfences}" &>/dev/null 2>&1 || \
           python3 -c "import $pkg" &>/dev/null 2>&1; then
            ok "Python package: $pkg"
        else
            warn "Python package missing: $pkg"
        fi
    done
else
    info "Installing Python packages..."
    pip3 install --quiet weasyprint markdown pymdown-extensions pygments \
        ${PIP_EXTRA_FLAGS:-} 2>&1 | tail -3 || \
    pip3 install --quiet --break-system-packages \
        weasyprint markdown pymdown-extensions pygments 2>&1 | tail -3
    ok "Python packages installed"
fi

# ── 3. Node / npm ────────────────────────────────────────────────────────────
if ! command -v node &>/dev/null || ! command -v npm &>/dev/null; then
    err "node/npm not found. Install Node.js 18+ first (https://nodejs.org)."
    exit 1
fi
NODE_VER=$(node --version)
ok "Node $NODE_VER found"

if $CHECK_ONLY; then
    if [[ -x "$SCRIPT_DIR/node_modules/.bin/mmdc" ]]; then
        ok "mmdc found"
    else
        warn "mmdc not found (run install.sh without --check)"
    fi
else
    info "Installing Node packages..."
    cd "$SCRIPT_DIR"
    npm install --silent
    ok "Node packages installed"
fi

# ── 4. Chromium headless shell ───────────────────────────────────────────────
if $CHECK_ONLY; then
    if [[ -x "$CHROME_BIN" ]]; then
        ok "chrome-headless-shell found"
    else
        warn "chrome-headless-shell missing at: $CHROME_BIN"
    fi
else
    if [[ -x "$CHROME_BIN" ]]; then
        ok "chrome-headless-shell already present — skipping download"
    else
        info "Downloading Chromium headless shell $CHROME_VERSION (~113 MB)..."
        CHROME_URL="https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux64/chrome-headless-shell-linux64.zip"
        TMP_ZIP="$(mktemp /tmp/chrome-headless-shell-XXXXXX.zip)"

        if command -v curl &>/dev/null; then
            curl -fL --progress-bar "$CHROME_URL" -o "$TMP_ZIP"
        elif command -v wget &>/dev/null; then
            wget -q --show-progress "$CHROME_URL" -O "$TMP_ZIP"
        else
            err "Neither curl nor wget found. Cannot download Chromium."
            exit 1
        fi

        mkdir -p "$(dirname "$CHROME_DIR")"
        # Remove any incomplete previous extraction
        rm -rf "$(dirname "$CHROME_DIR")"
        mkdir -p "$(dirname "$CHROME_DIR")"
        unzip -q "$TMP_ZIP" -d "$(dirname "$CHROME_DIR")"
        chmod +x "$CHROME_BIN"
        rm -f "$TMP_ZIP"
        ok "chrome-headless-shell installed"
    fi
fi

# ── 5. Verify mmdc works ─────────────────────────────────────────────────────
if ! $CHECK_ONLY; then
    info "Verifying mmdc..."
    MMDC="$SCRIPT_DIR/node_modules/.bin/mmdc"
    if echo 'graph TD; A-->B' > /tmp/_md2pdf_test.mmd && \
       "$MMDC" -i /tmp/_md2pdf_test.mmd -o /tmp/_md2pdf_test.png &>/dev/null; then
        ok "mmdc works"
        rm -f /tmp/_md2pdf_test.mmd /tmp/_md2pdf_test.png
    else
        warn "mmdc test failed — Mermaid diagrams may not render"
    fi
fi

# ── 6. Summary ───────────────────────────────────────────────────────────────
echo ""
echo "  Installation complete."
echo ""
echo "  Usage:"
echo "    python3 $SCRIPT_DIR/md2pdf.py <docs-dir/>          # portrait, default margins"
echo "    python3 $SCRIPT_DIR/md2pdf.py <docs-dir/> out.pdf  # explicit output"
echo "    python3 $SCRIPT_DIR/md2pdf.py docs/ out.pdf -o l   # landscape"
echo "    python3 $SCRIPT_DIR/md2pdf.py docs/ out.pdf -m 15 10 20 10  # custom margins"
echo ""
echo "  Or add an alias to your shell:"
echo "    alias md2pdf='python3 $SCRIPT_DIR/md2pdf.py'"
echo ""
