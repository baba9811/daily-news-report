#!/usr/bin/env python3
"""Register the daily-scheduler investment council in Multica (idempotent).

Creates workspace-visible agents (mapped onto the live claude/codex runtimes),
an "Investment Council" squad, and a reporting skill, so the whole Multica
workspace can see and run the trading team. Re-running only fills in what's
missing.

Prerequisites:
  1. The Multica stack is up (`make multica-up`).
  2. A PAT + workspace exist (`make multica-bootstrap` writes them to .env).
  3. The runtime daemon is registered (`make multica-runtime` / `multica daemon
     start`) so claude/codex runtimes are online.

Reads MULTICA_BASE_URL / MULTICA_API_TOKEN / MULTICA_WORKSPACE_ID from the
environment or the project .env. Stdlib only — no third-party deps.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_env() -> dict[str, str]:
    """Merge os.environ over the project .env (os.environ wins)."""
    values: dict[str, str] = {}
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            values[key.strip()] = val.split("#", 1)[0].strip()
    values.update({k: v for k, v in os.environ.items() if v})
    return values


ENV = load_env()
BASE = ENV.get("MULTICA_BASE_URL", "http://localhost:8080").rstrip("/")
TOKEN = ENV.get("MULTICA_API_TOKEN", "")
WORKSPACE = ENV.get("MULTICA_WORKSPACE_ID", "")


def die(msg: str) -> None:
    sys.stderr.write(f"  \033[31m[agents]\033[0m {msg}\n")
    sys.exit(1)


def log(msg: str) -> None:
    sys.stdout.write(f"  \033[36m[agents]\033[0m {msg}\n")


def api(method: str, path: str, body: dict | None = None) -> tuple[int, object]:
    """Call the Multica API with PAT + workspace headers. Returns (status, json)."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{BASE}{path}", data=data, method=method)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("X-Workspace-ID", WORKSPACE)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310 (trusted localhost)
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, raw


# ── Council definition ──────────────────────────────────────
# provider determines which runtime the agent binds to. Web-grounded research
# roles + the report writer run on Claude (opus); the cross-model critique layer
# runs on Codex/GPT-5.5 — mirroring backend/.../council/role_registry.py.
LEADER = "Portfolio Manager"
AGENTS: list[dict[str, str]] = [
    {
        "name": "Fundamentals Analyst",
        "provider": "claude",
        "model": "opus",
        "description": "KR + US equity fundamentals research",
        "instructions": (
            "You are a buy-side fundamentals analyst covering Korean (KOSPI/KOSDAQ) "
            "and US (NYSE/NASDAQ) equities. Use web search to gather the latest "
            "earnings, valuation (PER/PBR/ROE/EV-EBITDA), guidance and filings. "
            "Output concise, evidence-backed JSON findings with sources."
        ),
    },
    {
        "name": "Technical Analyst",
        "provider": "claude",
        "model": "opus",
        "description": "Price action, RSI/MACD, moving averages, volume",
        "instructions": (
            "You are a technical analyst. From recent price/volume data and web "
            "research, report RSI(14), MACD signal, MA status, 52-week position and "
            "volume ratio for the watchlist. Flag overbought/oversold and breakouts."
        ),
    },
    {
        "name": "News Sentiment Analyst",
        "provider": "claude",
        "model": "opus",
        "description": "Headline + flow sentiment across major outlets",
        "instructions": (
            "You are a market-sentiment analyst. Aggregate news across major KR/US "
            "outlets via web search, score bullish/bearish balance, and surface the "
            "catalysts and risk-on/risk-off signals driving the tape today."
        ),
    },
    {
        "name": "Bull Researcher",
        "provider": "claude",
        "model": "opus",
        "description": "Builds the strongest evidence-based long thesis",
        "instructions": (
            "You are the Bull researcher in an investment debate. Build the strongest "
            "evidence-backed case for going long the strongest candidates, citing the "
            "analysts' findings. Engage directly with the Bear's counterarguments."
        ),
    },
    {
        "name": "Bear Researcher",
        "provider": "claude",
        "model": "opus",
        "description": "Builds the strongest risk/short thesis",
        "instructions": (
            "You are the Bear researcher in an investment debate. Poke holes in the "
            "Bull case, surface downside risks, valuation stretch and crowded "
            "positioning, and argue for caution or hedges with evidence."
        ),
    },
    {
        "name": "Investment Judge",
        "provider": "codex",
        "model": "gpt-5.5",
        "description": "Hybrid rule + LLM consensus judge (cross-model)",
        "instructions": (
            "You are the Judge. Weigh the Bull and Bear arguments on logical "
            "coherence and evidence quality, detect false consensus, and decide "
            "whether the debate has converged. Stay neutral; output a structured "
            "agreement score with sharpening questions when it has not."
        ),
    },
    {
        "name": "Trader",
        "provider": "codex",
        "model": "gpt-5.5",
        "description": "Turns the verdict into concrete entries (no execution)",
        "instructions": (
            "You are the Trader. From the converged thesis, propose concrete entries "
            "with direction, timeframe, entry/target/stop and risk-reward — but never "
            "place live orders. Output structured trade proposals only."
        ),
    },
    {
        "name": "Risk Manager",
        "provider": "codex",
        "model": "gpt-5.5",
        "description": "Independent risk critique of the trade proposals",
        "instructions": (
            "You are the Risk Manager. Independently critique the Trader's proposals: "
            "position sizing, correlation/concentration, drawdown and tail risk. "
            "Approve, trim or reject each with a rationale."
        ),
    },
    {
        "name": LEADER,
        "provider": "claude",
        "model": "opus",
        "description": "Synthesizes the final report + recommendations",
        "instructions": (
            "You are the Portfolio Manager and council lead. Synthesize the analysts, "
            "the Bull/Bear debate, the Trader proposals and the Risk critique into a "
            "final daily report: market summary, causal chains, risk matrix, and a "
            "ranked set of actionable recommendations with entry/target/stop. "
            "Everything up to recommendations — no live trading."
        ),
    },
]

SKILL = {
    "name": "Daily Trading Report",
    "description": "House format for the daily news & trading report.",
    "content": (
        "# Daily Trading Report\n\n"
        "Produce a daily KR+US markets report covering: an alert banner, market "
        "summary, top news with causal-chain analysis (news -> direct impact -> "
        "derived effects -> opportunity), sector flows, market sentiment, technical "
        "snapshots, a risk matrix, upcoming catalysts, and a ranked list of "
        "actionable trade recommendations (ticker, direction, entry, target, stop, "
        "risk-reward, rationale). Cover everything a trading desk does *except* "
        "placing live orders. Be concrete, cite evidence, and prefer numbers.\n"
    ),
    "config": {},
    "files": [],
}


def require_config() -> None:
    if not TOKEN or not WORKSPACE:
        die(
            "MULTICA_API_TOKEN / MULTICA_WORKSPACE_ID not set. "
            "Run `make multica-bootstrap` first."
        )
    status, _ = api("GET", "/api/runtimes")
    if status == 401:
        die("PAT rejected (401). Re-run `make multica-bootstrap`.")


def runtime_by_provider() -> dict[str, str]:
    """Map provider -> first online runtime id."""
    status, data = api("GET", "/api/runtimes")
    if status != 200:
        die(f"could not list runtimes (HTTP {status})")
    items = data.get("runtimes") if isinstance(data, dict) else data
    mapping: dict[str, str] = {}
    for rt in items or []:
        provider = rt.get("provider", "")
        if provider and provider not in mapping:
            mapping[provider] = rt["id"]
    if "claude" not in mapping and "codex" not in mapping:
        die(
            "no claude/codex runtimes online. Start the daemon first:\n"
            "    make multica-runtime   (or: multica daemon start)"
        )
    return mapping


def existing_by_name(path: str, key: str = "name") -> dict[str, dict]:
    status, data = api("GET", path)
    if status != 200:
        return {}
    items = data if isinstance(data, list) else (data.get(path.rsplit("/", 1)[-1]) or [])
    if not isinstance(items, list):
        items = data.get("items", []) if isinstance(data, dict) else []
    return {it[key]: it for it in items if isinstance(it, dict) and key in it}


def ensure_agents(runtimes: dict[str, str]) -> dict[str, str]:
    """Create any missing agents. Returns name -> agent id."""
    existing = existing_by_name("/api/agents")
    result: dict[str, str] = {}
    for spec in AGENTS:
        name = spec["name"]
        if name in existing:
            result[name] = existing[name]["id"]
            log(f"agent exists: {name}")
            continue
        provider = spec["provider"]
        runtime_id = runtimes.get(provider) or runtimes.get("claude") or next(iter(runtimes.values()))
        body = {
            "name": name,
            "description": spec["description"],
            "instructions": spec["instructions"],
            "runtime_id": runtime_id,
            "model": spec["model"],
            "visibility": "workspace",
        }
        status, data = api("POST", "/api/agents", body)
        if status in (200, 201) and isinstance(data, dict):
            result[name] = data["id"]
            log(f"created agent: {name} ({provider}/{spec['model']})")
        else:
            sys.stderr.write(f"  [agents] FAILED to create {name}: HTTP {status} {data}\n")
    return result


def ensure_squad(agent_ids: dict[str, str]) -> None:
    leader_id = agent_ids.get(LEADER)
    if not leader_id:
        log("leader agent missing — skipping squad")
        return
    squads = existing_by_name("/api/squads")
    squad_name = "Investment Council"
    if squad_name in squads:
        squad_id = squads[squad_name]["id"]
        log(f"squad exists: {squad_name}")
    else:
        status, data = api(
            "POST",
            "/api/squads",
            {
                "name": squad_name,
                "description": "Daily KR+US investment debate team (research → recommendations).",
                "leader_id": leader_id,
            },
        )
        if status not in (200, 201) or not isinstance(data, dict):
            sys.stderr.write(f"  [agents] FAILED to create squad: HTTP {status} {data}\n")
            return
        squad_id = data["id"]
        log(f"created squad: {squad_name} (leader={LEADER})")

    status, members = api("GET", f"/api/squads/{squad_id}/members")
    member_ids = set()
    if status == 200:
        rows = members if isinstance(members, list) else (members or {}).get("members", [])
        member_ids = {m.get("member_id") for m in rows or []}
    for name, agent_id in agent_ids.items():
        if name == LEADER or agent_id in member_ids:
            continue
        status, _ = api(
            "POST",
            f"/api/squads/{squad_id}/members",
            {"member_type": "agent", "member_id": agent_id, "role": "member"},
        )
        if status in (200, 201):
            log(f"squad += {name}")


def ensure_skill() -> None:
    skills = existing_by_name("/api/skills")
    if SKILL["name"] in skills:
        log(f"skill exists: {SKILL['name']}")
        return
    status, data = api("POST", "/api/skills", SKILL)
    if status in (200, 201):
        log(f"created skill: {SKILL['name']}")
    else:
        sys.stderr.write(f"  [agents] skill create HTTP {status}: {data}\n")


def main() -> None:
    require_config()
    log(f"workspace {WORKSPACE} @ {BASE}")
    runtimes = runtime_by_provider()
    log("runtimes: " + ", ".join(f"{p}={i[:8]}" for p, i in runtimes.items()))
    agent_ids = ensure_agents(runtimes)
    ensure_squad(agent_ids)
    ensure_skill()
    log(f"done — {len(agent_ids)} agents registered (visibility=workspace).")
    log("Open http://localhost:3001 → Agents / Squads to see the council.")


if __name__ == "__main__":
    main()
