"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Candidate, CreateCandidatePayload } from "@/types/candidate";
import { CandidateForm } from "@/components/CandidateForm";
import { LoadingState } from "@/components/LoadingState";
import { ErrorState } from "@/components/ErrorState";

export default function EditCandidatePage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params.id;

  const [candidate, setCandidate] = useState<Candidate | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const fetchCandidate = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getCandidate(id);
      setCandidate(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load candidate.");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void fetchCandidate();
  }, [fetchCandidate]);

  async function handleUpdate(payload: CreateCandidatePayload) {
    await api.updateCandidate(id, payload);
    setSuccess(true);
    setTimeout(() => {
      router.push(`/candidates/${id}`);
    }, 800);
  }

  if (loading) return <LoadingState label="Loading candidate…" />;
  if (error) return <ErrorState message={error} onRetry={() => void fetchCandidate()} />;
  if (!candidate) return null;

  const initialValues: CreateCandidatePayload = {
    full_name: candidate.full_name,
    email: candidate.email,
    phone: candidate.phone,
    position: candidate.position,
    linkedin_url: candidate.linkedin_url,
    cv_url: candidate.cv_url,
    experience_years: candidate.experience_years,
  };

  return (
    <main className="max-w-lg mx-auto px-4 py-8">
      <Link href={`/candidates/${id}`} className="text-sm text-blue-600 hover:underline">
        ← Back to candidate
      </Link>
      <h1 className="text-xl font-semibold mt-4 mb-6">Edit candidate</h1>
      {success && (
        <div className="border border-green-200 bg-green-50 text-green-700 text-sm rounded-md px-4 py-3 mb-4">
          Changes saved. Redirecting…
        </div>
      )}
      <CandidateForm initialValues={initialValues} onSubmit={handleUpdate} submitLabel="Save changes" />
    </main>
  );
}
