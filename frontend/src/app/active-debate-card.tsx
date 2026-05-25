"use client";

import Link from "next/link";
import { MessageSquare, Radio } from "lucide-react";
import { useDebates } from "@/lib/api-client";

export default function ActiveDebateCard() {
  const { data } = useDebates();
  const active = data?.items.find((d) => d.state === "RUNNING") ?? null;

  return (
    <div className="card">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-[var(--text-primary)]">
          Active debate
        </h2>
        {active ? (
          <Radio size={16} className="animate-pulse text-blue-400" />
        ) : (
          <MessageSquare size={16} className="text-[var(--text-secondary)]" />
        )}
      </div>
      {active ? (
        <Link
          href={`/debate/${active.id}`}
          className="block rounded-md border border-blue-500/30 bg-blue-500/5 p-3 hover:border-blue-400"
        >
          <p className="text-sm font-medium text-[var(--text-primary)]">
            {active.pipeline}
          </p>
          <p className="mt-1 font-mono text-xs text-[var(--text-secondary)]">
            {active.id}
          </p>
          <p className="mt-1 text-xs text-blue-300">
            {active.rounds} rounds · started{" "}
            {active.started_at ?? "—"}
          </p>
        </Link>
      ) : (
        <p className="text-sm text-[var(--text-secondary)]">
          No active debate
        </p>
      )}
    </div>
  );
}
