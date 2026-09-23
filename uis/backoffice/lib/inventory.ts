import { clearToken, getToken } from "@/lib/auth";
import type {
  Asset,
  AssetCreatePayload,
  AssetEntry,
  AssetEntryCreatePayload,
  AssetExit,
  AssetExitCreatePayload,
  Order,
} from "@/types/inventory";

// Separate from the auth API's base URL by design -- the README asks
// for a dedicated NEXT_PUBLIC_INVENTORY_API_URL, and even though this
// currently points at the same backend service as NEXT_PUBLIC_API_URL,
// keeping it as its own env var (rather than quietly reusing the other
// one) means the inventory API can be pointed at a different host later
// without touching anything auth-related.
function getInventoryBaseUrl(): string {
  const url = process.env.NEXT_PUBLIC_INVENTORY_API_URL?.replace(/\/$/, "");
  if (!url) {
    throw new Error("NEXT_PUBLIC_INVENTORY_API_URL is not set. Check your .env.local.");
  }
  return url;
}

interface ApiErrorBody {
  detail?: string | { msg?: string }[];
}

async function extractErrorMessage(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as ApiErrorBody;
    // FastAPI/pydantic validation errors (422) come back as
    // { detail: [{ msg, ... }] }; hand-raised HTTPExceptions (400, 404)
    // come back as { detail: "..." } -- both are real shapes this API
    // actually returns (confirmed live against both /orders/outbound's
    // insufficient-stock 400 and its allocation-validation 422).
    if (Array.isArray(body?.detail)) {
      return body.detail.map((d) => d.msg).filter(Boolean).join(" ") || res.statusText;
    }
    if (typeof body?.detail === "string") {
      return body.detail;
    }
  } catch {
    // response wasn't JSON -- fall through to statusText
  }
  return res.statusText || `Request failed with status ${res.status}`;
}

async function inventoryFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const baseUrl = getInventoryBaseUrl();
  const token = getToken();

  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...init?.headers,
  };

  let res: Response;
  try {
    res = await fetch(`${baseUrl}${path}`, { ...init, headers });
  } catch {
    throw new Error("Could not reach the inventory service. Check your connection.");
  }

  if (res.status === 401) {
    if (token) {
      clearToken();
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
      throw new Error("Session expired. Please log in again.");
    }
    throw new Error(await extractErrorMessage(res));
  }

  if (!res.ok) {
    // Every 4xx/5xx surfaces its real message -- never a raw JSON blob,
    // never a silent failure, per the README's explicit requirement.
    throw new Error(await extractErrorMessage(res));
  }

  if (res.status === 204) {
    return undefined as T;
  }

  try {
    return (await res.json()) as T;
  } catch {
    throw new Error("Received an unexpected response from the inventory service.");
  }
}

export const inventoryApi = {
  listProducts(): Promise<Asset[]> {
    return inventoryFetch<Asset[]>("/inventory/products");
  },

  getProduct(id: number): Promise<Asset> {
    return inventoryFetch<Asset>(`/inventory/products/${id}`);
  },

  createProduct(payload: AssetCreatePayload): Promise<Asset> {
    return inventoryFetch<Asset>("/inventory/products", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  createInboundOrder(payload: AssetEntryCreatePayload): Promise<AssetEntry> {
    return inventoryFetch<AssetEntry>("/inventory/orders/inbound", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  createOutboundOrder(payload: AssetExitCreatePayload): Promise<AssetExit> {
    return inventoryFetch<AssetExit>("/inventory/orders/outbound", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listOrders(): Promise<Order[]> {
    return inventoryFetch<Order[]>("/inventory/orders");
  },
};
