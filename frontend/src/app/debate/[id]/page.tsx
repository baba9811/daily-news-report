"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowLeft, Radio } from "lucide-react";
import { useDebate } from "@/lib/api-client";
import { subscribeDebate, type DebateEvent } from "@/lib/debate-stream";

export default function DebateDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id ?? "";
  const { data, refetch } = useDebate(id);
  const [liveEvents, setLiveEvents] = useState<DebateEvent[]>([]);

  useEffect(() => {
    if (!id || !data || data.state !== "RUNNING") {
      return;
    }
    const unsubscribe = subscribeDebate(id, (e) => {
      setLiveEvents((prev) => [...prev, e]);
      if (e.kind === "debate_done" || e.kind === "error") {
        refetch();
      }
    });
    return unsubscribe;
  }, [id, data, refetch]);

  if (!data) {
    return (
      <div className="space-y-6">
        <Link
          href="/debate"
          className="inline-flex items-center gap-2 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
        >
          <ArrowLeft size={16} />
          Back to Debates
        </Link>
        <div className="card">
          <p className="text-sm text-[var(--text-secondary)]">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Link
        href="/debate"
        className="inline-flex items-center gap-2 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
      >
        <ArrowLeft size={16} />
        Back to Debates
      </Link>

      <div className="card">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-xl font-bold text-[var(--text-primary)]">
              {data.pipeline} debate
            </h1>
            <p className="mt-1 font-mono text-xs text-[var(--text-secondary)]">
              {data.id}
            </p>
            <p className="mt-1 text-sm text-[var(--text-secondary)]">
              state: {data.state} · started:{" "}
              {data.started_at ?? "—"}
            </p>
          </div>
          <span className="rounded-full bg-blue-500/20 px-3 py-1 text-xs font-medium text-blue-300">
            {data.state}
          </span>
        </div>
      </div>

      {data.state === "RUNNING" && (
        <section className="card border-l-4 border-blue-500">
          <div className="mb-3 flex items-center gap-2">
            <Radio size={16} className="text-blue-400" />
            <h2 className="font-semibold text-[var(--text-primary)]">
              Live ({liveEvents.length} events)
            </h2>
          </div>
          <ul className="max-h-48 space-y-1 overflow-y-auto text-xs">
            {liveEvents.length === 0 ? (
              <li className="text-[var(--text-secondary)]">
                Waiting for events...
              </li>
            ) : (
              liveEvents.map((e, i) => (
                <li
                  key={`${e.kind}-${i}`}
                  className="font-mono text-[var(--text-secondary)]"
                >
                  <span className="text-blue-400">{e.kind}</span>
                </li>
              ))
            )}
          </ul>
        </section>
      )}

      <section className="space-y-4">
        <h2 className="text-lg font-semibold text-[var(--text-primary)]">
          Rounds
        </h2>
        {data.rounds.length === 0 ? (
          <div className="card">
            <p className="text-sm text-[var(--text-secondary)]">
              No rounds yet.
            </p>
          </div>
        ) : (
          data.rounds.map((r) => (
            <div key={r.index} className="card space-y-3">
              <h3 className="font-semibold text-[var(--text-primary)]">
                Round {r.index + 1}
              </h3>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <div className="rounded-md border border-red-500/30 bg-red-500/5 p-3">
                  <h4 className="mb-2 text-sm font-medium text-red-300">
                    Bull
                  </h4>
                  <p className="line-clamp-6 whitespace-pre-wrap text-xs text-[var(--text-secondary)]">
                    {r.bull.text}
                  </p>
                </div>
                <div className="rounded-md border border-blue-500/30 bg-blue-500/5 p-3">
                  <h4 className="mb-2 text-sm font-medium text-blue-300">
                    Bear
                  </h4>
                  <p className="line-clamp-6 whitespace-pre-wrap text-xs text-[var(--text-secondary)]">
                    {r.bear.text}
                  </p>
                </div>
              </div>
              <div className="text-xs text-[var(--text-secondary)]">
                Judge: rule={r.judge.rule_score.toFixed(2)} · llm=
                {r.judge.llm_score.toFixed(2)} · false_consensus=
                {String(r.judge.false_consensus)}
              </div>
              {r.judge.next_round_questions.length > 0 && (
                <details>
                  <summary className="cursor-pointer text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
                    Next round questions (
                    {r.judge.next_round_questions.length})
                  </summary>
                  <ul className="ml-5 mt-2 list-disc space-y-1 text-xs text-[var(--text-secondary)]">
                    {r.judge.next_round_questions.map((q, i) => (
                      <li key={`${r.index}-q-${i}`}>{q}</li>
                    ))}
                  </ul>
                </details>
              )}
            </div>
          ))
        )}
      </section>

      {data.verdict && (
        <section className="card">
          <h2 className="mb-3 font-semibold text-[var(--text-primary)]">
            Verdict — {data.verdict.consensus}
          </h2>
          <pre className="max-h-96 overflow-auto rounded-md bg-[var(--bg-primary)] p-3 text-xs text-[var(--text-secondary)]">
            {JSON.stringify(data.verdict.report_content, null, 2)}
          </pre>
        </section>
      )}

      {data.error && (
        <section className="card border-l-4 border-red-500">
          <h2 className="mb-2 font-semibold text-red-300">Error</h2>
          <p className="text-sm text-[var(--text-secondary)]">{data.error}</p>
        </section>
      )}
    </div>
  );
}
