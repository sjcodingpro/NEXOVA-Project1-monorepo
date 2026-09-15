"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import type {
  Incident,
  IncidentBranch,
  IncidentCategory,
  IncidentManagerSummary,
  IncidentOrigin,
  IncidentStatus,
} from "@/types/incidents";
import { getIncidentSummary, listIncidents, updateIncidentStatus } from "@/lib/incidents-api";

const CATEGORY_LABELS: Record<IncidentCategory, string> = {
  technical_failure: "Technical failure",
  process_error: "Process error",
  client_complaint: "Client complaint",
  candidate_issue: "Candidate issue",
  staff_issue: "Staff issue",
  sla_breach: "SLA breach",
  data_quality: "Data quality",
  other: "Other",
};

const STATUS_LABELS: Record<IncidentStatus, string> = {
  open: "Open",
  in_progress: "In progress",
  resolved: "Resolved",
  discarded: "Discarded",
};

const ORIGIN_LABELS: Record<IncidentOrigin, string> = {
  customer: "Customer",
  branch: "Branch",
  internal: "Internal",
};

const BRANCH_LABELS: Record<IncidentBranch, string> = {
  central: "Central — Valencia HQ",
  valencia_operations: "Valencia — Operations",
  miami_office: "Miami Office",
  remote: "Remote (no fixed office)",
};

const NEXT_STATUS: Record<IncidentStatus, IncidentStatus[]> = {
  open: ["in_progress", "discarded"],
  in_progress: ["resolved", "discarded"],
  resolved: [],
  discarded: [],
};

const ALL_STATUSES = Object.keys(STATUS_LABELS) as IncidentStatus[];
const ALL_ORIGINS = Object.keys(ORIGIN_LABELS) as IncidentOrigin[];
const ALL_BRANCHES = Object.keys(BRANCH_LABELS) as IncidentBranch[];

export default function IncidentListPage() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rowError, setRowError] = useState<string | null>(null);

  const [statusFilter, setStatusFilter] = useState<IncidentStatus | "">("");
  const [originFilter, setOriginFilter] = useState<IncidentOrigin | "">("");
  const [branchFilter, setBranchFilter] = useState<IncidentBranch | "">("");

  const [summary, setSummary] = useState<IncidentManagerSummary | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [summaryError, setSummaryError] = useState<string | null>(null);

  const fetchIncidents = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listIncidents({
        status: statusFilter || undefined,
        origin: originFilter || undefined,
        branch: branchFilter || undefined,
      });
      setIncidents(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load incidents.");
    } finally {
      setLoading(false);
    }
  }, [statusFilter, originFilter, branchFilter]);

  const fetchSummary = useCallback(async () => {
    setSummaryLoading(true);
    setSummaryError(null);
    try {
      const data = await getIncidentSummary();
      setSummary(data);
    } catch (err) {
      setSummaryError(err instanceof Error ? err.message : "Could not load the summary.");
    } finally {
      setSummaryLoading(false);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void fetchIncidents();
  }, [fetchIncidents]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void fetchSummary();
  }, [fetchSummary]);

  async function handleStatusChange(incident: Incident, newStatus: IncidentStatus) {
    const previous = incident.status;
    setIncidents((prev) => prev.map((i) => (i.id === incident.id ? { ...i, status: newStatus } : i)));
    setRowError(null);

    try {
      const updated = await updateIncidentStatus(incident.id, newStatus);
      setIncidents((prev) => prev.map((i) => (i.id === incident.id ? updated : i)));
      void fetchSummary();
    } catch (err) {
      setIncidents((prev) => prev.map((i) => (i.id === incident.id ? { ...i, status: previous } : i)));
      setRowError(err instanceof Error ? err.message : "Could not update this incident's status.");
    }
  }

  return (
    <div className="max-w-5xl mx-auto px-6 py-10">
      <Link href="/incidents" className="text-sm text-slate-400 hover:text-slate-200">
        &larr; Back to incident analysis
      </Link>
      <span className="mx-2 text-slate-700">|</span>
      <Link href="/incidents/register" className="text-sm text-slate-400 hover:text-slate-200">
        Register an incident &rarr;
      </Link>

      <h1 className="text-2xl font-semibold mt-4">Incident register</h1>
      <p className="text-slate-400 text-sm mt-2 max-w-xl">
        Every incident logged across Nexova&apos;s offices, corporate clients, and internal
        systems.
      </p>

      <section className="mt-8">
        <h2 className="text-sm font-medium text-slate-400 uppercase tracking-wide mb-3">
          Summary
        </h2>
        {summaryLoading && <p className="text-sm text-slate-400">Loading summary...</p>}
        {!summaryLoading && summaryError && (
          <div className="border border-red-900 bg-red-950/50 text-red-300 text-sm rounded-md px-4 py-3 flex items-center justify-between">
            <span>{summaryError}</span>
            <button onClick={() => void fetchSummary()} className="underline ml-4">
              Retry
            </button>
          </div>
        )}
        {!summaryLoading && summary && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <Breakdown title="By status" data={summary.by_status} labels={STATUS_LABELS} />
            <Breakdown title="By category" data={summary.by_category} labels={CATEGORY_LABELS} />
            <Breakdown title="By origin" data={summary.by_origin} labels={ORIGIN_LABELS} />
            <Breakdown title="By branch" data={summary.by_branch} labels={BRANCH_LABELS} />
          </div>
        )}
      </section>

      <section className="mt-10">
        <h2 className="text-sm font-medium text-slate-400 uppercase tracking-wide mb-3">
          Incidents
        </h2>

        <div className="flex flex-wrap gap-3 mb-4">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as IncidentStatus | "")}
            className="bg-slate-900 border border-slate-800 rounded-md px-3 py-2 text-sm"
          >
            <option value="">All statuses</option>
            {ALL_STATUSES.map((s) => (
              <option key={s} value={s}>
                {STATUS_LABELS[s]}
              </option>
            ))}
          </select>

          <select
            value={originFilter}
            onChange={(e) => setOriginFilter(e.target.value as IncidentOrigin | "")}
            className="bg-slate-900 border border-slate-800 rounded-md px-3 py-2 text-sm"
          >
            <option value="">All origins</option>
            {ALL_ORIGINS.map((o) => (
              <option key={o} value={o}>
                {ORIGIN_LABELS[o]}
              </option>
            ))}
          </select>

          <select
            value={branchFilter}
            onChange={(e) => setBranchFilter(e.target.value as IncidentBranch | "")}
            className="bg-slate-900 border border-slate-800 rounded-md px-3 py-2 text-sm"
          >
            <option value="">All branches</option>
            {ALL_BRANCHES.map((b) => (
              <option key={b} value={b}>
                {BRANCH_LABELS[b]}
              </option>
            ))}
          </select>
        </div>

        {loading && <p className="text-sm text-slate-400">Loading incidents...</p>}
        {!loading && error && (
          <div className="border border-red-900 bg-red-950/50 text-red-300 text-sm rounded-md px-4 py-3 flex items-center justify-between">
            <span>{error}</span>
            <button onClick={() => void fetchIncidents()} className="underline ml-4">
              Retry
            </button>
          </div>
        )}
        {rowError && (
          <div className="mb-3 border border-red-900 bg-red-950/50 text-red-300 text-sm rounded-md px-4 py-3">
            {rowError}
          </div>
        )}

        {!loading && !error && incidents.length === 0 && (
          <p className="text-sm text-slate-500 py-4">
            {statusFilter || originFilter || branchFilter
              ? "No incidents match the current filters."
              : "No incidents have been registered yet."}
          </p>
        )}

        {!loading && !error && incidents.length > 0 && (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="text-left text-slate-400 border-b border-slate-800">
                <tr>
                  <th className="py-2 pr-4">Title</th>
                  <th className="py-2 pr-4">Category</th>
                  <th className="py-2 pr-4">Origin</th>
                  <th className="py-2 pr-4">Branch</th>
                  <th className="py-2 pr-4">Status</th>
                </tr>
              </thead>
              <tbody>
                {incidents.map((incident) => {
                  const nextOptions = NEXT_STATUS[incident.status];
                  return (
                    <tr key={incident.id} className="border-b border-slate-900">
                      <td className="py-3 pr-4">{incident.title}</td>
                      <td className="py-3 pr-4">{CATEGORY_LABELS[incident.category]}</td>
                      <td className="py-3 pr-4">{ORIGIN_LABELS[incident.origin]}</td>
                      <td className="py-3 pr-4">{BRANCH_LABELS[incident.branch]}</td>
                      <td className="py-3 pr-4">
                        <select
                          value={incident.status}
                          onChange={(e) =>
                            handleStatusChange(incident, e.target.value as IncidentStatus)
                          }
                          disabled={nextOptions.length === 0}
                          className="bg-slate-900 border border-slate-700 rounded px-2 py-1 text-xs"
                        >
                          <option value={incident.status}>{STATUS_LABELS[incident.status]}</option>
                          {nextOptions.map((opt) => (
                            <option key={opt} value={opt}>
                              {STATUS_LABELS[opt]}
                            </option>
                          ))}
                        </select>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function Breakdown({
  title,
  data,
  labels,
}: {
  title: string;
  data: Record<string, number>;
  labels: Record<string, string>;
}) {
  return (
    <div className="border border-slate-800 rounded-lg px-4 py-3 bg-slate-900/50">
      <p className="text-xs text-slate-500 mb-2">{title}</p>
      <ul className="space-y-1">
        {Object.entries(data).map(([key, count]) => (
          <li key={key} className="flex justify-between text-xs">
            <span className="text-slate-400">{labels[key] ?? key}</span>
            <span className="font-medium">{count}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
