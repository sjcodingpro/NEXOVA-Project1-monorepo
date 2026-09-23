"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { useRequireAuth } from "@/lib/useRequireAuth";
import { inventoryApi } from "@/lib/inventory";
import type { Asset, ExitType, Office } from "@/types/inventory";

const OFFICES: Office[] = ["Valencia", "Miami"];

// Same Suspense requirement as the inbound form -- see its comment.
export default function OutboundOrderPage() {
  return (
    <Suspense fallback={<div className="max-w-lg mx-auto px-6 py-10 text-sm text-slate-400">Loading...</div>}>
      <OutboundOrderForm />
    </Suspense>
  );
}

function OutboundOrderForm() {
  const authed = useRequireAuth();
  const searchParams = useSearchParams();

  const [products, setProducts] = useState<Asset[]>([]);
  const [loadingProducts, setLoadingProducts] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [assetId, setAssetId] = useState<string>("");
  const [quantity, setQuantity] = useState<string>("");
  const [exitType, setExitType] = useState<ExitType>("consumption");
  const [assignedTo, setAssignedTo] = useState("");
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

  // Reactive stock lookup -- derived directly from the already-fetched
  // products list rather than a fresh request per selection change, so
  // it updates instantly (no loading flicker) whenever assetId changes.
  const selectedAsset = useMemo(
    () => products.find((p) => String(p.id) === assetId) ?? null,
    [products, assetId]
  );

  const parsedQuantity = Number(quantity);
  const exceedsStock =
    selectedAsset !== null &&
    Number.isFinite(parsedQuantity) &&
    parsedQuantity > 0 &&
    parsedQuantity > selectedAsset.current_stock;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitError(null);
    setSubmitSuccess(false);

    if (!assetId) {
      setSubmitError("Select an asset.");
      return;
    }
    if (!Number.isFinite(parsedQuantity) || parsedQuantity <= 0) {
      setSubmitError("Quantity must be a positive number.");
      return;
    }
    if (exitType === "allocation" && !assignedTo.trim()) {
      setSubmitError("Assigned to is required for an allocation.");
      return;
    }
    // Client-side guard -- a UX nicety, not the authoritative rule.
    // The API is what actually rejects an over-quantity exit; this
    // just stops the user from submitting one they can already see is
    // wrong, without waiting on a round trip.
    if (exceedsStock && selectedAsset) {
      setSubmitError(
        `Only ${selectedAsset.current_stock} unit(s) of ${selectedAsset.name} are available.`
      );
      return;
    }

    setSubmitting(true);
    try {
      await inventoryApi.createOutboundOrder({
        asset_id: Number(assetId),
        quantity: parsedQuantity,
        exit_type: exitType,
        assigned_to: exitType === "allocation" ? assignedTo.trim() : null,
        office,
      });
      setSubmitSuccess(true);
      setAssetId("");
      setQuantity("");
      setExitType("consumption");
      setAssignedTo("");
      setOffice("Valencia");
      void fetchProducts(); // refresh stock numbers immediately
    } catch (err) {
      // The API's own 400 (insufficient stock) or 422 (assigned_to
      // validation) message lands here verbatim -- same banner either
      // way, rendered right below the quantity field.
      setSubmitError(err instanceof Error ? err.message : "Could not register the exit.");
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
      <h1 className="text-2xl font-semibold mt-4">Log an exit</h1>
      <p className="text-slate-400 text-sm mt-1">
        Register an asset exit -- an allocation to an employee, or a consumption event.
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
            {selectedAsset && (
              <p className="text-xs text-slate-500 mt-1" data-testid="available-stock">
                Available stock: <span className="text-slate-300">{selectedAsset.current_stock}</span>
              </p>
            )}
          </div>

          <div>
            <label className="block text-sm text-slate-400 mb-1">Quantity</label>
            <input
              type="number"
              min="1"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              className="w-full bg-slate-900 border border-slate-800 rounded-md px-3 py-2 text-sm"
            />
            {exceedsStock && selectedAsset && (
              <p className="text-xs text-amber-400 mt-1" data-testid="exceeds-stock-warning">
                Only {selectedAsset.current_stock} unit(s) available -- this exceeds current stock.
              </p>
            )}
          </div>

          <div>
            <label className="block text-sm text-slate-400 mb-1">Exit type</label>
            <select
              value={exitType}
              onChange={(e) => {
                const next = e.target.value as ExitType;
                setExitType(next);
                if (next === "consumption") setAssignedTo("");
              }}
              className="w-full bg-slate-900 border border-slate-800 rounded-md px-3 py-2 text-sm"
            >
              <option value="consumption">Consumption</option>
              <option value="allocation">Allocation</option>
            </select>
          </div>

          {exitType === "allocation" && (
            <div>
              <label className="block text-sm text-slate-400 mb-1">Assigned to</label>
              <input
                type="text"
                value={assignedTo}
                onChange={(e) => setAssignedTo(e.target.value)}
                placeholder="Employee name"
                className="w-full bg-slate-900 border border-slate-800 rounded-md px-3 py-2 text-sm"
              />
            </div>
          )}

          <div>
            <label className="block text-sm text-slate-400 mb-1">Office</label>
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
              Exit logged successfully.
            </div>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="bg-slate-100 text-slate-900 text-sm font-medium px-4 py-2 rounded-md disabled:opacity-50"
          >
            {submitting ? "Logging..." : "Log exit"}
          </button>
        </form>
      )}
    </div>
  );
}
