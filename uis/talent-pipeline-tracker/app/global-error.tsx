"use client";

/**
 * H4: catches errors thrown by the root layout itself, which app/error.tsx
 * cannot -- an error boundary can't catch an error in the same segment
 * that renders it, and the root layout is what renders error.tsx's parent
 * tree. This is Next's documented mechanism for that specific case, and
 * unlike error.tsx it must render its own <html>/<body> since it replaces
 * the entire root layout, not just a nested segment.
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body style={{ fontFamily: "system-ui, sans-serif", background: "#0a0e14", color: "#e2e8f0" }}>
        <div style={{ maxWidth: 560, margin: "0 auto", padding: "64px 24px", textAlign: "center" }}>
          <h1 style={{ fontSize: 20, fontWeight: 600 }}>Something went wrong</h1>
          <p style={{ color: "#94a3b8", fontSize: 14, marginTop: 8 }}>
            {error.message || "An unexpected error occurred."}
          </p>
          <div style={{ display: "flex", justifyContent: "center", gap: 16, marginTop: 24 }}>
            <button
              onClick={reset}
              style={{
                background: "#f1f5f9",
                color: "#0f172a",
                fontSize: 14,
                fontWeight: 500,
                padding: "8px 16px",
                borderRadius: 6,
                border: "none",
                cursor: "pointer",
              }}
            >
              Try again
            </button>
          </div>
        </div>
      </body>
    </html>
  );
}
