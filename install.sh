#!/usr/bin/env sh
# Installs pmon-cli and ensures p-mon is on your PATH.
# Usage: sh install.sh
set -e

step() { printf '\033[36m  > %s\033[0m\n' "$1"; }
ok()   { printf '\033[32m  + %s\033[0m\n' "$1"; }
warn() { printf '\033[33m  ! %s\033[0m\n' "$1"; }

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
    printf '\n  Error: Python not found. Install it from https://python.org\n' >&2
    exit 1
fi
ok "Found $($PYTHON --version 2>&1)"

# ── 2. Install pmon-cli ───────────────────────────────────────────────────────
step "Installing pmon-cli (pip)..."
"$PYTHON" -m pip install --upgrade pmon-cli
ok "pmon-cli installed"

# ── 3. Find scripts directory ─────────────────────────────────────────────────
step "Locating scripts directory..."
SCRIPTS_DIR=$("$PYTHON" -c "import sysconfig; print(sysconfig.get_path('scripts'))")
ok "Scripts: $SCRIPTS_DIR"

# ── 4. Ensure directory is on PATH ────────────────────────────────────────────
case ":${PATH}:" in
    *":${SCRIPTS_DIR}:"*)
        ok "Already on PATH"
        printf '\n  Done. Run:  p-mon\n\n'
        exit 0
        ;;
esac

step "Adding $SCRIPTS_DIR to your shell profile..."

# Detect the right profile file
if [ -n "$ZSH_VERSION" ] || [ "$(basename "${SHELL:-}")" = "zsh" ]; then
    PROFILE="$HOME/.zshrc"
elif [ -f "$HOME/.bashrc" ]; then
    PROFILE="$HOME/.bashrc"
elif [ -f "$HOME/.bash_profile" ]; then
    PROFILE="$HOME/.bash_profile"
else
    PROFILE="$HOME/.profile"
fi

LINE="export PATH=\"${SCRIPTS_DIR}:\$PATH\""

if grep -qF "$SCRIPTS_DIR" "$PROFILE" 2>/dev/null; then
    ok "$PROFILE already references this directory"
else
    printf '\n# pmon-cli\n%s\n' "$LINE" >> "$PROFILE"
    ok "Added to $PROFILE"
fi

warn "Restart your terminal (or: source $PROFILE) for PATH to update."
printf '\n  Done. Run:  p-mon\n\n'
