/**
 * Typed fetch wrapper that works on both server and client.
 *
 * On the server (during SSR), we call the backend directly.
 * On the client, we go through the Next.js rewrite proxy.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

function getBaseUrl(): string {
  if (typeof window === "undefined") {
    // Server-side: call backend directly
    return BACKEND_URL;
  }
  // Client-side: use Next.js rewrite (relative URL)
  return "";
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const base = getBaseUrl();
  const url = `${base}${path}`;

  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!res.ok) {
    const body = await res.text().catch(() => "Unknown error");
    throw new ApiError(res.status, body);
  }

  return res.json() as Promise<T>;
}

export const api = {
  get<T>(path: string, options?: RequestInit): Promise<T> {
    return request<T>(path, { ...options, method: "GET" });
  },

  post<T>(path: string, body?: unknown, options?: RequestInit): Promise<T> {
    return request<T>(path, {
      ...options,
      method: "POST",
      body: body ? JSON.stringify(body) : undefined,
    });
  },

  put<T>(path: string, body?: unknown, options?: RequestInit): Promise<T> {
    return request<T>(path, {
      ...options,
      method: "PUT",
      body: body ? JSON.stringify(body) : undefined,
    });
  },

  delete<T>(path: string, options?: RequestInit): Promise<T> {
    return request<T>(path, { ...options, method: "DELETE" });
  },
};

// ─── Multi-agent / debate / memory types ────────────────────────────
export type AgentBinding = {
  provider: string;
  model: string;
  system_prompt_override?: string | null;
  timeout_s: number;
};

export type AgentItem = {
  role: string;
  binding: AgentBinding;
  tools: string[];
  pipelines: string[];
};

export type AgentDetail = {
  role: string;
  binding: AgentBinding;
  tools: string[];
};

export type AgentsList = {
  items: AgentItem[];
};

export type DebateSummary = {
  id: string;
  pipeline: string;
  state: string;
  started_at: string | null;
  ended_at: string | null;
  triggered_by: string | null;
  rounds: number;
};

export type DebateList = {
  items: DebateSummary[];
  total: number;
};

export type DebateRoundSpeech = {
  text: string;
  structured: unknown;
  latency_ms: number;
};

export type DebateRoundJudge = {
  rule_score: number;
  llm_score: number;
  false_consensus: boolean;
  dimensions: Record<string, number>;
  next_round_questions: string[];
};

export type DebateRound = {
  index: number;
  bull: DebateRoundSpeech;
  bear: DebateRoundSpeech;
  judge: DebateRoundJudge;
};

export type DebateVerdict = {
  consensus: string;
  report_content: unknown;
  recommendations: unknown[];
};

export type DebateDetail = {
  id: string;
  pipeline: string;
  state: string;
  started_at: string | null;
  ended_at: string | null;
  triggered_by: string | null;
  rounds: DebateRound[];
  verdict: DebateVerdict | null;
  error: string | null;
};

export type MemoryTreeNode = {
  id?: string;
  title: string;
  summary?: string | null;
  outcome?: string | null;
  children?: MemoryTreeNode[];
};

export type MemoryTree = {
  root: MemoryTreeNode;
};

export type MemorySearchItem = {
  id: string;
  summary: string | null;
  symbol: string | null;
  sector: string | null;
  date: string;
  outcome: string | null;
  kind: string;
};

export type MemorySearchResult = {
  items: MemorySearchItem[];
};

// ─── React Query hooks ───────────────────────────────────────────────
export function useAgents() {
  return useQuery({
    queryKey: ["agents"],
    queryFn: () => api.get<AgentsList>("/api/agents"),
  });
}

export function useAgent(role: string) {
  return useQuery({
    queryKey: ["agents", role],
    queryFn: () => api.get<AgentDetail>(`/api/agents/${role}`),
    enabled: Boolean(role),
  });
}

export function useUpdateBinding(role: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: AgentBinding) =>
      api.put<void>(`/api/agents/${role}/binding`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["agents"] });
      qc.invalidateQueries({ queryKey: ["agents", role] });
    },
  });
}

export function useDebates(pipeline?: string) {
  return useQuery({
    queryKey: ["debates", pipeline ?? "all"],
    queryFn: () =>
      api.get<DebateList>(
        pipeline ? `/api/debate?pipeline=${pipeline}` : "/api/debate"
      ),
  });
}

export function useDebate(id: string) {
  return useQuery({
    queryKey: ["debate", id],
    queryFn: () => api.get<DebateDetail>(`/api/debate/${id}`),
    enabled: Boolean(id),
  });
}

export function useMemoryTree() {
  return useQuery({
    queryKey: ["memory-tree"],
    queryFn: () => api.get<MemoryTree>("/api/memory/tree"),
  });
}

export function useMemorySearch(q: string) {
  return useQuery({
    queryKey: ["memory-search", q],
    queryFn: () =>
      api.get<MemorySearchResult>(
        `/api/memory/search?q=${encodeURIComponent(q)}`
      ),
    enabled: q.length > 0,
  });
}
