import type {
  Supplier,
  CreateSupplierPayload,
  Country,
  Category,
  SupplierStatus,
  ApiErrorBody,
} from "@/types/suppliers";

const BASE_URL = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "");

if (!BASE_URL) {
  throw new Error("NEXT_PUBLIC_API_URL is not set. Check your .env.local.");
}

async function parseErrorDetail(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as ApiErrorBody;
    if (Array.isArray(body?.detail)) {
      return body.detail.map((d) => d.msg).join(" ");
    }
    if (typeof body?.detail === "string") {
      return body.detail;
    }
  } catch {
    // response wasn't JSON; fall through
  }
  return res.statusText || `Request failed with status ${res.status}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...init?.headers,
      },
    });
  } catch {
    throw new Error("Could not reach the API. Is the server running?");
  }

  if (!res.ok) {
    throw new Error(await parseErrorDetail(res));
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return (await res.json()) as T;
}

export function listSuppliers(filters?: {
  country?: Country;
  category?: Category;
}): Promise<Supplier[]> {
  const params = new URLSearchParams();
  if (filters?.country) params.set("country", filters.country);
  if (filters?.category) params.set("category", filters.category);
  const qs = params.toString();
  return request<Supplier[]>(`/suppliers${qs ? `?${qs}` : ""}`);
}

export function createSupplier(payload: CreateSupplierPayload): Promise<Supplier> {
  return request<Supplier>("/suppliers", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateSupplierRate(id: number, monthly_rate: number): Promise<Supplier> {
  return request<Supplier>(`/suppliers/${id}/rate`, {
    method: "PATCH",
    body: JSON.stringify({ monthly_rate }),
  });
}

export function updateSupplierStatus(
  id: number,
  status: SupplierStatus
): Promise<Supplier> {
  return request<Supplier>(`/suppliers/${id}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}
