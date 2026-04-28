#!/usr/bin/env sh
# Installs pmon-cli and ensures p-mon is on your PATH.
# Usage: sh install.sh
set -e

step() { printf '\033[36m  > %s\033[0m\n' "$1"; }
ok()   { printf '\033[32m  + %s\033[0m\n' "$1"; }
warn() { printf '\033[33m  ! %s\033[0m\n' "$1"; }
err()  { printf '\033[31m  Error: %s\033[0m\n' "$1" >&2; }

printf '\n  pmon-cli installer\n  ------------------\n\n'

# ── 1. Locate Python ──────────────────────────────────────────────────────────
step "Locating Python..."
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" >/dev/null 2>&1; then
        PYTHON="$cmd"
        break
    fi
done
if [ -z "$PYTHON" ]; then
    err "Python not found. Install it from https://python.org"
    exit 1
fi

# Validate version >= 3.9
PY_OK=$("$PYTHON" -c "import sys; print('ok' if sys.version_info >= (3,9) else 'old')" 2>/dev/null || echo "old")
if [ "$PY_OK" != "ok" ]; then
    err "Python 3.9+ is required. Found: $("$PYTHON" --version 2>&1)"
    exit 1
fi
ok "Found $("$PYTHON" --version 2>&1)"

# ── 2. Check pip ──────────────────────────────────────────────────────────────
step "Checking pip..."
if ! "$PYTHON" -m pip --version >/dev/null 2>&1; then
    err "pip not available. Try: $PYTHON -m ensurepip --upgrade"
    exit 1
fi
ok "pip available"

# ── 3. Install pmon-cli ───────────────────────────────────────────────────────
step "Installing pmon-cli (pip)..."
# Capture output so we can detect PEP 668 (externally-managed-environment).
# set -e is active so we temporarily disable it around the pip call.
set +e
INSTALL_OUT=$("$PYTHON" -m pip install --upgrade pmon-cli 2>&1)
INSTALL_RC=$?
set -e

if [ $INSTALL_RC -ne 0 ]; then
    if echo "$INSTALL_OUT" | grep -q "externally-managed-environment"; then
        warn "System Python is externally managed (PEP 668). Retrying with --user..."
        set +e
        "$PYTHON" -m pip install --upgrade --user pmon-cli 2>&1
        INSTALL_RC=$?
        set -e
        if [ $INSTALL_RC -ne 0 ]; then
            err "pip install --user also failed. Try: pipx install pmon-cli"
            exit 1
        fi
    else
        err "pip install failed:"
        printf '%s\n' "$INSTALL_OUT" >&2
        exit 1
    fi
fi
ok "pmon-cli installed"

# ── 4. Find scripts directory ─────────────────────────────────────────────────
# pip may install to the system scripts dir or the user scripts dir depending on
# whether the system site-packages is writable.  Check both.
step "Locating scripts directory..."
SCRIPTS_DIR=""

# Build list of candidates: system dir, then user dirs (Linux ~/.local/bin and
# macOS ~/Library/Python/X.Y/bin), then the sysconfig user-scheme path.
SYS_SCRIPTS=$("$PYTHON" -c "import sysconfig; print(sysconfig.get_path('scripts'))" 2>/dev/null || true)
PY_MINOR=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || true)
USER_SCHEME_SCRIPTS=$("$PYTHON" -c "
import sys, sysconfig
if sys.version_info >= (3, 10):
    scheme = sysconfig.get_preferred_scheme('user')
elif sys.platform == 'darwin':
    scheme = 'osx_framework_user'
else:
    scheme = 'posix_user'
print(sysconfig.get_path('scripts', scheme))
" 2>/dev/null || true)

for candidate in \
    "$SYS_SCRIPTS" \
    "$HOME/.local/bin" \
    "$HOME/Library/Python/${PY_MINOR}/bin" \
    "$USER_SCHEME_SCRIPTS"; do
    if [ -n "$candidate" ] && [ -f "$candidate/p-mon" ]; then
        SCRIPTS_DIR="$candidate"
        break
    fi
done

if [ -z "$SCRIPTS_DIR" ]; then
    warn "Could not locate p-mon after install."
    warn "Run 'python -m project_monitor' as a fallback."
    exit 0
fi
ok "Scripts: $SCRIPTS_DIR"

# ── 5. Ensure directory is on PATH ────────────────────────────────────────────
case ":${PATH}:" in
    *":${SCRIPTS_DIR}:"*)
        ok "Already on PATH"
        printf '\n  Done. Run:  p-mon\n\n'
        exit 0
        ;;
esac

step "Adding $SCRIPTS_DIR to your shell profile..."

# Detect the right profile file (including fish)
SHELL_NAME="$(basename "${SHELL:-}")"
if [ -n "$FISH_VERSION" ] || [ "$SHELL_NAME" = "fish" ]; then
    PROFILE="$HOME/.config/fish/config.fish"
    LINE="fish_add_path $SCRIPTS_DIR"
elif [ -n "$ZSH_VERSION" ] || [ "$SHELL_NAME" = "zsh" ]; then
    PROFILE="$HOME/.zshrc"
    LINE="export PATH=\"${SCRIPTS_DIR}:\$PATH\""
elif [ -f "$HOME/.bashrc" ]; then
    PROFILE="$HOME/.bashrc"
    LINE="export PATH=\"${SCRIPTS_DIR}:\$PATH\""
elif [ -f "$HOME/.bash_profile" ]; then
    PROFILE="$HOME/.bash_profile"
    LINE="export PATH=\"${SCRIPTS_DIR}:\$PATH\""
else
    PROFILE="$HOME/.profile"
    LINE="export PATH=\"${SCRIPTS_DIR}:\$PATH\""
fi

if grep -qF "$SCRIPTS_DIR" "$PROFILE" 2>/dev/null; then
    ok "$PROFILE already references this directory"
else
    printf '\n# pmon-cli\n%s\n' "$LINE" >> "$PROFILE"
    ok "Added to $PROFILE"
fi

warn "Restart your terminal (or: source $PROFILE) for PATH to update."
printf '\n  Done. Run:  p-mon\n\n'
