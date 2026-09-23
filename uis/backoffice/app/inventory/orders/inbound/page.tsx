"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { useRequireAuth } from "@/lib/useRequireAuth";
import { inventoryApi } from "@/lib/inventory";
import type { Asset, Office } from "@/types/inventory";

const OFFICES: Office[] = ["Valencia", "Miami"];

// useSearchParams() opts a page out of static generation unless it's
// wrapped in Suspense -- Next's build fails outright otherwise
// ("should be wrapped in a suspense boundary"). The actual form lives
// in the inner component below; this default export just supplies the
// boundary. Nothing here actually suspends during a normal client
// render, so the fallback is only ever seen for an instant, if at all.
export default function InboundOrderPage() {
  return (
    <Suspense fallback={<div className="max-w-lg mx-auto px-6 py-10 text-sm text-slate-400">Loading...</div>}>
      <InboundOrderForm />
    </Suspense>
  );
}

function InboundOrderForm() {
  const authed = useRequireAuth();
  const searchParams = useSearchParams();

  const [products, setProducts] = useState<Asset[]>([]);
  const [loadingProducts, setLoadingProducts] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [assetId, setAssetId] = useState<string>("");
  const [quantity, setQuantity] = useState<string>("");
  const [supplier, setSupplier] = useState("");
  const [office, setOffice] = useState<Office>("Valencia");

  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitSuccess, setSubmitSuccess] = useState(false);

  const fetchProducts = useCallback(async () => {
    setLoadingProducts(true);
    setLoadError(null);
    try {
      const data = await inventoryApi.listProducts();
      setProducts(data);
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Could not load assets.");
    } finally {
      setLoadingProducts(false);
    }
  }, []);

  useEffect(() => {
    if (!authed) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void fetchProducts();
  }, [authed, fetchProducts]);

  useEffect(() => {
    const preselect = searchParams.get("asset_id");
    if (preselect) setAssetId(preselect);
  }, [searchParams]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitError(null);
    setSubmitSuccess(false);

    const parsedQuantity = Number(quantity);
    if (!assetId) {
      setSubmitError("Select an asset.");
      return;
    }
    if (!Number.isFinite(parsedQuantity) || parsedQuantity <= 0) {
      setSubmitError("Quantity must be a positive number.");
      return;
    }
    if (!supplier.trim()) {
      setSubmitError("Supplier is required.");
      return;
    }

    setSubmitting(true);
    try {
      await inventoryApi.createInboundOrder({
        asset_id: Number(assetId),
        quantity: parsedQuantity,
        supplier: supplier.trim(),
        office,
      });
      setSubmitSuccess(true);
      setAssetId("");
      setQuantity("");
      setSupplier("");
      setOffice("Valencia");
      void fetchProducts(); // refresh stock numbers for the next entry
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Could not register the delivery.");
    } finally {
      setSubmitting(false);
    }
  }

  if (!authed) return null;

  return (
    <div className="max-w-lg mx-auto px-6 py-10">
      <Link href="/inventory/products" className="text-sm text-slate-400 hover:text-slate-200">
        &larr; Back to assets
      </Link>
      <h1 className="text-2xl font-semibold mt-4">Log a delivery</h1>
      <p className="text-slate-400 text-sm mt-1">
        Register an asset entry -- a purchase or supplier delivery received by Nexova.
      </p>

      {loadingProducts && <p className="mt-6 text-sm text-slate-400">Loading assets...</p>}
      {!loadingProducts && loadError && (
        <div className="mt-6 border border-red-900 bg-red-950/50 text-red-300 text-sm rounded-md px-4 py-3 flex items-center justify-between">
          <span>{loadError}</span>
          <button onClick={() => void fetchProducts()} className="underline ml-4">
            Retry
          </button>
        </div>
      )}

      {!loadingProducts && !loadError && (
        <form onSubmit={handleSubmit} className="space-y-4 mt-8">
          <div>
            <label className="block text-sm text-slate-400 mb-1">Asset</label>
            <select
              value={assetId}
              onChange={(e) => setAssetId(e.target.value)}
              className="w-full bg-slate-900 border border-slate-800 rounded-md px-3 py-2 text-sm"
            >
              <option value="">Select an asset&hellip;</option>
              {products.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.sku}) &mdash; {p.office}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm text-slate-400 mb-1">Quantity received</label>
            <input
              type="number"
              min="1"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              className="w-full bg-slate-900 border border-slate-800 rounded-md px-3 py-2 text-sm"
            />
          </div>

          <div>
            <label className="block text-sm text-slate-400 mb-1">Supplier</label>
            <input
              type="text"
              value={supplier}
              onChange={(e) => setSupplier(e.target.value)}
              placeholder="e.g. TechDistrib Valencia S.L."
              className="w-full bg-slate-900 border border-slate-800 rounded-md px-3 py-2 text-sm"
            />
          </div>

          <div>
            <label className="block text-sm text-slate-400 mb-1">Receiving office</label>
            <select
              value={office}
              onChange={(e) => setOffice(e.target.value as Office)}
              className="w-full bg-slate-900 border border-slate-800 rounded-md px-3 py-2 text-sm"
            >
              {OFFICES.map((o) => (
                <option key={o} value={o}>
                  {o}
                </option>
              ))}
            </select>
          </div>

          {submitError && (
            <div className="border border-red-900 bg-red-950/50 text-red-300 text-sm rounded-md px-4 py-3">
              {submitError}
            </div>
          )}
          {submitSuccess && (
            <div className="border border-emerald-900 bg-emerald-950/50 text-emerald-300 text-sm rounded-md px-4 py-3">
              Delivery logged successfully.
            </div>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="bg-slate-100 text-slate-900 text-sm font-medium px-4 py-2 rounded-md disabled:opacity-50"
          >
            {submitting ? "Logging..." : "Log delivery"}
          </button>
        </form>
      )}
    </div>
  );
}
