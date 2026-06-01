#!/usr/bin/env bash
#
# Bootstrap Multica outbound integration for daily-scheduler.
#
# Creates (or reuses) a Multica user, workspace, and Personal Access Token via
# the self-host API, then writes MULTICA_API_TOKEN + MULTICA_WORKSPACE_ID into
# the project .env. The email verification code is read from the multica
# backend container logs (self-host prints it there when no email provider is
# configured).
#
# Prerequisites: the Multica stack must be running (`make multica-up`).
#
# Usage:
#   bash scripts/multica-bootstrap.sh [bot-email] [workspace-name] [workspace-slug]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT/.env"
BASE_URL="${MULTICA_BASE_URL:-http://localhost:8080}"
BACKEND_CONTAINER="${MULTICA_BACKEND_CONTAINER:-multica-backend-1}"

BOT_EMAIL="${1:-scheduler-bot@daily-scheduler.local}"
WS_NAME="${2:-Daily Scheduler Council}"
WS_SLUG="${3:-daily-scheduler}"

log()  { printf '  \033[36m[bootstrap]\033[0m %s\n' "$*"; }
err()  { printf '  \033[31m[bootstrap]\033[0m %s\n' "$*" >&2; }
jget() { python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('$1','') if isinstance(d,dict) else '')"; }

curl -fsS -o /dev/null --max-time 5 "$BASE_URL/healthz" || {
  err "Multica backend not reachable at $BASE_URL. Run: make multica-up"
  exit 1
}

log "Requesting verification code for $BOT_EMAIL …"
curl -fsS -X POST --max-time 8 -H "Content-Type: application/json" \
  -d "{\"email\":\"$BOT_EMAIL\"}" "$BASE_URL/auth/send-code" >/dev/null

# The self-host backend logs: "[DEV] Verification code for <email>: 123456"
CODE="$(docker logs --since 30s "$BACKEND_CONTAINER" 2>&1 \
  | grep -aoE "Verification code for ${BOT_EMAIL}: [0-9]{6}" | tail -1 | grep -oE '[0-9]{6}' || true)"
if [ -z "$CODE" ]; then
  err "Could not read the verification code from '$BACKEND_CONTAINER' logs."
  err "If you use a real email provider, fetch the code from the inbox and run verify-code manually."
  exit 1
fi
log "Verification code: $CODE"

JWT="$(curl -fsS -X POST --max-time 8 -H "Content-Type: application/json" \
  -d "{\"email\":\"$BOT_EMAIL\",\"code\":\"$CODE\"}" "$BASE_URL/auth/verify-code" | jget token)"
[ -n "$JWT" ] || { err "verify-code did not return a token"; exit 1; }
log "Authenticated."

WSID="$(curl -fsS --max-time 8 -H "Authorization: Bearer $JWT" "$BASE_URL/api/workspaces" \
  | python3 -c "import sys,json
d=json.load(sys.stdin)
items=d if isinstance(d,list) else d.get('workspaces') or d.get('items') or []
print(items[0]['id'] if items else '')")"
if [ -z "$WSID" ]; then
  log "Creating workspace '$WS_NAME' ($WS_SLUG) …"
  WSID="$(curl -fsS -X POST --max-time 8 -H "Authorization: Bearer $JWT" -H "Content-Type: application/json" \
    -d "{\"name\":\"$WS_NAME\",\"slug\":\"$WS_SLUG\"}" "$BASE_URL/api/workspaces" | jget id)"
fi
[ -n "$WSID" ] || { err "could not resolve a workspace id"; exit 1; }
log "Workspace: $WSID"

PAT="$(curl -fsS -X POST --max-time 8 -H "Authorization: Bearer $JWT" -H "Content-Type: application/json" \
  -d '{"name":"daily-scheduler"}' "$BASE_URL/api/tokens" | jget token)"
[ -n "$PAT" ] || { err "token creation did not return a token"; exit 1; }
log "Personal Access Token created (${PAT:0:12}…)."

# Upsert the two keys into .env.
touch "$ENV_FILE"
python3 - "$ENV_FILE" "$PAT" "$WSID" <<'PY'
import sys
path, pat, wsid = sys.argv[1], sys.argv[2], sys.argv[3]
lines = open(path, encoding="utf-8").read().splitlines()
vals = {"MULTICA_API_TOKEN": pat, "MULTICA_WORKSPACE_ID": wsid}
seen = set()
out = []
for line in lines:
    key = line.split("=", 1)[0].strip() if "=" in line else None
    if key in vals:
        out.append(f"{key}={vals[key]}")
        seen.add(key)
    else:
        out.append(line)
for key, val in vals.items():
    if key not in seen:
        out.append(f"{key}={val}")
open(path, "w", encoding="utf-8").write("\n".join(out) + "\n")
PY

log "Wrote MULTICA_API_TOKEN + MULTICA_WORKSPACE_ID to $ENV_FILE"
log "Verifying issue creation …"
RESP="$(curl -fsS -X POST --max-time 8 -H "Authorization: Bearer $PAT" -H "X-Workspace-ID: $WSID" \
  -H "Content-Type: application/json" \
  -d '{"title":"[bootstrap] daily-scheduler connected","description":"Outbound integration verified.","priority":"low"}' \
  "$BASE_URL/api/issues")"
IDENT="$(printf '%s' "$RESP" | jget identifier)"
log "Created issue ${IDENT:-?} — Multica outbound integration is live."
