"use client";

/**
 * React Query provider for client-side data fetching hooks.
 *
 * Wraps the application so the new multi-agent pages (`/agents`,
 * `/debate`, `/memory`) can use `useQuery`/`useMutation` hooks from
 * `@/lib/api-client`.
 */

import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

export default function QueryProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            refetchOnWindowFocus: false,
          },
        },
      })
  );

  return (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}
