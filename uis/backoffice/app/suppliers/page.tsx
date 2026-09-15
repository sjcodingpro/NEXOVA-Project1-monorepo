"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import type {
  Supplier,
  Country,
  Category,
  CreateSupplierPayload,
} from "@/types/suppliers";
import {
  listSuppliers,
  createSupplier,
  updateSupplierRate,
  updateSupplierStatus,
} from "@/lib/suppliers-api";

const CATEGORY_LABELS: Record<Category, string> = {
  job_boards: "Job Boards",
  ats_software: "ATS Software",
  assessment_tools: "Assessment Tools",
  training_platforms: "Training Platforms",
  payroll_and_hr_software: "Payroll & HR Software",
  video_interview: "Video Interview",
  background_check: "Background Check",
  office_and_facilities: "Office & Facilities",
  it_and_software_licenses: "IT & Software Licenses",
};

const ALL_CATEGORIES = Object.keys(CATEGORY_LABELS) as Category[];
const COUNTRY_CURRENCY: Record<Country, "EUR" | "USD"> = {
  Spain: "EUR",
  USA: "USD",
};

function daysUntil(dateStr: string): number {
  const target = new Date(dateStr + "T00:00:00Z").getTime();
  const now = new Date();
  const today = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate());
  return Math.round((target - today) / 86400000);
}

const EMPTY_FORM: CreateSupplierPayload = {
  name: "",
  country: "Spain",
  categories: [],
  monthly_rate: 0,
  currency: "EUR",
  status: "active",
  contract_renewal_date: "",
  contact_email: "",
  notes: "",
};

export default function SuppliersPage() {
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [countryFilter, setCountryFilter] = useState<Country | "">("");
  const [categoryFilter, setCategoryFilter] = useState<Category | "">("");

  const [editingRateId, setEditingRateId] = useState<number | null>(null);
  const [rateDraft, setRateDraft] = useState<string>("");
  const [rowError, setRowError] = useState<string | null>(null);

  const [form, setForm] = useState<CreateSupplierPayload>(EMPTY_FORM);
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitSuccess, setSubmitSuccess] = useState(false);

  const fetchSuppliers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listSuppliers({
        country: countryFilter || undefined,
        category: categoryFilter || undefined,
      });
      setSuppliers(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }, [countryFilter, categoryFilter]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void fetchSuppliers();
  }, [fetchSuppliers]);

  function startEditRate(supplier: Supplier) {
    setEditingRateId(supplier.id);
    setRateDraft(String(supplier.monthly_rate));
    setRowError(null);
  }

  function cancelEditRate() {
    setEditingRateId(null);
    setRateDraft("");
    setRowError(null);
  }

  async function saveRate(id: number) {
    const parsed = Number(rateDraft);
    if (!Number.isFinite(parsed) || parsed <= 0) {
      setRowError("Rate must be a positive number.");
      return;
    }
    setRowError(null);
    try {
      const updated = await updateSupplierRate(id, parsed);
      setSuppliers((prev) => prev.map((s) => (s.id === id ? updated : s)));
      setEditingRateId(null);
    } catch (err) {
      setRowError(err instanceof Error ? err.message : "Could not update rate.");
    }
  }

  async function toggleStatus(supplier: Supplier) {
    const next = supplier.status === "active" ? "suspended" : "active";
    setRowError(null);
    try {
      const updated = await updateSupplierStatus(supplier.id, next);
      setSuppliers((prev) => prev.map((s) => (s.id === supplier.id ? updated : s)));
    } catch (err) {
      setRowError(err instanceof Error ? err.message : "Could not update status.");
    }
  }

  function updateForm<K extends keyof CreateSupplierPayload>(
    key: K,
    value: CreateSupplierPayload[K]
  ) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function handleCountryChange(country: Country) {
    setForm((prev) => ({ ...prev, country, currency: COUNTRY_CURRENCY[country] }));
  }

  function toggleFormCategory(category: Category) {
    setForm((prev) => {
      const has = prev.categories.includes(category);
      return {
        ...prev,
        categories: has
          ? prev.categories.filter((c) => c !== category)
          : [...prev.categories, category],
      };
    });
  }

  function validateForm(): boolean {
    const errors: Record<string, string> = {};
    if (!form.name.trim()) errors.name = "Name is required.";
    if (form.categories.length === 0) errors.categories = "Select at least one category.";
    if (!form.monthly_rate || form.monthly_rate <= 0) {
      errors.monthly_rate = "Rate must be a positive number.";
    }
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
      const payload: CreateSupplierPayload = {
        ...form,
        contract_renewal_date: form.contract_renewal_date || null,
        contact_email: form.contact_email || null,
        notes: form.notes || null,
      };
      const created = await createSupplier(payload);
      setSuppliers((prev) => [...prev, created]);
      setForm(EMPTY_FORM);
      setSubmitSuccess(true);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Could not register supplier.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-5xl mx-auto px-6 py-10">
      <Link href="/" className="text-sm text-slate-400 hover:text-slate-200">
        &larr; Back to backoffice
      </Link>

      <h1 className="text-2xl font-semibold mt-4">Supplier directory</h1>
      <p className="text-slate-400 text-sm mt-2 max-w-xl">
        Nexova&apos;s official supplier registry -- replaces the shared
        spreadsheet. Filter, register new suppliers, and update rates or
        status directly from here.
      </p>

      <div className="flex flex-wrap gap-3 mt-6">
        <select
          value={countryFilter}
          onChange={(e) => setCountryFilter(e.target.value as Country | "")}
          className="bg-slate-900 border border-slate-800 rounded-md px-3 py-2 text-sm"
        >
          <option value="">All countries</option>
          <option value="Spain">Spain</option>
          <option value="USA">USA</option>
        </select>

        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value as Category | "")}
          className="bg-slate-900 border border-slate-800 rounded-md px-3 py-2 text-sm"
        >
          <option value="">All categories</option>
          {ALL_CATEGORIES.map((cat) => (
            <option key={cat} value={cat}>
              {CATEGORY_LABELS[cat]}
            </option>
          ))}
        </select>
      </div>

      {loading && <p className="mt-6 text-sm text-slate-400">Loading suppliers...</p>}
      {!loading && error && (
        <div className="mt-6 border border-red-900 bg-red-950/50 text-red-300 text-sm rounded-md px-4 py-3 flex items-center justify-between">
          <span>{error}</span>
          {/* M3: this error state previously had no retry, unlike the
              incidents list which does the equivalent thing. The table
              area just rendered empty with no way forward. */}
          <button onClick={() => void fetchSuppliers()} className="underline ml-4">
            Retry
          </button>
        </div>
      )}
      {rowError && (
        <div className="mt-4 border border-red-900 bg-red-950/50 text-red-300 text-sm rounded-md px-4 py-3 flex items-center justify-between">
          <span>{rowError}</span>
          {/* L1: same fix as incidents/list/page.tsx -- this banner
              previously had no dismiss control. */}
          <button onClick={() => setRowError(null)} className="text-slate-400 hover:text-slate-200 ml-4" aria-label="Dismiss">
            &times;
          </button>
        </div>
      )}

      {!loading && !error && (
        <div className="mt-6 overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="text-left text-slate-400 border-b border-slate-800">
              <tr>
                <th className="py-2 pr-4">Name</th>
                <th className="py-2 pr-4">Country</th>
                <th className="py-2 pr-4">Categories</th>
                <th className="py-2 pr-4">Rate</th>
                <th className="py-2 pr-4">Status</th>
                <th className="py-2 pr-4">Renewal</th>
                <th className="py-2 pr-4"></th>
              </tr>
            </thead>
            <tbody>
              {suppliers.length === 0 && (
                <tr>
                  <td colSpan={7} className="py-6 text-center text-slate-500">
                    No suppliers match the current filters.
                  </td>
                </tr>
              )}
              {suppliers.map((s) => {
                const soon =
                  s.contract_renewal_date !== null &&
                  daysUntil(s.contract_renewal_date) >= 0 &&
                  daysUntil(s.contract_renewal_date) <= 60;
                return (
                  <tr key={s.id} className="border-b border-slate-900">
                    <td className="py-3 pr-4">{s.name}</td>
                    <td className="py-3 pr-4">{s.country}</td>
                    <td className="py-3 pr-4">
                      {s.categories.map((c) => CATEGORY_LABELS[c]).join(", ")}
                    </td>
                    <td className="py-3 pr-4">
                      {editingRateId === s.id ? (
                        <span className="flex items-center gap-2">
                          <input
                            type="number"
                            value={rateDraft}
                            onChange={(e) => setRateDraft(e.target.value)}
                            className="w-24 bg-slate-900 border border-slate-700 rounded px-2 py-1"
                          />
                          <button
                            onClick={() => saveRate(s.id)}
                            className="text-emerald-400 text-xs"
                          >
                            Save
                          </button>
                          <button onClick={cancelEditRate} className="text-slate-500 text-xs">
                            Cancel
                          </button>
                        </span>
                      ) : (
                        <span
                          onClick={() => startEditRate(s)}
                          className="cursor-pointer hover:underline"
                        >
                          {/* L4: toFixed() throws if the API ever returns
                              null/undefined for this field instead of a
                              number. */}
                          {(s.monthly_rate ?? 0).toFixed(2)} {s.currency}
                        </span>
                      )}
                    </td>
                    <td className="py-3 pr-4">
                      <span
                        className={`inline-block px-2 py-0.5 rounded-full text-xs ${
                          s.status === "active"
                            ? "bg-emerald-900/50 text-emerald-300"
                            : "bg-amber-900/50 text-amber-300"
                        }`}
                      >
                        {s.status}
                      </span>
                    </td>
                    <td className="py-3 pr-4">
                      {s.contract_renewal_date ? (
                        <span className={soon ? "text-amber-400 font-medium" : "text-slate-400"}>
                          {s.contract_renewal_date}
                          {soon ? " (soon)" : ""}
                        </span>
                      ) : (
                        <span className="text-slate-600">--</span>
                      )}
                    </td>
                    <td className="py-3 pr-4">
                      <button
                        onClick={() => toggleStatus(s)}
                        className="text-xs border border-slate-700 rounded px-2 py-1 hover:bg-slate-800"
                      >
                        {s.status === "active" ? "Suspend" : "Activate"}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <section className="mt-10">
        <h2 className="text-lg font-semibold mb-4">Register a new supplier</h2>
        <form onSubmit={handleSubmit} className="space-y-4 max-w-lg">
          <div>
            <label className="block text-sm text-slate-400 mb-1">Name</label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => updateForm("name", e.target.value)}
              className="w-full bg-slate-900 border border-slate-800 rounded-md px-3 py-2 text-sm"
            />
            {formErrors.name && <p className="text-xs text-red-400 mt-1">{formErrors.name}</p>}
          </div>

          <div>
            <label className="block text-sm text-slate-400 mb-1">Country</label>
            <select
              value={form.country}
              onChange={(e) => handleCountryChange(e.target.value as Country)}
              className="w-full bg-slate-900 border border-slate-800 rounded-md px-3 py-2 text-sm"
            >
              <option value="Spain">Spain</option>
              <option value="USA">USA</option>
            </select>
            <p className="text-xs text-slate-500 mt-1">Currency: {form.currency}</p>
          </div>

          <div>
            <label className="block text-sm text-slate-400 mb-1">Categories</label>
            <div className="grid grid-cols-2 gap-2">
              {ALL_CATEGORIES.map((cat) => (
                <label key={cat} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={form.categories.includes(cat)}
                    onChange={() => toggleFormCategory(cat)}
                  />
                  {CATEGORY_LABELS[cat]}
                </label>
              ))}
            </div>
            {formErrors.categories && (
              <p className="text-xs text-red-400 mt-1">{formErrors.categories}</p>
            )}
          </div>

          <div>
            <label className="block text-sm text-slate-400 mb-1">Monthly rate</label>
            <input
              type="number"
              value={form.monthly_rate || ""}
              onChange={(e) => updateForm("monthly_rate", Number(e.target.value))}
              className="w-full bg-slate-900 border border-slate-800 rounded-md px-3 py-2 text-sm"
            />
            {formErrors.monthly_rate && (
              <p className="text-xs text-red-400 mt-1">{formErrors.monthly_rate}</p>
            )}
          </div>

          <div>
            <label className="block text-sm text-slate-400 mb-1">
              Contract renewal date (optional)
            </label>
            <input
              type="date"
              value={form.contract_renewal_date || ""}
              onChange={(e) => updateForm("contract_renewal_date", e.target.value)}
              className="w-full bg-slate-900 border border-slate-800 rounded-md px-3 py-2 text-sm"
            />
          </div>

          <div>
            <label className="block text-sm text-slate-400 mb-1">
              Contact email (optional)
            </label>
            <input
              type="email"
              value={form.contact_email || ""}
              onChange={(e) => updateForm("contact_email", e.target.value)}
              className="w-full bg-slate-900 border border-slate-800 rounded-md px-3 py-2 text-sm"
            />
          </div>

          <div>
            <label className="block text-sm text-slate-400 mb-1">Notes (optional)</label>
            <textarea
              value={form.notes || ""}
              onChange={(e) => updateForm("notes", e.target.value)}
              className="w-full bg-slate-900 border border-slate-800 rounded-md px-3 py-2 text-sm"
              rows={3}
            />
          </div>

          {submitError && (
            <div className="border border-red-900 bg-red-950/50 text-red-300 text-sm rounded-md px-4 py-3">
              {submitError}
            </div>
          )}
          {submitSuccess && (
            <div className="border border-emerald-900 bg-emerald-950/50 text-emerald-300 text-sm rounded-md px-4 py-3">
              Supplier registered successfully.
            </div>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="bg-slate-100 text-slate-900 text-sm font-medium px-4 py-2 rounded-md disabled:opacity-50"
          >
            {submitting ? "Registering..." : "Register supplier"}
          </button>
        </form>
      </section>
    </div>
  );
}
