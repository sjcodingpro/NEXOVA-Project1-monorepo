import type { StatusValue, StageValue } from "@/types/candidate";

/**
 * Maps raw API status values to the labels Nexova's People & Talent team
 * uses. Raw values must never be rendered directly in the UI — always go
 * through this map.
 */
export const STATUS_LABELS: Record<StatusValue, string> = {
  received: "Received",
  in_progress: "In progress",
  selected: "Selected",
  discarded: "Discarded",
};

/**
 * Maps raw API stage values to the labels Nexova's People & Talent team
 * uses. Raw values must never be rendered directly in the UI — always go
 * through this map.
 */
export const STAGE_LABELS: Record<StageValue, string> = {
  pending: "Pending review",
  review: "Under review",
  personal_interview: "Personal interview",
  technical_interview: "Technical interview",
  offer_presented: "Offer presented",
};

export const STATUS_OPTIONS: { value: StatusValue; label: string }[] = (
  Object.keys(STATUS_LABELS) as StatusValue[]
).map((value) => ({ value, label: STATUS_LABELS[value] }));

export const STAGE_OPTIONS: { value: StageValue; label: string }[] = (
  Object.keys(STAGE_LABELS) as StageValue[]
).map((value) => ({ value, label: STAGE_LABELS[value] }));
