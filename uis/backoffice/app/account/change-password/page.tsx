"use client";

import { useState } from "react";
import { changePassword } from "@/lib/auth-api";

export default function ChangePasswordPage() {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(false);

    if (newPassword.length < 8) {
      setError("New password must be at least 8 characters.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("New passwords do not match.");
      return;
    }

    setSubmitting(true);
    try {
      await changePassword(currentPassword, newPassword);
      setSuccess(true);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not change password.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-sm mx-auto px-6 py-16">
      <h1 className="text-2xl font-semibold">Change password</h1>
      <p className="text-slate-400 text-sm mt-2">
        Enter your current password and a new one.
      </p>

      <form onSubmit={handleSubmit} className="space-y-4 mt-8">
        <div>
          <label className="block text-sm text-slate-400 mb-1">Current password</label>
          <input
            type="password"
            required
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            className="w-full bg-slate-900 border border-slate-800 rounded-md px-3 py-2 text-sm"
          />
        </div>
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
          <label className="block text-sm text-slate-400 mb-1">Confirm new password</label>
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
          </div>
        )}
        {success && (
          <div className="border border-emerald-900 bg-emerald-950/50 text-emerald-300 text-sm rounded-md px-4 py-3">
            Password changed successfully.
          </div>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="w-full bg-slate-100 text-slate-900 text-sm font-medium px-4 py-2 rounded-md disabled:opacity-50"
        >
          {submitting ? "Changing..." : "Change password"}
        </button>
      </form>
    </div>
  );
}
