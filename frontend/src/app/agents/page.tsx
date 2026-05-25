"use client";

import Link from "next/link";
import { Bot, AlertCircle } from "lucide-react";
import { useAgents, type AgentItem } from "@/lib/api-client";

export default function AgentsPage() {
  const { data, isLoading, error } = useAgents();

  if (isLoading) {
    return (
      <div className="space-y-8">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">
            Agents
          </h1>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">
            Loading agent roster...
          </p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-8">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">
            Agents
          </h1>
        </div>
        <div className="card flex flex-col items-center justify-center py-16">
          <AlertCircle size={48} className="mb-4 text-red-400" />
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">
            Failed to load agents
          </h2>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">
            {String(error)}
          </p>
        </div>
      </div>
    );
  }

  if (!data) {
    return null;
  }

  const byPipeline = new Map<string, AgentItem[]>();
  for (const item of data.items) {
    for (const p of item.pipelines) {
      if (!byPipeline.has(p)) {
        byPipeline.set(p, []);
      }
      byPipeline.get(p)?.push(item);
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-[var(--text-primary)]">
          Agents
        </h1>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">
          Multi-agent council roster grouped by pipeline
        </p>
      </div>

      {Array.from(byPipeline.entries()).map(([pipeline, items]) => (
        <section key={pipeline} className="space-y-3">
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">
            {pipeline}
          </h2>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {items.map((a) => (
              <Link
                key={`${pipeline}-${a.role}`}
                href={`/agents/${a.role}`}
                className="card card-hover block"
              >
                <div className="mb-3 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Bot size={18} className="text-blue-400" />
                    <h3 className="font-semibold text-[var(--text-primary)]">
                      {a.role}
                    </h3>
                  </div>
                  <span
                    className={
                      "rounded-full px-2 py-0.5 text-xs font-medium " +
                      (a.binding.provider === "codex"
                        ? "bg-amber-500/20 text-amber-300"
                        : "bg-sky-500/20 text-sky-300")
                    }
                  >
                    {a.binding.provider}
                  </span>
                </div>
                <p className="text-xs text-[var(--text-secondary)]">
                  model: {a.binding.model}
                </p>
                <p className="mt-1 text-xs text-[var(--text-secondary)]">
                  tools: {a.tools.length > 0 ? a.tools.join(", ") : "—"}
                </p>
              </Link>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
