#!/usr/bin/env bash
#
# Register THIS machine as a Multica runtime so the council agents can execute
# tasks. A runtime can only be registered by the `multica` daemon (there is no
# REST endpoint for it), so this script:
#   1. ensures the `multica` CLI is installed,
#   2. points it at the local self-host server,
#   3. logs in with the bot Personal Access Token from .env (no browser OAuth),
#   4. starts the background daemon, which auto-registers a runtime for each
#      detected agent CLI (claude, codex, …).
#
# Prerequisites: the Multica stack is up (`make multica-up`) and .env has
# MULTICA_API_TOKEN (run `make multica-bootstrap` once).
#
# Usage: bash scripts/multica-runtime.sh   (or: make multica-runtime)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT/.env"

log()  { printf '  \033[36m[runtime]\033[0m %s\n' "$*"; }
warn() { printf '  \033[33m[runtime]\033[0m %s\n' "$*" >&2; }
err()  { printf '  \033[31m[runtime]\033[0m %s\n' "$*" >&2; }

envget() { [ -f "$ENV_FILE" ] && grep -E "^$1=" "$ENV_FILE" | tail -1 | cut -d= -f2- | sed 's/[[:space:]]*#.*$//' || true; }

BASE_URL="${MULTICA_BASE_URL:-$(envget MULTICA_BASE_URL)}"; BASE_URL="${BASE_URL:-http://localhost:8080}"
WEB_URL="${MULTICA_WEB_URL:-$(envget MULTICA_WEB_URL)}";   WEB_URL="${WEB_URL:-http://localhost:3001}"
PAT="$(envget MULTICA_API_TOKEN)"

[ -n "$PAT" ] || { err "MULTICA_API_TOKEN missing in .env — run 'make multica-bootstrap' first."; exit 1; }
curl -fsS -o /dev/null --max-time 5 "$BASE_URL/healthz" || { err "Multica not reachable at $BASE_URL. Run 'make multica-up'."; exit 1; }

# --- 1. locate or install the multica CLI -------------------------------------
find_cli() {
  if command -v multica >/dev/null 2>&1; then command -v multica; return; fi
  for p in "$HOME/.local/bin/multica" "/usr/local/bin/multica" "$HOME/.multica/server/server/bin/multica"; do
    [ -x "$p" ] && { printf '%s' "$p"; return; }
  done
  printf ''
}

MULTICA_BIN="$(find_cli)"
if [ -z "$MULTICA_BIN" ]; then
  warn "multica CLI not found — installing via the official installer…"
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL https://raw.githubusercontent.com/multica-ai/multica/main/scripts/install.sh | bash || true
  fi
  MULTICA_BIN="$(find_cli)"
fi
[ -n "$MULTICA_BIN" ] || {
  err "Could not install the multica CLI automatically."
  err "Install it manually (https://github.com/multica-ai/multica) then re-run, e.g.:"
  err "  brew install multica-ai/tap/multica"
  err "  # or build from source: git clone … && cd multica/server && go build -o ~/.local/bin/multica ./cmd/multica"
  exit 1
}
log "multica CLI: $MULTICA_BIN"

# --- 2. configure + 3. authenticate -------------------------------------------
log "Configuring CLI for self-host ($BASE_URL / $WEB_URL)…"
"$MULTICA_BIN" setup self-host --server-url "$BASE_URL" --app-url "$WEB_URL" </dev/null >/dev/null 2>&1 || true
log "Logging in with the bot token…"
"$MULTICA_BIN" login --token "$PAT" >/dev/null

# --- 4. start the daemon (idempotent) -----------------------------------------
if "$MULTICA_BIN" daemon status >/dev/null 2>&1; then
  log "Daemon already running — restarting to refresh runtimes…"
  "$MULTICA_BIN" daemon restart >/dev/null 2>&1 || "$MULTICA_BIN" daemon start >/dev/null
else
  log "Starting the runtime daemon…"
  "$MULTICA_BIN" daemon start >/dev/null
fi

sleep 3
log "Registered runtimes:"
"$MULTICA_BIN" runtime list 2>/dev/null | sed 's/^/    /' | head -8
log "Done. The daemon keeps this machine online so agents can execute tasks."
log "Next: make multica-register-agents   (create the council agents + squad)"
