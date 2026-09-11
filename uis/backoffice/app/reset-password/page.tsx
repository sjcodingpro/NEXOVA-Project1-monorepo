"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { resetPassword } from "@/lib/auth-api";

function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token");

  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!token) {
    return (
      <div className="max-w-sm mx-auto px-6 py-16">
        <h1 className="text-2xl font-semibold">Invalid reset link</h1>
        <p className="text-slate-400 text-sm mt-2">
          This link is missing its reset token. Request a new one below.
        </p>
        <Link
          href="/forgot-password"
          className="inline-block mt-6 text-sm text-slate-300 hover:text-white underline"
        >
          Request a new reset link
        </Link>
      </div>
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (newPassword.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setSubmitting(true);
    try {
      await resetPassword(token as string, newPassword);
      router.push("/login?reset=success");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "This link is invalid or has expired."
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-sm mx-auto px-6 py-16">
      <h1 className="text-2xl font-semibold">Reset your password</h1>
      <p className="text-slate-400 text-sm mt-2">Choose a new password.</p>

      <form onSubmit={handleSubmit} className="space-y-4 mt-8">
        <div>
          <label className="block text-sm text-slate-400 mb-1">New password</label>
          <input
            type="password"
            required
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            className="w-full bg-slate-900 border border-slate-800 rounded-md px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="block text-sm text-slate-400 mb-1">Confirm password</label>
          <input
            type="password"
            required
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            className="w-full bg-slate-900 border border-slate-800 rounded-md px-3 py-2 text-sm"
          />
        </div>

        {error && (
          <div className="border border-red-900 bg-red-950/50 text-red-300 text-sm rounded-md px-4 py-3">
            {error}
            {error.toLowerCase().includes("invalid") ||
            error.toLowerCase().includes("expired") ? (
              <>
                {" "}
                <Link href="/forgot-password" className="underline">
                  Request a new link
                </Link>
                .
              </>
            ) : null}
          </div>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="w-full bg-slate-100 text-slate-900 text-sm font-medium px-4 py-2 rounded-md disabled:opacity-50"
        >
          {submitting ? "Resetting..." : "Reset password"}
        </button>
      </form>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense
      fallback={
        <div className="max-w-sm mx-auto px-6 py-16 text-sm text-slate-400">
          Loading...
        </div>
      }
    >
      <ResetPasswordForm />
    </Suspense>
  );
}
