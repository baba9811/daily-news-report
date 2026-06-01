#!/usr/bin/env bash
#
# Invite a human into the daily-scheduler Multica council workspace.
#
# Uses the official Multica members API (POST /api/workspaces/{id}/members)
# authenticated with the bot Personal Access Token from .env. The API creates a
# *pending invitation* — the invitee then signs into the Multica board with that
# email and accepts the invitation to become a member. No direct database writes.
#
# Prerequisites:
#   - The Multica stack is running (`make multica-up`).
#   - .env contains MULTICA_API_TOKEN + MULTICA_WORKSPACE_ID
#     (run `make multica-bootstrap` once if it does not).
#
# Usage:
#   bash scripts/multica-add-member.sh <email> [role]
#   make multica-add-member EMAIL=you@example.com ROLE=admin
#
# role defaults to "admin"; accepts "admin" or "member".
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT/.env"

log() { printf '  \033[36m[member]\033[0m %s\n' "$*"; }
err() { printf '  \033[31m[member]\033[0m %s\n' "$*" >&2; }

# Read a KEY=value from .env (last definition wins); empty when absent.
envget() { [ -f "$ENV_FILE" ] && grep -E "^$1=" "$ENV_FILE" | tail -1 | cut -d= -f2- || true; }

EMAIL="${1:-${EMAIL:-}}"
ROLE="${2:-${ROLE:-admin}}"

if [ -z "$EMAIL" ]; then
  err "Usage: bash scripts/multica-add-member.sh <email> [admin|member]"
  err "   or: make multica-add-member EMAIL=you@example.com ROLE=admin"
  exit 2
fi
case "$ROLE" in
  admin | member) ;;
  *)
    err "role must be 'admin' or 'member' (got '$ROLE')"
    exit 2
    ;;
esac

BASE_URL="${MULTICA_BASE_URL:-$(envget MULTICA_BASE_URL)}"
BASE_URL="${BASE_URL:-http://localhost:8080}"
WEB_URL="${MULTICA_WEB_URL:-$(envget MULTICA_WEB_URL)}"
WEB_URL="${WEB_URL:-http://localhost:3001}"
PAT="$(envget MULTICA_API_TOKEN)"
WSID="$(envget MULTICA_WORKSPACE_ID)"

if [ -z "$PAT" ] || [ -z "$WSID" ]; then
  err "MULTICA_API_TOKEN / MULTICA_WORKSPACE_ID missing in .env."
  err "Run 'make multica-bootstrap' first to provision the bot token + workspace."
  exit 1
fi

curl -fsS -o /dev/null --max-time 5 "$BASE_URL/healthz" || {
  err "Multica backend not reachable at $BASE_URL. Run: make multica-up"
  exit 1
}

log "Inviting $EMAIL as '$ROLE' to workspace $WSID …"
RESP="$(curl -s -w $'\n%{http_code}' --max-time 8 -X POST \
  -H "Authorization: Bearer $PAT" -H "X-Workspace-ID: $WSID" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"role\":\"$ROLE\"}" \
  "$BASE_URL/api/workspaces/$WSID/members")"
CODE="$(printf '%s' "$RESP" | tail -1)"
BODY="$(printf '%s' "$RESP" | sed '$d')"

case "$CODE" in
  200 | 201)
    log "Invitation created (pending). ✅"
    log "Next: ask $EMAIL to open $WEB_URL, sign in with that email,"
    log "      and accept the pending invitation to join the council workspace."
    ;;
  409)
    log "$EMAIL is already a member — nothing to do. ✅"
    ;;
  *)
    err "Failed (HTTP $CODE): $BODY"
    exit 1
    ;;
esac
