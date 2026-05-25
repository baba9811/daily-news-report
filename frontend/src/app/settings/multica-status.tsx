"use client";

import { useQuery } from "@tanstack/react-query";
import { Boxes, CheckCircle, XCircle } from "lucide-react";
import { api } from "@/lib/api-client";

type MulticaStatus = {
  enabled: boolean;
  up: boolean;
  url: string | null;
};

/**
 * Multica connectivity panel for the Settings page.
 *
 * Polls /api/multica/status every 15 seconds and surfaces the enabled flag,
 * health probe result, and configured base URL. The card sits alongside
 * SystemStatus + MultiAgentStatus on the settings page sidebar.
 */
export default function MulticaStatusPanel() {
  const { data, isLoading, dataUpdatedAt } = useQuery({
    queryKey: ["multica-status"],
    queryFn: () => api.get<MulticaStatus>("/api/multica/status"),
    refetchInterval: 15000,
  });

  const lastChecked = dataUpdatedAt
    ? new Date(dataUpdatedAt).toLocaleTimeString()
    : null;

  return (
    <div className="card">
      <div className="mb-4 flex items-center gap-2">
        <Boxes size={18} className="text-blue-400" />
        <h2 className="text-lg font-semibold text-[var(--text-primary)]">
          Multica
        </h2>
      </div>

      {isLoading || !data ? (
        <p className="text-sm text-[var(--text-secondary)]">
          Checking Multica status…
        </p>
      ) : (
        <ul className="space-y-3">
          <li className="flex items-center justify-between text-sm">
            <span className="text-[var(--text-secondary)]">Integration</span>
            <span className="flex items-center gap-2">
              <span className="text-[var(--text-secondary)]">
                {data.enabled ? "enabled" : "disabled"}
              </span>
              {data.enabled ? (
                <CheckCircle size={16} className="text-emerald-400" />
              ) : (
                <XCircle size={16} className="text-[var(--text-secondary)]" />
              )}
            </span>
          </li>
          <li className="flex items-center justify-between text-sm">
            <span className="text-[var(--text-secondary)]">Service</span>
            <span className="flex items-center gap-2">
              <span className="text-[var(--text-secondary)]">
                {data.enabled ? (data.up ? "up" : "down") : "—"}
              </span>
              {data.enabled ? (
                data.up ? (
                  <CheckCircle size={16} className="text-emerald-400" />
                ) : (
                  <XCircle size={16} className="text-red-400" />
                )
              ) : (
                <XCircle size={16} className="text-[var(--text-secondary)]" />
              )}
            </span>
          </li>
          {data.url && (
            <li className="flex items-center justify-between text-sm">
              <span className="text-[var(--text-secondary)]">URL</span>
              <span className="truncate font-mono text-xs text-[var(--text-secondary)]">
                {data.url}
              </span>
            </li>
          )}
        </ul>
      )}

      {lastChecked && (
        <p className="mt-4 text-xs text-[var(--text-secondary)]">
          Last checked {lastChecked}
        </p>
      )}
    </div>
  );
}
