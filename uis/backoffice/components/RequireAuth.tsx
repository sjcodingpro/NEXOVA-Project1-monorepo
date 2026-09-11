"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { hasValidToken } from "@/lib/auth";

/**
 * Wrap any layout that requires a session with this. Checks
 * localStorage for a token (client-side only, since middleware can't
 * read localStorage) and redirects to /login if it's absent or expired.
 */
export default function RequireAuth({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    if (!hasValidToken()) {
      router.replace("/login");
      return;
    }
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setChecked(true);
  }, [router]);

  if (!checked) {
    return (
      <div className="max-w-5xl mx-auto px-6 py-10 text-sm text-slate-400">
        Checking session...
      </div>
    );
  }

  return <>{children}</>;
}
