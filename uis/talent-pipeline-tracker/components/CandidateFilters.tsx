"use client";

import { useEffect, useState } from "react";
import { STATUS_OPTIONS, STAGE_OPTIONS } from "@/lib/labels";
import type { StatusValue, StageValue } from "@/types/candidate";

interface Props {
  status?: StatusValue;
  stage?: StageValue;
  search: string;
  onStatusChange: (value: StatusValue | "") => void;
  onStageChange: (value: StageValue | "") => void;
  onSearchChange: (value: string) => void;
}

export function CandidateFilters({
  status,
  stage,
  search,
  onStatusChange,
  onStageChange,
  onSearchChange,
}: Props) {
  // Local, debounced copy so we don't refetch on every keystroke.
  const [searchInput, setSearchInput] = useState(search);

  useEffect(() => {
    setSearchInput(search);
  }, [search]);

  useEffect(() => {
    const timeout = setTimeout(() => {
      if (searchInput !== search) onSearchChange(searchInput);
    }, 400);
    return () => clearTimeout(timeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchInput]);

  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center mb-6">
      <input
        type="text"
        value={searchInput}
        onChange={(e) => setSearchInput(e.target.value)}
        placeholder="Search by name or email"
        className="border rounded-md px-3 py-2 text-sm flex-1"
      />
      <select
        value={status ?? ""}
        onChange={(e) => onStatusChange(e.target.value as StatusValue | "")}
        className="border rounded-md px-3 py-2 text-sm"
      >
        <option value="">All statuses</option>
        {STATUS_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
      <select
        value={stage ?? ""}
        onChange={(e) => onStageChange(e.target.value as StageValue | "")}
        className="border rounded-md px-3 py-2 text-sm"
      >
        <option value="">All stages</option>
        {STAGE_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}
