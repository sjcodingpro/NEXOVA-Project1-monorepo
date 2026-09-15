"use client";

import { useEffect } from "react";

/**
 * H4: neither app had an error boundary anywhere. Any render-time throw
 * (a missing env var, a malformed API response slipping past a guard, an
 * unhandled status value, etc.) escaped to Next's bare default handler --
 * in production, just "Application error: a client-side exception has
 * occurred", no message, no retry, no way out except a manual reload.
 *
 * This catches anything thrown while rendering a route inside app/ (but
 * not the root layout itself -- see global-error.tsx for that case).
 */
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Server-side equivalent of this is main.py's exception handler --
    // this is the client-side counterpart, so an error here is at least
    // visible in the browser console for debugging, not just swallowed
    // by the fallback UI.
    console.error(error);
  }, [error]);

  return (
    <div className="max-w-2xl mx-auto px-6 py-16 text-center">
      <h1 className="text-xl font-semibold">Something went wrong</h1>
      <p className="text-slate-400 text-sm mt-2">
        {error.message || "An unexpected error occurred."}
      </p>
      <div className="flex items-center justify-center gap-4 mt-6">
        <button
          onClick={reset}
          className="bg-slate-100 text-slate-900 text-sm font-medium px-4 py-2 rounded-md"
        >
          Try again
        </button>
        <a href="/" className="text-sm text-slate-400 hover:text-slate-200">
          Back to home
        </a>
      </div>
    </div>
  );
}
