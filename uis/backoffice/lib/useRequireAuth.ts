"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getToken } from "@/lib/auth";

/**
 * Proactive route protection -- redirects to /login if there's no
 * token, on mount, before the page renders any protected content.
 *
 * The rest of the backoffice only has *reactive* protection:
 * apiFetch/inventoryFetch clear the token and redirect only after a
 * 401 comes back from a failed request. That's a real gap for a page
 * whose whole purpose is a form -- a user could fill the entire thing
 * out before ever discovering they weren't logged in. This hook closes
 * that gap for the inventory pages, which the milestone brief requires
 * explicitly ("If a user is not authenticated, redirect them to the
 * login page").
 *
 * Returns true once a token has been confirmed present, so callers can
 * gate rendering: `if (!authed) return null;`. Returns false both
 * while the check is still pending (first render, before the effect
 * has run) and once the redirect has been triggered -- either way the
 * caller should render nothing rather than a flash of protected content.
 */
export function useRequireAuth(): boolean {
  const router = useRouter();
  const [authed, setAuthed] = useState(false);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (getToken()) {
      setAuthed(true);
    } else {
      router.replace("/login");
    }
  }, [router]);

  return authed;
}
