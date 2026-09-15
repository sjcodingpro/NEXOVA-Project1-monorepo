"use client";

import { useCallback, useRef, useState } from "react";
import Link from "next/link";
import type { AnalysisSummary } from "@/types/incidents";
import { analyzeIncidents, exportResultsUrl } from "@/lib/incidents-api";

const RULE_LABELS: Record<string, string> = {
  missing_client_company: "Missing client company",
  invalid_category: "Invalid or missing category",
  empty_description: "Empty or too-short description",
  invalid_agent_id: "Missing or invalid agent ID",
  invalid_email: "Invalid or missing email",
  closed_no_score: "Closed ticket, no score",
  score_out_of_range: "Satisfaction score out of range",
};

const CATEGORY_LABELS: Record<string, string> = {
  TECHNICAL: "Technical",
  BILLING: "Billing",
  ACCESS: "Access",
  HR_QUERY: "HR Query",
  COMPLAINT: "Complaint",
};

const STATUS_LABELS: Record<string, string> = {
  OPEN: "Open",
  CLOSED: "Closed",
  DISCARDED: "Discarded",
};

const CATEGORY_ORDER = ["TECHNICAL", "BILLING", "ACCESS", "HR_QUERY", "COMPLAINT"];
const STATUS_ORDER = ["OPEN", "CLOSED", "DISCARDED"];

function pct(count: number, total: number): string {
  if (total === 0) return "0.0";
  return ((count / total) * 100).toFixed(1);
}

export default function IncidentAnalysisPage() {
  const [dragActive, setDragActive] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [summary, setSummary] = useState<AnalysisSummary | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback(async (file: File) => {
    setAnalyzing(true);
    setError(null);
    setFileName(file.name);
    try {
      const result = await analyzeIncidents(file);
      setSummary(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
      setSummary(null);
    } finally {
      setAnalyzing(false);
    }
  }, []);

  function onInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  }

  function onDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragActive(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  }

  return (
    <div className="max-w-4xl mx-auto px-6 py-10">
      <Link href="/" className="text-sm text-slate-400 hover:text-slate-200">
        &larr; Back to backoffice
      </Link>
      <span className="mx-2 text-slate-700">|</span>
      <Link href="/incidents/register" className="text-sm text-slate-400 hover:text-slate-200">
        Register an incident
      </Link>
      <span className="mx-2 text-slate-700">|</span>
      <Link href="/incidents/list" className="text-sm text-slate-400 hover:text-slate-200">
        View incident register &rarr;
      </Link>

      <h1 className="text-2xl font-semibold mt-4">Incident analysis</h1>
      <p className="text-slate-400 text-sm mt-2 max-w-xl">
        Upload the support ticket CSV export to validate records and see a
        summary of the ticket backlog -- category breakdown, status
        breakdown, and satisfaction index. Customer data never leaves this
        upload; only aggregate metrics are shown or exported.
      </p>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragActive(true);
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        className={`mt-6 border-2 border-dashed rounded-lg px-6 py-10 text-center cursor-pointer transition-colors ${
          dragActive
            ? "border-slate-400 bg-slate-900"
            : "border-slate-800 bg-slate-900/50"
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".csv"
          onChange={onInputChange}
          className="hidden"
        />
        <p className="text-sm text-slate-300">
          {fileName ? `Selected: ${fileName}` : "Drag and drop a CSV here, or click to choose a file"}
        </p>
        <p className="text-xs text-slate-500 mt-1">.csv files only</p>
      </div>

      {analyzing && (
        <p className="mt-4 text-sm text-slate-400">Analyzing...</p>
      )}

      {!analyzing && error && (
        <div className="mt-4 border border-red-900 bg-red-950/50 text-red-300 text-sm rounded-md px-4 py-3">
          {error}
        </div>
      )}

      {!analyzing && summary && (
        <div className="mt-8 space-y-8">
          <section>
            <h2 className="text-sm font-medium text-slate-400 uppercase tracking-wide mb-3">
              General metrics
            </h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
              <Stat label="Total records" value={summary.total} />
              <Stat label="Valid records" value={summary.valid_count} />
              <Stat label="Invalid / incomplete" value={summary.invalid_count} />
            </div>
          </section>

          {summary.invalid_count > 0 && (
            <section>
              <h2 className="text-sm font-medium text-slate-400 uppercase tracking-wide mb-3">
                Invalid records breakdown
              </h2>
              <ul className="space-y-2">
                {Object.entries(summary.invalid_rule_counts)
                  .filter(([, count]) => count > 0)
                  .map(([key, count]) => (
                    <li
                      key={key}
                      className="flex justify-between border border-slate-800 rounded-md px-4 py-2 text-sm bg-slate-900/50"
                    >
                      <span>{RULE_LABELS[key] || key}</span>
                      <span className="font-medium">{count}</span>
                    </li>
                  ))}
              </ul>
            </section>
          )}

          <section>
            <h2 className="text-sm font-medium text-slate-400 uppercase tracking-wide mb-3">
              Breakdown by category (valid records)
            </h2>
            <ul className="space-y-2">
              {CATEGORY_ORDER.map((cat) => {
                const count = summary.category_counts[cat] || 0;
                return (
                  <li
                    key={cat}
                    className="flex justify-between border border-slate-800 rounded-md px-4 py-2 text-sm bg-slate-900/50"
                  >
                    <span>{CATEGORY_LABELS[cat] || cat}</span>
                    <span className="font-medium">
                      {count} ({pct(count, summary.valid_count)}%)
                    </span>
                  </li>
                );
              })}
            </ul>
          </section>

          <section>
            <h2 className="text-sm font-medium text-slate-400 uppercase tracking-wide mb-3">
              Breakdown by status (valid records)
            </h2>
            <ul className="space-y-2">
              {STATUS_ORDER.map((st) => {
                const count = summary.status_counts[st] || 0;
                return (
                  <li
                    key={st}
                    className="flex justify-between border border-slate-800 rounded-md px-4 py-2 text-sm bg-slate-900/50"
                  >
                    <span>{STATUS_LABELS[st] || st}</span>
                    <span className="font-medium">
                      {count} ({pct(count, summary.valid_count)}%)
                    </span>
                  </li>
                );
              })}
            </ul>
          </section>

          <section>
            <h2 className="text-sm font-medium text-slate-400 uppercase tracking-wide mb-3">
              Satisfaction index (closed tickets)
            </h2>
            <p className="text-sm text-slate-300">
              Scored tickets: {summary.scored_total} of {summary.closed_total}
            </p>
            <p className="text-sm text-slate-300 mb-3">
              Average score: {summary.avg_score.toFixed(2)} / 5.00
            </p>
            <ul className="space-y-2">
              {[1, 2, 3, 4, 5].map((score) => (
                <li
                  key={score}
                  className="flex justify-between border border-slate-800 rounded-md px-4 py-2 text-sm bg-slate-900/50"
                >
                  <span>Score {score}</span>
                  <span className="font-medium">
                    {summary.score_distribution[String(score)] || 0}
                  </span>
                </li>
              ))}
            </ul>
          </section>

            <a
            href={exportResultsUrl()}
            className="inline-block bg-slate-100 text-slate-900 text-sm font-medium px-4 py-2 rounded-md"
          >
            Download results as CSV
          </a>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="border border-slate-800 rounded-lg px-4 py-3 bg-slate-900/50">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="text-lg font-semibold mt-1">{value}</p>
    </div>
  );
}
