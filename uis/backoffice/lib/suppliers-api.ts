import type {
  Supplier,
  CreateSupplierPayload,
  Country,
  Category,
  SupplierStatus,
} from "@/types/suppliers";
import { apiFetch } from "@/lib/api-client";

export function listSuppliers(filters?: {
  country?: Country;
  category?: Category;
}): Promise<Supplier[]> {
  const params = new URLSearchParams();
  if (filters?.country) params.set("country", filters.country);
  if (filters?.category) params.set("category", filters.category);
  const qs = params.toString();
  return apiFetch<Supplier[]>(`/suppliers${qs ? `?${qs}` : ""}`);
}

export function createSupplier(payload: CreateSupplierPayload): Promise<Supplier> {
  return apiFetch<Supplier>("/suppliers", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateSupplierRate(id: number, monthly_rate: number): Promise<Supplier> {
  return apiFetch<Supplier>(`/suppliers/${id}/rate`, {
    method: "PATCH",
    body: JSON.stringify({ monthly_rate }),
  });
}

export function updateSupplierStatus(
  id: number,
  status: SupplierStatus
): Promise<Supplier> {
  return apiFetch<Supplier>(`/suppliers/${id}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}
