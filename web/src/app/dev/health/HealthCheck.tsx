"use client";

import { ErrorState } from "@/components/ui/ErrorState";
import { Spinner } from "@/components/ui/Spinner";
import { ApiError, apiBaseUrl } from "@/lib/api";
import { useHealth } from "@/lib/queries/health";

function describe(error: Error): string {
  return error instanceof ApiError
    ? `${error.code} (${error.status}): ${error.message}`
    : `${error.name}: ${error.message}. Is the API running, and does CORS_ORIGINS allow this origin?`;
}

export function HealthCheck() {
  const health = useHealth();

  return (
    <main className="bg-bg mx-auto flex min-h-dvh max-w-130 flex-col gap-6 px-5 py-8 md:px-6">
      <header>
        <h1 className="text-title-1 text-ink">API health</h1>
        <p className="text-small text-mute">
          GET /healthz on {apiBaseUrl()} through useHealth(), the api client and
          TanStack Query. Dev only.
        </p>
      </header>

      {health.isPending ? (
        <Spinner label="Checking the API" />
      ) : health.isError ? (
        <div className="rounded-card border-line border">
          <ErrorState
            title="The API didn't answer"
            body={describe(health.error)}
            onRetry={() => void health.refetch()}
          />
        </div>
      ) : (
        <section className="rounded-card border-line bg-surface border p-4">
          <p className="text-body text-ink">
            status: <strong>{health.data.status}</strong>
          </p>
        </section>
      )}
    </main>
  );
}
