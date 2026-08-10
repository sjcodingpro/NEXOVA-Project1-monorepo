"use client";

import { useCallback, useMemo } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import type { StatusValue, StageValue, RecordsQueryParams } from "@/types/candidate";

/**
 * Keeps status/stage/search filters in the URL query string so the list
 * view is shareable and survives a refresh, per the milestone requirement.
 */
export function useRecordsFilters() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const status = (searchParams.get("status") as StatusValue | null) ?? undefined;
  const stage = (searchParams.get("stage") as StageValue | null) ?? undefined;
  const search = searchParams.get("search") ?? "";

  const setParam = useCallback(
    (key: string, value: string | undefined) => {
      const params = new URLSearchParams(searchParams.toString());
      if (value) {
        params.set(key, value);
      } else {
        params.delete(key);
      }
      router.replace(`${pathname}?${params.toString()}`);
    },
    [router, pathname, searchParams]
  );

  const setStatus = useCallback(
    (value: StatusValue | "") => setParam("status", value || undefined),
    [setParam]
  );
  const setStage = useCallback(
    (value: StageValue | "") => setParam("stage", value || undefined),
    [setParam]
  );
  const setSearch = useCallback(
    (value: string) => setParam("search", value || undefined),
    [setParam]
  );

  // Passed straight into api.listCandidates() — the API does server-side
  // filtering/search, so we refetch on change rather than filtering client-side.
  const queryParams: RecordsQueryParams = useMemo(
    () => ({
      status,
      stage,
      search: search || undefined,
      limit: 100,
    }),
    [status, stage, search]
  );

  return { status, stage, search, setStatus, setStage, setSearch, queryParams };
}
