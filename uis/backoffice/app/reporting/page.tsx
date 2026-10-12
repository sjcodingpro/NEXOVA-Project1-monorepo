"use client";

import { useEffect, useState } from "react";
import { getWeeklyOfficeProgramPerformance } from "@/lib/reporting-api";
import type { WeeklyPerformance, WeeklyPerformanceEntry } from "@/types/reporting";

const OFFICE_LABEL: Record<string, string> = { valencia: "Valencia", miami: "Miami" };

// The four KPIs, named exactly as in the pipeline's CONTEXT ("KPIs to Measure").
const KPIS: {
  name: string;
  description: string;
  column: string;
  show: (entry: WeeklyPerformanceEntry) => string;
}[] = [
  {
    name: "Material Cost per Office/Programme",
    description:
      "How much each office spent acquiring training and onboarding material this week. Amounts are in each office's own currency and are never added together.",
    column: "Amount spent",
    show: (e) => new Intl.NumberFormat("en-US", { style: "currency", currency: e.currency }).format(e.total_material_cost),
  },
  {
    name: "Kits Delivered",
    description: "How many kits or certificates reached clients, candidates, consultants or agents this week.",
    column: "Kits delivered",
    show: (e) => String(e.kits_delivered_count),
  },
  {
    name: "Shortage Frequency",
    description: "How many times this week a programme's material stock ran below its minimum.",
    column: "Times stock ran low",
    show: (e) => String(e.shortage_events_count),
  },
  {
    name: "Cost Variance Frequency",
    description: "How many times this week a supplier's cost spiked abnormally compared with its usual price.",
    column: "Times a cost spiked",
    show: (e) => String(e.cost_variance_events_count),
  },
];

function addDays(isoDate: string, days: number): string {
  const d = new Date(`${isoDate}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

function formatDay(isoDate: string): string {
  return new Date(`${isoDate}T00:00:00Z`).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}

function programmeLabel(id: string): string {
  const text = id.replace(/-/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export default function ReportingPage() {
  const [week, setWeek] = useState<string | null>(null); // null = most recent computed week
  const [latestWeek, setLatestWeek] = useState<string | null>(null);
  const [data, setData] = useState<WeeklyPerformance | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    getWeeklyOfficeProgramPerformance(week ?? undefined)
      .then((result) => {
        if (cancelled) return;
        setData(result);
        setError(null);
        if (week === null) setLatestWeek(result.week_start);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "The report could not be loaded.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [week]);

  function goToWeek(next: string) {
    setLoading(true);
    setWeek(next);
  }

  const shownWeek = data?.week_start ?? null;
  const atLatest = shownWeek !== null && latestWeek !== null && shownWeek >= latestWeek;

  return (
    <div className="max-w-5xl mx-auto px-6 py-10">
      <h1 className="text-2xl font-semibold tracking-tight">Weekly Office &amp; Programme Performance Report</h1>
      <p className="mt-1 text-sm text-slate-400">
        How each office is doing on training material investment and delivery. Figures are refreshed every Monday morning.
      </p>

      <div className="mt-6 flex flex-wrap items-center gap-3">
        <button
          type="button"
          disabled={!shownWeek || loading}
          onClick={() => shownWeek && goToWeek(addDays(shownWeek, -7))}
          className="rounded border border-slate-700 px-3 py-1.5 text-sm text-slate-200 hover:bg-slate-800 disabled:opacity-40"
        >
          &larr; Previous week
        </button>
        <div className="text-sm">
          {shownWeek ? (
            <>
              <span className="text-slate-400">Week of </span>
              <span className="font-medium">{formatDay(shownWeek)}</span>
              <span className="text-slate-400"> to </span>
              <span className="font-medium">{formatDay(addDays(shownWeek, 6))}</span>
            </>
          ) : (
            <span className="text-slate-400">No week has been calculated yet</span>
          )}
        </div>
        <button
          type="button"
          disabled={!shownWeek || atLatest || loading}
          onClick={() => shownWeek && goToWeek(addDays(shownWeek, 7))}
          className="rounded border border-slate-700 px-3 py-1.5 text-sm text-slate-200 hover:bg-slate-800 disabled:opacity-40"
        >
          Next week &rarr;
        </button>
      </div>

      {error && (
        <div className="mt-6 rounded border border-red-900 bg-red-950/40 px-4 py-3 text-sm text-red-200">{error}</div>
      )}
      {loading && !data && <p className="mt-6 text-sm text-slate-400">Loading the report...</p>}
      {data && data.entries.length === 0 && !error && (
        <p className="mt-6 text-sm text-slate-400">There are no figures for this week yet.</p>
      )}

      {data && data.entries.length > 0 && (
        <div className="mt-6 grid gap-6">
          {KPIS.map((kpi) => (
            <section key={kpi.name} className="rounded-lg border border-slate-800 bg-slate-900/50 p-5">
              <h2 className="text-lg font-semibold">{kpi.name}</h2>
              <p className="mt-1 text-sm text-slate-400">{kpi.description}</p>
              <table className="mt-4 w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-wide text-slate-500">
                    <th className="pb-2 font-medium">Office</th>
                    <th className="pb-2 font-medium">Programme</th>
                    <th className="pb-2 text-right font-medium">{kpi.column}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.entries.map((entry) => (
                    <tr key={`${entry.office}-${entry.programme_id}`} className="border-t border-slate-800">
                      <td className="py-2">{OFFICE_LABEL[entry.office] ?? entry.office}</td>
                      <td className="py-2 text-slate-300">{programmeLabel(entry.programme_id)}</td>
                      <td className="py-2 text-right font-medium tabular-nums">{kpi.show(entry)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
