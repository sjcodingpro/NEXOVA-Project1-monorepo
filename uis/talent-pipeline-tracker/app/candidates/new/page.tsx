"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import type { CreateCandidatePayload } from "@/types/candidate";
import { CandidateForm } from "@/components/CandidateForm";

export default function NewCandidatePage() {
  const router = useRouter();
  const [success, setSuccess] = useState(false);

  async function handleCreate(payload: CreateCandidatePayload) {
    const created = await api.createCandidate(payload);
    setSuccess(true);
    setTimeout(() => {
      router.push(`/candidates/${created.id}`);
    }, 800);
  }

  return (
    <main className="max-w-lg mx-auto px-4 py-8">
      <Link href="/" className="text-sm text-blue-600 hover:underline">
        ← Back to pipeline
      </Link>
      <h1 className="text-xl font-semibold mt-4 mb-6">Register candidate</h1>
      {success && (
        <div className="border border-green-200 bg-green-50 text-green-700 text-sm rounded-md px-4 py-3 mb-4">
          Candidate registered. Redirecting…
        </div>
      )}
      <CandidateForm onSubmit={handleCreate} submitLabel="Register candidate" />
    </main>
  );
}
