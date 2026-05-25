"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";

type MulticaStatus = {
  enabled: boolean;
  up: boolean;
  url: string | null;
};

export default function MulticaPage() {
  const { data } = useQuery({
    queryKey: ["multica-status"],
    queryFn: () => api.get<MulticaStatus>("/api/multica/status"),
    refetchInterval: 15000,
  });

  if (!data) {
    return (
      <div className="p-8 text-sm text-[var(--text-secondary)]">Loading…</div>
    );
  }

  if (!data.enabled) {
    return (
      <main className="space-y-3 p-8">
        <h1 className="text-2xl font-semibold text-[var(--text-primary)]">
          Multica
        </h1>
        <p className="text-sm text-[var(--text-secondary)]">
          Multica integration is disabled. Set <code>MULTICA_BASE_URL</code> to
          enable.
        </p>
      </main>
    );
  }

  return (
    <main className="flex h-[calc(100vh-4rem)] flex-col p-0">
      <header className="flex items-center gap-3 border-b border-[var(--border-color)] p-4">
        <h1 className="text-lg font-semibold text-[var(--text-primary)]">
          Multica
        </h1>
        <span
          className={
            "rounded px-2 py-0.5 text-xs " +
            (data.up
              ? "bg-emerald-500/20 text-emerald-300"
              : "bg-red-500/20 text-red-300")
          }
        >
          {data.up ? "connected" : "offline"}
        </span>
      </header>
      {data.up && data.url ? (
        <iframe
          src={data.url}
          className="w-full flex-1"
          title="Multica board"
        />
      ) : (
        <div className="p-8 text-sm text-[var(--text-secondary)]">
          Multica is configured but unreachable at {data.url}. Check
          docker-compose status.
        </div>
      )}
    </main>
  );
}
