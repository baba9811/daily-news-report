"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { ArrowLeft, Check } from "lucide-react";
import {
  useAgent,
  useUpdateBinding,
  type AgentBinding,
} from "@/lib/api-client";

export default function AgentDetailPage() {
  const params = useParams<{ role: string }>();
  const role = params?.role ?? "";
  const { data } = useAgent(role);
  const mutate = useUpdateBinding(role);
  const [form, setForm] = useState<AgentBinding | null>(null);

  if (!data) {
    return (
      <div className="space-y-6">
        <Link
          href="/agents"
          className="inline-flex items-center gap-2 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
        >
          <ArrowLeft size={16} />
          Back to Agents
        </Link>
        <div className="card">
          <p className="text-sm text-[var(--text-secondary)]">Loading...</p>
        </div>
      </div>
    );
  }

  const current: AgentBinding = form ?? data.binding;

  const updateField = <K extends keyof AgentBinding>(
    key: K,
    value: AgentBinding[K]
  ) => {
    setForm({ ...current, [key]: value });
  };

  const handleSave = () => {
    mutate.mutate(current);
  };

  return (
    <div className="space-y-6">
      <Link
        href="/agents"
        className="inline-flex items-center gap-2 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
      >
        <ArrowLeft size={16} />
        Back to Agents
      </Link>

      <div>
        <h1 className="text-2xl font-bold text-[var(--text-primary)]">
          {role}
        </h1>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">
          Configure provider, model, and timeout for this role
        </p>
      </div>

      <div className="card max-w-2xl space-y-5">
        <div className="space-y-2">
          <label
            htmlFor="provider"
            className="block text-sm font-medium text-[var(--text-primary)]"
          >
            Provider
          </label>
          <select
            id="provider"
            value={current.provider}
            onChange={(e) => updateField("provider", e.target.value)}
            className="block w-64 rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] px-3 py-2 text-sm text-[var(--text-primary)] focus:border-blue-400 focus:outline-none"
          >
            <option value="claude-code">claude-code</option>
            <option value="codex">codex</option>
          </select>
        </div>

        <div className="space-y-2">
          <label
            htmlFor="model"
            className="block text-sm font-medium text-[var(--text-primary)]"
          >
            Model
          </label>
          <input
            id="model"
            type="text"
            value={current.model}
            onChange={(e) => updateField("model", e.target.value)}
            className="block w-64 rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] px-3 py-2 text-sm text-[var(--text-primary)] focus:border-blue-400 focus:outline-none"
          />
        </div>

        <div className="space-y-2">
          <label
            htmlFor="timeout"
            className="block text-sm font-medium text-[var(--text-primary)]"
          >
            Timeout (seconds)
          </label>
          <input
            id="timeout"
            type="number"
            value={current.timeout_s}
            onChange={(e) =>
              updateField("timeout_s", Number(e.target.value))
            }
            className="block w-32 rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] px-3 py-2 text-sm text-[var(--text-primary)] focus:border-blue-400 focus:outline-none"
          />
        </div>

        <div className="flex items-center gap-3 pt-2">
          <button
            type="button"
            onClick={handleSave}
            disabled={mutate.isPending}
            className="rounded-md bg-blue-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-600 disabled:opacity-50"
          >
            {mutate.isPending ? "Saving..." : "Save"}
          </button>
          {mutate.isSuccess && (
            <span className="inline-flex items-center gap-1 text-sm text-emerald-400">
              <Check size={14} />
              Saved
            </span>
          )}
          {mutate.isError && (
            <span className="text-sm text-red-400">
              {String(mutate.error)}
            </span>
          )}
        </div>
      </div>

      <details className="card max-w-2xl">
        <summary className="cursor-pointer text-sm font-medium text-[var(--text-primary)]">
          Tools enabled ({data.tools.length})
        </summary>
        <ul className="mt-3 space-y-1 text-sm text-[var(--text-secondary)]">
          {data.tools.length === 0 ? (
            <li>—</li>
          ) : (
            data.tools.map((t) => (
              <li key={t} className="font-mono">
                {t}
              </li>
            ))
          )}
        </ul>
      </details>
    </div>
  );
}
