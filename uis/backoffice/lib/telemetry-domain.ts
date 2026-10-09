// Telemetry domain assumptions.
//
// The NXV-0201 inventory model (Asset/AssetEntry/AssetExit) has no concept
// of programmes, unit costs or recipient roles, which the telemetry plan
// requires. Per instructor guidance, these values are defined here, as
// close to the Nexova CONTEXT as possible. Everything assumed lives in
// this one file so it can be reviewed or replaced in a single place.

export const PROGRAMMES = ["b2b-sales", "basic-leadership", "support-onboarding"] as const;
export type ProgrammeId = (typeof PROGRAMMES)[number];

export const RECIPIENT_ROLES = ["client", "candidate", "consultant", "support_agent"] as const;
export type RecipientRole = (typeof RECIPIENT_ROLES)[number];

// Must match LOW_STOCK_THRESHOLD in app/inventory/products/page.tsx.
export const MINIMUM_STOCK_THRESHOLD = 10;
export const COST_VARIANCE_THRESHOLD = 0.1;

const PROGRAMME_BY_SKU: Record<string, ProgrammeId> = {
  "NXV-TRN-001": "basic-leadership",
  "NXV-IT-001": "support-onboarding",
  "NXV-IT-002": "support-onboarding",
  "NXV-PER-001": "support-onboarding",
  "NXV-PER-002": "support-onboarding",
  "NXV-OFF-001": "b2b-sales",
};

const PROGRAMME_BY_CATEGORY: Record<string, ProgrammeId> = {
  training_materials: "basic-leadership",
  hardware: "support-onboarding",
  peripherals: "support-onboarding",
  office_supplies: "b2b-sales",
};

export function programmeFor(sku: string, category: string): ProgrammeId {
  return PROGRAMME_BY_SKU[sku] ?? PROGRAMME_BY_CATEGORY[category] ?? "support-onboarding";
}

export function telemetryCategory(category: string): "training_kit" | "onboarding_equipment" {
  return category === "training_materials" ? "training_kit" : "onboarding_equipment";
}

export function officeId(office: string): "valencia" | "miami" {
  return office.toLowerCase() === "miami" ? "miami" : "valencia";
}

export function currencyFor(office: string): "EUR" | "USD" {
  return officeId(office) === "miami" ? "USD" : "EUR";
}

/** "TechDistrib Valencia S.L." -> "techdistrib-valencia-s-l" (stable supplier key). */
export function supplierId(name: string): string {
  return name.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
}

const COST_HISTORY_KEY = "nexova_telemetry_cost_history";

/**
 * Compares an inbound unit cost with the running average for the same
 * SKU + supplier, then records it. Returns null unless there is history
 * AND the deviation exceeds COST_VARIANCE_THRESHOLD.
 * NOTE: history lives in this browser only; a later phase should move it
 * server-side.
 */
export function checkCostVariance(
  sku: string,
  supplier: string,
  unitCost: number
): { historical: number; variancePct: number } | null {
  const key = `${sku}::${supplier.trim().toLowerCase()}`;
  let history: Record<string, { avg: number; n: number }> = {};
  try {
    history = JSON.parse(localStorage.getItem(COST_HISTORY_KEY) ?? "{}");
  } catch {
    // storage unavailable: no history, no variance
  }
  const prior = history[key];
  let result: { historical: number; variancePct: number } | null = null;
  if (prior && prior.avg > 0) {
    const variancePct = (unitCost - prior.avg) / prior.avg;
    if (Math.abs(variancePct) > COST_VARIANCE_THRESHOLD) {
      result = { historical: prior.avg, variancePct: Math.round(variancePct * 1000) / 1000 };
    }
  }
  const n = (prior?.n ?? 0) + 1;
  history[key] = { avg: ((prior?.avg ?? 0) * (n - 1) + unitCost) / n, n };
  try {
    localStorage.setItem(COST_HISTORY_KEY, JSON.stringify(history));
  } catch {
    // ignore
  }
  return result;
}
