import { useEffect, useState } from "react";

type HealthState =
  | { kind: "loading" }
  | { kind: "ok"; status: string }
  | { kind: "error"; message: string };

const BACKEND_HEALTH_URL = "http://localhost:8000/health";

function App() {
  const [state, setState] = useState<HealthState>({ kind: "loading" });

  useEffect(() => {
    const controller = new AbortController();

    fetch(BACKEND_HEALTH_URL, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const body = (await response.json()) as { status?: unknown };
        if (typeof body.status !== "string") {
          throw new Error("Response missing 'status' string");
        }
        setState({ kind: "ok", status: body.status });
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        const message = err instanceof Error ? err.message : "Unknown error";
        setState({ kind: "error", message });
      });

    return () => controller.abort();
  }, []);

  return (
    <main style={{ fontFamily: "system-ui, sans-serif", padding: "2rem", maxWidth: 640 }}>
      <h1>Story Forge</h1>
      <p>
        Backend health probe to <code>{BACKEND_HEALTH_URL}</code>:
      </p>
      {state.kind === "loading" && <p>Loading…</p>}
      {state.kind === "ok" && (
        <p style={{ color: "green" }}>
          <strong>OK</strong> — status: <code>{state.status}</code>
        </p>
      )}
      {state.kind === "error" && (
        <p style={{ color: "crimson" }}>
          <strong>Error</strong>: {state.message}
        </p>
      )}
    </main>
  );
}

export default App;
