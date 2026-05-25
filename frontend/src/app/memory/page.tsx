"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, Search } from "lucide-react";
import {
  useMemoryTree,
  useMemorySearch,
  type MemoryTreeNode,
} from "@/lib/api-client";

function TreeNode({ node }: { node: MemoryTreeNode }) {
  const [open, setOpen] = useState(false);
  const hasChildren = Boolean(node.children && node.children.length > 0);

  if (hasChildren) {
    return (
      <li>
        <button
          type="button"
          onClick={() => setOpen(!open)}
          className="flex items-start gap-1 text-left text-[var(--text-primary)] hover:text-blue-400"
        >
          {open ? (
            <ChevronDown size={14} className="mt-0.5 flex-shrink-0" />
          ) : (
            <ChevronRight size={14} className="mt-0.5 flex-shrink-0" />
          )}
          <span>
            {node.title}
            {node.summary && (
              <span className="ml-2 text-xs text-[var(--text-secondary)]">
                — {node.summary}
              </span>
            )}
          </span>
        </button>
        {open && node.children && (
          <ul className="ml-5 mt-1 space-y-1 border-l border-[var(--border-color)] pl-3">
            {node.children.map((c, i) => (
              <TreeNode key={c.id ?? `${node.title}-${i}`} node={c} />
            ))}
          </ul>
        )}
      </li>
    );
  }

  return (
    <li className="text-sm text-[var(--text-secondary)]">
      <span className="text-[var(--text-primary)]">{node.title}</span>
      {node.outcome && (
        <span className="ml-2 text-xs">({node.outcome})</span>
      )}
    </li>
  );
}

export default function MemoryPage() {
  const { data: tree, isLoading: treeLoading } = useMemoryTree();
  const [q, setQ] = useState("");
  const { data: search, isFetching: searching } = useMemorySearch(q);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-[var(--text-primary)]">
          Memory
        </h1>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">
          Browse the agent memory tree and search past notes
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <section className="card lg:col-span-2">
          <h2 className="mb-4 text-lg font-semibold text-[var(--text-primary)]">
            Memory tree
          </h2>
          {treeLoading ? (
            <p className="text-sm text-[var(--text-secondary)]">Loading...</p>
          ) : tree ? (
            <ul className="space-y-1 text-sm">
              <TreeNode node={tree.root} />
            </ul>
          ) : (
            <p className="text-sm text-[var(--text-secondary)]">
              No memory available.
            </p>
          )}
        </section>

        <aside className="card space-y-3">
          <div className="relative">
            <Search
              size={14}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-secondary)]"
            />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search memory..."
              className="w-full rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] py-2 pl-9 pr-3 text-sm text-[var(--text-primary)] focus:border-blue-400 focus:outline-none"
            />
          </div>
          {q.length > 0 && (
            <>
              {searching && (
                <p className="text-xs text-[var(--text-secondary)]">
                  Searching...
                </p>
              )}
              {search && search.items.length === 0 && !searching && (
                <p className="text-sm text-[var(--text-secondary)]">
                  No results
                </p>
              )}
              {search && search.items.length > 0 && (
                <ul className="space-y-2 text-sm">
                  {search.items.map((m) => (
                    <li
                      key={m.id}
                      className="rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] p-2"
                    >
                      <div className="font-medium text-[var(--text-primary)]">
                        {m.symbol ?? m.date}
                      </div>
                      {m.summary && (
                        <div className="mt-1 text-xs text-[var(--text-secondary)]">
                          {m.summary}
                        </div>
                      )}
                      {m.outcome && (
                        <div className="mt-1 text-xs text-emerald-400">
                          outcome: {m.outcome}
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </aside>
      </div>
    </div>
  );
}
