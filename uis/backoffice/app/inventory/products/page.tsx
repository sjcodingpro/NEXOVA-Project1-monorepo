"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRequireAuth } from "@/lib/useRequireAuth";
import { inventoryApi } from "@/lib/inventory";
import type { Asset } from "@/types/inventory";

const CATEGORY_LABELS: Record<string, string> = {
  hardware: "Hardware",
  peripherals: "Peripherals",
  office_supplies: "Office Supplies",
  training_materials: "Training Materials",
};

// Stock-level thresholds -- CONTEXT.md doesn't specify any, so these
// are our own, documented per the README's explicit requirement:
//   0 units          -> "Out of stock" (red)   -- nothing left at all
//   1-9 units        -> "Low stock" (amber)     -- worth reordering soon
//   10+ units        -> "Healthy" (green)
const LOW_STOCK_THRESHOLD = 10;

function stockBadge(stock: number) {
  if (stock === 0) {
    return { label: "Out of stock", className: "bg-red-900/50 text-red-300 border-red-800" };
  }
  if (stock < LOW_STOCK_THRESHOLD) {
    return { label: "Low stock", className: "bg-amber-900/50 text-amber-300 border-amber-800" };
  }
  return { label: "Healthy", className: "bg-emerald-900/50 text-emerald-300 border-emerald-800" };
}

export default function InventoryProductsPage() {
  const authed = useRequireAuth();
  const [products, setProducts] = useState<Asset[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchProducts = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await inventoryApi.listProducts();
      setProducts(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load assets.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!authed) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void fetchProducts();
  }, [authed, fetchProducts]);

  if (!authed) return null;

  return (
    <div className="max-w-5xl mx-auto px-6 py-10">
      <Link href="/" className="text-sm text-slate-400 hover:text-slate-200">
        &larr; Back to backoffice
      </Link>
      <div className="flex items-center justify-between mt-4 flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Assets</h1>
          <p className="text-slate-400 text-sm mt-1">
            Equipment and supplies inventory across all offices.
          </p>
        </div>
        <div className="flex gap-3">
          <Link
            href="/inventory/orders/inbound"
            className="bg-slate-100 text-slate-900 text-sm font-medium px-4 py-2 rounded-md"
          >
            Log delivery
          </Link>
          <Link
            href="/inventory/orders"
            className="border border-slate-700 text-sm font-medium px-4 py-2 rounded-md hover:bg-slate-900"
          >
            View order history
          </Link>
        </div>
      </div>

      {loading && <p className="mt-6 text-sm text-slate-400">Loading assets...</p>}

      {!loading && error && (
        <div className="mt-6 border border-red-900 bg-red-950/50 text-red-300 text-sm rounded-md px-4 py-3 flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => void fetchProducts()} className="underline ml-4">
            Retry
          </button>
        </div>
      )}

      {!loading && !error && (
        <div className="mt-6 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-500 border-b border-slate-800">
                <th className="pb-3 pr-4">Name</th>
                <th className="pb-3 pr-4">SKU</th>
                <th className="pb-3 pr-4">Category</th>
                <th className="pb-3 pr-4">Office</th>
                <th className="pb-3 pr-4">Current stock</th>
                <th className="pb-3 pr-4"></th>
              </tr>
            </thead>
            <tbody>
              {products.map((p) => {
                const badge = stockBadge(p.current_stock);
                return (
                  <tr key={p.id} className="border-b border-slate-900">
                    <td className="py-3 pr-4">{p.name}</td>
                    <td className="py-3 pr-4 text-slate-400">{p.sku}</td>
                    <td className="py-3 pr-4 text-slate-400">
                      {CATEGORY_LABELS[p.category] ?? p.category}
                    </td>
                    <td className="py-3 pr-4 text-slate-400">{p.office}</td>
                    <td className="py-3 pr-4">
                      <span
                        className={`inline-flex items-center gap-2 px-2 py-0.5 rounded-full text-xs border ${badge.className}`}
                      >
                        {p.current_stock} &middot; {badge.label}
                      </span>
                    </td>
                    <td className="py-3 pr-4 text-right whitespace-nowrap">
                      <Link
                        href={`/inventory/orders/inbound?asset_id=${p.id}`}
                        className="text-slate-400 hover:text-slate-200 underline text-xs mr-3"
                      >
                        Log delivery
                      </Link>
                      <Link
                        href={`/inventory/orders/outbound?asset_id=${p.id}`}
                        className="text-slate-400 hover:text-slate-200 underline text-xs"
                      >
                        Log exit
                      </Link>
                    </td>
                  </tr>
                );
              })}
              {products.length === 0 && (
                <tr>
                  <td colSpan={6} className="py-6 text-center text-slate-500">
                    No assets registered yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
