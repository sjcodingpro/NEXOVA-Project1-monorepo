"use client";

import { useState } from "react";
import Link from "next/link";
import type { CreateIncidentPayload, IncidentBranch, IncidentCategory, IncidentOrigin } from "@/types/incidents";
import { createIncident } from "@/lib/incidents-api";

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

const ALL_CATEGORIES = Object.keys(CATEGORY_LABELS) as IncidentCategory[];
const ALL_ORIGINS = Object.keys(ORIGIN_LABELS) as IncidentOrigin[];
const ALL_BRANCHES = Object.keys(BRANCH_LABELS) as IncidentBranch[];

const EMPTY_FORM: CreateIncidentPayload = {
  title: "",
  description: "",
  category: "",
  origin: "",
  branch: "",
};

export default function RegisterIncidentPage() {
  const [form, setForm] = useState<CreateIncidentPayload>(EMPTY_FORM);
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitSuccess, setSubmitSuccess] = useState(false);

  function update<K extends keyof CreateIncidentPayload>(key: K, value: CreateIncidentPayload[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function validateForm(): boolean {
    const errors: Record<string, string> = {};
    if (!form.title.trim()) errors.title = "Title is required.";
    if (!form.description.trim()) errors.description = "Description is required.";
    if (!form.category) errors.category = "Category is required.";
    if (!form.origin) errors.origin = "Origin is required.";
    if (!form.branch) errors.branch = "Branch is required.";
    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitError(null);
    setSubmitSuccess(false);
    if (!validateForm()) return;

    setSubmitting(true);
    try {
      await createIncident(form);
      setForm(EMPTY_FORM);
      setFormErrors({});
      setSubmitSuccess(true);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Could not register the incident.");
    } finally {
      setSubmitting(false);
    }
  }

  const branchHighlighted = form.origin === "branch";

  return (
    <div className="max-w-2xl mx-auto px-6 py-10">
      <Link href="/incidents" className="text-sm text-slate-400 hover:text-slate-200">
        &larr; Back to incident analysis
      </Link>
      <span className="mx-2 text-slate-700">|</span>
      <Link href="/incidents/list" className="text-sm text-slate-400 hover:text-slate-200">
        View incident register &rarr;
      </Link>

      <h1 className="text-2xl font-semibold mt-4">Register an incident</h1>
      <p className="text-slate-400 text-sm mt-2 max-w-xl">
        Log a technical failure, process error, client complaint, candidate or staff issue,
        SLA breach, or data-quality problem so it&apos;s tracked centrally instead of by email
        or Slack.
      </p>

      <form onSubmit={handleSubmit} className="space-y-4 max-w-lg mt-6">
        <div>
          <label className="block text-sm text-slate-400 mb-1">Title</label>
          <input
            type="text"
            value={form.title}
            onChange={(e) => update("title", e.target.value)}
            className="w-full bg-slate-900 border border-slate-800 rounded-md px-3 py-2 text-sm"
          />
          {formErrors.title && <p className="text-xs text-red-400 mt-1">{formErrors.title}</p>}
        </div>

        <div>
          <label className="block text-sm text-slate-400 mb-1">Description</label>
          <textarea
            value={form.description}
            onChange={(e) => update("description", e.target.value)}
            rows={4}
            className="w-full bg-slate-900 border border-slate-800 rounded-md px-3 py-2 text-sm"
          />
          {formErrors.description && (
            <p className="text-xs text-red-400 mt-1">{formErrors.description}</p>
          )}
        </div>

        <div>
          <label className="block text-sm text-slate-400 mb-1">Category</label>
          <select
            value={form.category}
            onChange={(e) => update("category", e.target.value as IncidentCategory)}
            className="w-full bg-slate-900 border border-slate-800 rounded-md px-3 py-2 text-sm"
          >
            <option value="">Select a category…</option>
            {ALL_CATEGORIES.map((cat) => (
              <option key={cat} value={cat}>
                {CATEGORY_LABELS[cat]}
              </option>
            ))}
          </select>
          {formErrors.category && (
            <p className="text-xs text-red-400 mt-1">{formErrors.category}</p>
          )}
        </div>

        <div>
          <label className="block text-sm text-slate-400 mb-1">Origin</label>
          <select
            value={form.origin}
            onChange={(e) => update("origin", e.target.value as IncidentOrigin)}
            className="w-full bg-slate-900 border border-slate-800 rounded-md px-3 py-2 text-sm"
          >
            <option value="">Select an origin…</option>
            {ALL_ORIGINS.map((o) => (
              <option key={o} value={o}>
                {ORIGIN_LABELS[o]}
              </option>
            ))}
          </select>
          {formErrors.origin && <p className="text-xs text-red-400 mt-1">{formErrors.origin}</p>}
        </div>

        <div
          className={`rounded-md ${
            branchHighlighted ? "border border-amber-700 bg-amber-950/30 p-3" : ""
          }`}
        >
          <label className="block text-sm text-slate-400 mb-1">Branch</label>
          <select
            value={form.branch}
            onChange={(e) => update("branch", e.target.value as IncidentBranch)}
            className="w-full bg-slate-900 border border-slate-800 rounded-md px-3 py-2 text-sm"
          >
            <option value="">Select a branch…</option>
            {ALL_BRANCHES.map((b) => (
              <option key={b} value={b}>
                {BRANCH_LABELS[b]}
              </option>
            ))}
          </select>
          {branchHighlighted && (
            <p className="text-xs text-amber-400 mt-1">
              You selected &quot;Branch&quot; as the origin — confirm which office this is
              reporting from.
            </p>
          )}
          {formErrors.branch && <p className="text-xs text-red-400 mt-1">{formErrors.branch}</p>}
        </div>

        {submitError && (
          <div className="border border-red-900 bg-red-950/50 text-red-300 text-sm rounded-md px-4 py-3">
            {submitError}
          </div>
        )}
        {submitSuccess && (
          <div className="border border-emerald-900 bg-emerald-950/50 text-emerald-300 text-sm rounded-md px-4 py-3">
            Incident registered successfully.
          </div>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="bg-slate-100 text-slate-900 text-sm font-medium px-4 py-2 rounded-md disabled:opacity-50"
        >
          {submitting ? "Registering..." : "Register incident"}
        </button>
      </form>
    </div>
  );
}
