"use client";

import { Bot, CheckCircle, XCircle } from "lucide-react";

/**
 * Multi-agent status panel — placeholder for CLI health checks and
 * token-usage stats. Plan 5 wires a real `/api/settings/health` endpoint;
 * for Plan 3 we render hardcoded "available" rows so the section appears
 * in the UI alongside the existing System Status panel.
 */

type CliCheck = {
  name: string;
  available: boolean;
  version: string | null;
};

const CLI_CHECKS: CliCheck[] = [
  { name: "claude-code", available: true, version: "stub" },
  { name: "codex", available: true, version: "stub" },
];

export default function MultiAgentStatus() {
  return (
    <div className="card">
      <div className="mb-4 flex items-center gap-2">
        <Bot size={18} className="text-blue-400" />
        <h2 className="text-lg font-semibold text-[var(--text-primary)]">
          Multi-agent
        </h2>
      </div>
      <ul className="space-y-3">
        {CLI_CHECKS.map((cli) => (
          <li
            key={cli.name}
            className="flex items-center justify-between text-sm"
          >
            <span className="font-mono text-[var(--text-secondary)]">
              CLI {cli.name}
            </span>
            <span className="flex items-center gap-2">
              {cli.available ? (
                <>
                  <span className="text-[var(--text-secondary)]">
                    v{cli.version ?? "—"}
                  </span>
                  <CheckCircle size={16} className="text-emerald-400" />
                </>
              ) : (
                <>
                  <span className="text-[var(--text-secondary)]">
                    unavailable
                  </span>
                  <XCircle size={16} className="text-red-400" />
                </>
              )}
            </span>
          </li>
        ))}
        <li className="flex items-center justify-between text-sm">
          <span className="text-[var(--text-secondary)]">Token usage (24h)</span>
          <span className="text-[var(--text-secondary)]">—</span>
        </li>
      </ul>
      <p className="mt-4 text-xs text-[var(--text-secondary)]">
        Real CLI health and token usage will be wired in Plan 5.
      </p>
    </div>
  );
}
