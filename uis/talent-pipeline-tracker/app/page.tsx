"use client";

import Link from "next/link";
import { Suspense, useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Candidate } from "@/types/candidate";
import { useRecordsFilters } from "@/hooks/useRecordsFilters";
import { CandidateFilters } from "@/components/CandidateFilters";
import { CandidateTable } from "@/components/CandidateTable";
import { LoadingState } from "@/components/LoadingState";
import { ErrorState } from "@/components/ErrorState";

function CandidateListPage() {
  const { status, stage, search, setStatus, setStage, setSearch, queryParams } =
    useRecordsFilters();
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchCandidates = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.listCandidates(queryParams);
      setCandidates(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }, [queryParams]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void fetchCandidates();
  }, [fetchCandidates]);

  return (
    <main className="max-w-5xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold">Candidate pipeline</h1>
          <p className="text-sm text-gray-500">Nexova People &amp; Talent</p>
        </div>
        <Link
          href="/candidates/new"
          className="bg-black text-white text-sm font-medium px-4 py-2 rounded-md"
        >
          Register candidate
        </Link>
      </div>

      <CandidateFilters
        status={status}
        stage={stage}
        search={search}
        onStatusChange={setStatus}
        onStageChange={setStage}
        onSearchChange={setSearch}
      />

      {loading && <LoadingState label="Loading candidates…" />}
      {!loading && error && <ErrorState message={error} onRetry={() => void fetchCandidates()} />}
      {!loading && !error && <CandidateTable candidates={candidates} />}
    </main>
  );
}

export default function Page() {
  return (
    <Suspense fallback={<LoadingState label="Loading candidates…" />}>
      <CandidateListPage />
    </Suspense>
  );
}
