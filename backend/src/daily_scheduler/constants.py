"""Application constants — tunable values that don't belong in .env.

These are operational defaults that rarely change between environments.
Edit this file to adjust behavior without touching .env or Settings.
"""

# ── Claude CLI ───────────────────────────────────────────────
CLAUDE_TIMEOUT_SECONDS = 1200  # Max wait for a single Claude CLI call (20 min)
CLAUDE_RETRY_COUNT = 2  # Number of attempts (1 = no retry)
CLAUDE_RETRY_DELAY_SECONDS = 30  # Wait between retries

# ── Email ────────────────────────────────────────────────────
EMAIL_MAX_RETRIES = 3  # SMTP send attempts
EMAIL_BACKOFF_BASE = 5  # Exponential backoff base (seconds)
EMAIL_SMTP_TIMEOUT = 30  # SMTP connection timeout (seconds)

# ── Recommendation Expiry ────────────────────────────────────
DAY_TRADE_EXPIRY_DAYS = 1  # DAY trades expire after this many days
SWING_TRADE_EXPIRY_DAYS = 14  # SWING trades expire after this many days

# ── Retrospective Analysis ───────────────────────────────────
RETROSPECTIVE_LOOKBACK_DAYS = 30  # How far back to analyze recommendations
RECENT_PERIOD_DAYS = 7  # "Recent" window for detailed table

# ── Report Parsing ───────────────────────────────────────────
SUMMARY_MAX_LENGTH = 200  # Truncation length for report summary

# --- Multi-agent council (Plan 1 onwards) ---

MAX_CONCURRENT_LLM_CALLS = 4
"""Cap on parallel subprocess LLM calls across all providers."""

MAX_DEBATE_ROUNDS_DAILY = 3
MAX_DEBATE_ROUNDS_NEWS = 2
MAX_DEBATE_ROUNDS_WEEKLY = 0

JUDGE_RULE_THRESHOLD = 0.75
JUDGE_LLM_THRESHOLD = 0.70

CLI_TIMEOUT_ANALYST_S = 900
CLI_TIMEOUT_DEBATE_S = 600
CLI_TIMEOUT_DECISION_S = 600
CLI_TIMEOUT_JUDGE_S = 300

MEMORY_TREE_MAX_BYTES = 200_000
MEMORY_AUTO_INJECT_TOP_K = 5

SSE_KEEPALIVE_INTERVAL_S = 15
MULTICA_HTTP_TIMEOUT_S = 10
MULTICA_RETRY_COUNT = 1

LLM_RETRY_COUNT = 2
LLM_BACKOFF_BASE_S = 5.0
