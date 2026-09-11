"use client";

import { useState } from "react";
import Link from "next/link";
import { forgotPassword } from "@/lib/auth-api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await forgotPassword(email);
      // Always show the same confirmation regardless of whether the
      // email exists -- the API itself never distinguishes the two
      // cases, so there is nothing here to leak either way.
      setSubmitted(true);
    } catch {
      // A genuine failure to reach the API is a different situation
      // from "email not found" (which the API never reveals) -- safe
      // to surface this distinctly without leaking anything.
      setError("Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-sm mx-auto px-6 py-16">
      <h1 className="text-2xl font-semibold">Forgot your password?</h1>
      <p className="text-slate-400 text-sm mt-2">
        Enter your email and we&apos;ll send you a reset link.
      </p>

      {submitted ? (
        <div className="mt-8 border border-emerald-900 bg-emerald-950/50 text-emerald-300 text-sm rounded-md px-4 py-3">
          If that address is registered, a reset link has been sent. Check
          your inbox.
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4 mt-8">
          <div>
            <label className="block text-sm text-slate-400 mb-1">Email</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={submitting}
              className="w-full bg-slate-900 border border-slate-800 rounded-md px-3 py-2 text-sm disabled:opacity-50"
            />
          </div>

          {error && (
            <div className="border border-red-900 bg-red-950/50 text-red-300 text-sm rounded-md px-4 py-3">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="w-full bg-slate-100 text-slate-900 text-sm font-medium px-4 py-2 rounded-md disabled:opacity-50"
          >
            {submitting ? "Sending..." : "Send reset link"}
          </button>
        </form>
      )}

      <div className="text-sm mt-6">
        <Link href="/login" className="text-slate-400 hover:text-slate-200">
          Back to log in
        </Link>
      </div>
    </div>
  );
}
