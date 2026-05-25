"use client";

import Link from "next/link";
import { useState } from "react";
import { MessageSquare } from "lucide-react";
import { useDebates } from "@/lib/api-client";
import { formatDate } from "@/lib/utils";

export default function DebateListPage() {
  const [pipeline, setPipeline] = useState<string>("");
  const { data, isLoading } = useDebates(pipeline || undefined);

  return (
    <div className="space-y-8">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">
            Debates
          </h1>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">
            History of multi-agent debate runs
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label
            htmlFor="pipeline-filter"
            className="text-xs text-[var(--text-secondary)]"
          >
            Pipeline
          </label>
          <select
            id="pipeline-filter"
            value={pipeline}
            onChange={(e) => setPipeline(e.target.value)}
            className="rounded-md border border-[var(--border-color)] bg-[var(--bg-card)] px-3 py-1.5 text-sm text-[var(--text-primary)] focus:border-blue-400 focus:outline-none"
          >
            <option value="">All pipelines</option>
            <option value="daily">daily</option>
            <option value="news">news</option>
            <option value="global-news">global-news</option>
            <option value="weekly">weekly</option>
          </select>
        </div>
      </div>

      {isLoading ? (
        <div className="card">
          <p className="text-sm text-[var(--text-secondary)]">Loading...</p>
        </div>
      ) : !data || data.items.length === 0 ? (
        <div className="card flex flex-col items-center justify-center py-16">
          <MessageSquare
            size={48}
            className="mb-4 text-[var(--text-secondary)]"
          />
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">
            No debates yet
          </h2>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">
            Debates will appear here once a pipeline runs.
          </p>
        </div>
      ) : (
        <div className="card overflow-x-auto p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border-color)] text-left text-[var(--text-secondary)]">
                <th className="px-4 py-3 font-medium">Pipeline</th>
                <th className="px-4 py-3 font-medium">Started</th>
                <th className="px-4 py-3 font-medium">State</th>
                <th className="px-4 py-3 font-medium">Rounds</th>
                <th className="px-4 py-3 font-medium">Trigger</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((d) => (
                <tr
                  key={d.id}
                  className="border-b border-[var(--border-color)] last:border-b-0 hover:bg-[var(--bg-hover)]"
                >
                  <td className="px-4 py-3">
                    <Link
                      href={`/debate/${d.id}`}
                      className="text-blue-400 hover:text-blue-300 hover:underline"
                    >
                      {d.pipeline}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-[var(--text-secondary)]">
                    {d.started_at ? formatDate(d.started_at) : "—"}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={
                        "rounded-full px-2 py-0.5 text-xs font-medium " +
                        stateColor(d.state)
                      }
                    >
                      {d.state}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-[var(--text-secondary)]">
                    {d.rounds}
                  </td>
                  <td className="px-4 py-3 text-[var(--text-secondary)]">
                    {d.triggered_by ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function stateColor(state: string): string {
  switch (state.toUpperCase()) {
    case "RUNNING":
      return "bg-blue-500/20 text-blue-300";
    case "DONE":
    case "COMPLETED":
      return "bg-emerald-500/20 text-emerald-300";
    case "ERROR":
    case "FAILED":
      return "bg-red-500/20 text-red-300";
    default:
      return "bg-zinc-500/20 text-zinc-300";
  }
}
