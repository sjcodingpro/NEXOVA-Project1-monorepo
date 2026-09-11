"use client";

import { useCallback, useEffect, useState } from "react";
import { getMe, updateMyProfile, MeResponse } from "@/lib/auth-api";
import { logout } from "@/lib/auth";

export default function ProfilePage() {
  const [me, setMe] = useState<MeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);

  const fetchMe = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getMe();
      setMe(result);
      setName(result.profile?.name || "");
      setPhone(result.profile?.phone || "");
      setAddress(result.profile?.address || "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load profile.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void fetchMe();
  }, [fetchMe]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaveError(null);
    setSaveSuccess(false);
    setSaving(true);
    try {
      await updateMyProfile({ name, phone, address });
      setSaveSuccess(true);
      await fetchMe();
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Could not save profile.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <div className="max-w-lg mx-auto px-6 py-10 text-sm text-slate-400">Loading...</div>;
  }

  if (error || !me) {
    return (
      <div className="max-w-lg mx-auto px-6 py-10">
        <div className="border border-red-900 bg-red-950/50 text-red-300 text-sm rounded-md px-4 py-3">
          {error || "Could not load profile."}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-lg mx-auto px-6 py-10">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Account</h1>
        <button onClick={logout} className="text-sm text-slate-400 hover:text-slate-200">
          Log out
        </button>
      </div>

      <p className="text-slate-400 text-sm mt-2">{me.email}</p>

      <form onSubmit={handleSave} className="space-y-4 mt-8">
        <div>
          <label className="block text-sm text-slate-400 mb-1">Name</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full bg-slate-900 border border-slate-800 rounded-md px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="block text-sm text-slate-400 mb-1">Phone</label>
          <input
            type="text"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            className="w-full bg-slate-900 border border-slate-800 rounded-md px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="block text-sm text-slate-400 mb-1">Address</label>
          <input
            type="text"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            className="w-full bg-slate-900 border border-slate-800 rounded-md px-3 py-2 text-sm"
          />
        </div>

        {saveError && (
          <div className="border border-red-900 bg-red-950/50 text-red-300 text-sm rounded-md px-4 py-3">
            {saveError}
          </div>
        )}
        {saveSuccess && (
          <div className="border border-emerald-900 bg-emerald-950/50 text-emerald-300 text-sm rounded-md px-4 py-3">
            Profile updated.
          </div>
        )}

        <button
          type="submit"
          disabled={saving}
          className="bg-slate-100 text-slate-900 text-sm font-medium px-4 py-2 rounded-md disabled:opacity-50"
        >
          {saving ? "Saving..." : "Save changes"}
        </button>
      </form>
    </div>
  );
}
