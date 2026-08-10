"use client";

import Link from "next/link";
import { STATUS_LABELS, STAGE_LABELS } from "@/lib/labels";
import type { Candidate } from "@/types/candidate";

export function CandidateTable({ candidates }: { candidates: Candidate[] }) {
  if (candidates.length === 0) {
    return (
      <div className="text-center text-sm text-gray-500 py-12 border rounded-md">
        No candidates match the current filters.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto border rounded-md">
      <table className="min-w-full text-sm">
        <thead className="bg-gray-50 text-left">
          <tr>
            <th className="px-4 py-2 font-medium">Name</th>
            <th className="px-4 py-2 font-medium">Position</th>
            <th className="px-4 py-2 font-medium">Status</th>
            <th className="px-4 py-2 font-medium">Stage</th>
          </tr>
        </thead>
        <tbody>
          {candidates.map((c) => (
            <tr key={c.id} className="border-t hover:bg-gray-50">
              <td className="px-4 py-2">
                <Link href={`/candidates/${c.id}`} className="text-blue-600 hover:underline">
                  {c.full_name}
                </Link>
              </td>
              <td className="px-4 py-2">{c.position}</td>
              <td className="px-4 py-2">{STATUS_LABELS[c.status]}</td>
              <td className="px-4 py-2">{STAGE_LABELS[c.stage]}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
