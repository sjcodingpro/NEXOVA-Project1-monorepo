"use client";

import { useState } from "react";
import type { CreateCandidatePayload } from "@/types/candidate";

interface Props {
  initialValues?: CreateCandidatePayload;
  onSubmit: (payload: CreateCandidatePayload) => Promise<void>;
  submitLabel: string;
}

const EMPTY: CreateCandidatePayload = {
  full_name: "",
  email: "",
  phone: "",
  position: "",
  linkedin_url: "",
  cv_url: "",
  experience_years: 0,
};

export function CandidateForm({ initialValues, onSubmit, submitLabel }: Props) {
  const [values, setValues] = useState<CreateCandidatePayload>(initialValues ?? EMPTY);
  const [errors, setErrors] = useState<Partial<Record<keyof CreateCandidatePayload, string>>>({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  function validate(): boolean {
    const next: typeof errors = {};
    if (!values.full_name.trim()) next.full_name = "Full name is required.";
    if (!values.email.trim()) next.email = "Email is required.";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(values.email)) next.email = "Enter a valid email.";
    if (!values.phone.trim()) next.phone = "Phone is required.";
    if (!values.position.trim()) next.position = "Position is required.";
    if (!values.cv_url.trim()) next.cv_url = "CV link is required.";
    if (values.experience_years < 0) next.experience_years = "Must be 0 or more.";
    setErrors(next);
    return Object.keys(next).length === 0;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitError(null);
    if (!validate()) return;
    setSubmitting(true);
    try {
      await onSubmit({
        ...values,
        linkedin_url: values.linkedin_url?.trim() ? values.linkedin_url.trim() : null,
      });
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  function field<K extends keyof CreateCandidatePayload>(key: K, value: CreateCandidatePayload[K]) {
    setValues((prev) => ({ ...prev, [key]: value }));
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 max-w-lg">
      <div>
        <label className="block text-sm text-gray-500 mb-1">Full name</label>
        <input
          type="text"
          value={values.full_name}
          onChange={(e) => field("full_name", e.target.value)}
          className="border rounded-md px-3 py-2 text-sm w-full"
        />
        {errors.full_name && <p className="text-xs text-red-600 mt-1">{errors.full_name}</p>}
      </div>

      <div>
        <label className="block text-sm text-gray-500 mb-1">Email</label>
        <input
          type="email"
          value={values.email}
          onChange={(e) => field("email", e.target.value)}
          className="border rounded-md px-3 py-2 text-sm w-full"
        />
        {errors.email && <p className="text-xs text-red-600 mt-1">{errors.email}</p>}
      </div>

      <div>
        <label className="block text-sm text-gray-500 mb-1">Phone</label>
        <input
          type="text"
          value={values.phone}
          onChange={(e) => field("phone", e.target.value)}
          className="border rounded-md px-3 py-2 text-sm w-full"
        />
        {errors.phone && <p className="text-xs text-red-600 mt-1">{errors.phone}</p>}
      </div>

      <div>
        <label className="block text-sm text-gray-500 mb-1">Position</label>
        <input
          type="text"
          value={values.position}
          onChange={(e) => field("position", e.target.value)}
          className="border rounded-md px-3 py-2 text-sm w-full"
        />
        {errors.position && <p className="text-xs text-red-600 mt-1">{errors.position}</p>}
      </div>

      <div>
        <label className="block text-sm text-gray-500 mb-1">LinkedIn (optional)</label>
        <input
          type="text"
          value={values.linkedin_url ?? ""}
          onChange={(e) => field("linkedin_url", e.target.value)}
          className="border rounded-md px-3 py-2 text-sm w-full"
        />
      </div>

      <div>
        <label className="block text-sm text-gray-500 mb-1">CV link</label>
        <input
          type="text"
          value={values.cv_url}
          onChange={(e) => field("cv_url", e.target.value)}
          className="border rounded-md px-3 py-2 text-sm w-full"
        />
        {errors.cv_url && <p className="text-xs text-red-600 mt-1">{errors.cv_url}</p>}
      </div>

      <div>
        <label className="block text-sm text-gray-500 mb-1">Years of experience</label>
        <input
          type="number"
          min={0}
          value={values.experience_years}
          onChange={(e) => field("experience_years", Number(e.target.value))}
          className="border rounded-md px-3 py-2 text-sm w-full"
        />
        {errors.experience_years && (
          <p className="text-xs text-red-600 mt-1">{errors.experience_years}</p>
        )}
      </div>

      {submitError && (
        <div className="border border-red-200 bg-red-50 text-red-700 text-sm rounded-md px-4 py-3">
          {submitError}
        </div>
      )}

      <button
        type="submit"
        disabled={submitting}
        className="bg-black text-white text-sm font-medium px-4 py-2 rounded-md disabled:opacity-50"
      >
        {submitting ? "Saving…" : submitLabel}
      </button>
    </form>
  );
}
