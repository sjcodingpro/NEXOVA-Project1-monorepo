"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRequireAuth } from "@/lib/useRequireAuth";
import { inventoryApi } from "@/lib/inventory";
import type { Order } from "@/types/inventory";

export default function InventoryOrdersPage() {
  const authed = useRequireAuth();
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchOrders = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await inventoryApi.listOrders();
      setOrders(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load orders.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!authed) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void fetchOrders();
  }, [authed, fetchOrders]);

  if (!authed) return null;

  return (
    <div className="max-w-5xl mx-auto px-6 py-10">
      <Link href="/inventory/products" className="text-sm text-slate-400 hover:text-slate-200">
        &larr; Back to assets
      </Link>
      <h1 className="text-2xl font-semibold mt-4">Order history</h1>
      <p className="text-slate-400 text-sm mt-1">
        Every asset entry and exit, newest first. Read-only.
      </p>

      {loading && <p className="mt-6 text-sm text-slate-400">Loading orders...</p>}
      {!loading && error && (
        <div className="mt-6 border border-red-900 bg-red-950/50 text-red-300 text-sm rounded-md px-4 py-3 flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => void fetchOrders()} className="underline ml-4">
            Retry
          </button>
        </div>
      )}

      {!loading && !error && (
        <div className="mt-6 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-500 border-b border-slate-800">
                <th className="pb-3 pr-4">Type</th>
                <th className="pb-3 pr-4">Asset</th>
                <th className="pb-3 pr-4">Quantity</th>
                <th className="pb-3 pr-4">Detail</th>
                <th className="pb-3 pr-4">Date</th>
                <th className="pb-3 pr-4">Registered by</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((o) => (
                <tr key={`${o.order_type}-${o.id}`} className="border-b border-slate-900">
                  <td className="py-3 pr-4">
                    <span
                      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs border ${
                        o.order_type === "inbound"
                          ? "bg-emerald-900/50 text-emerald-300 border-emerald-800"
                          : "bg-sky-900/50 text-sky-300 border-sky-800"
                      }`}
                    >
                      {o.order_type === "inbound" ? "\u2193 Entry" : "\u2191 Exit"}
                    </span>
                  </td>
                  <td className="py-3 pr-4">
                    {o.asset_name} <span className="text-slate-500">({o.asset_sku})</span>
                  </td>
                  <td className="py-3 pr-4">{o.quantity}</td>
                  <td className="py-3 pr-4 text-slate-400">
                    {o.order_type === "inbound"
                      ? o.supplier
                      : o.exit_type === "allocation"
                        ? `Allocated to ${o.assigned_to}`
                        : "Consumed"}
                  </td>
                  <td className="py-3 pr-4 text-slate-400">
                    {new Date(o.created_at).toLocaleString()}
                  </td>
                  <td className="py-3 pr-4 text-slate-500 text-xs">{o.user_uuid}</td>
                </tr>
              ))}
              {orders.length === 0 && (
                <tr>
                  <td colSpan={6} className="py-6 text-center text-slate-500">
                    No orders logged yet.
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
