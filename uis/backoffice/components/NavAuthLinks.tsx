"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";
import { hasValidToken, logout } from "@/lib/auth";

export default function NavAuthLinks() {
  const pathname = usePathname();
  const [loggedIn, setLoggedIn] = useState(false);

  useEffect(() => {
    // Re-checked on every route change so the nav updates right after
    // a login/register redirect or a logout navigation.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoggedIn(hasValidToken());
  }, [pathname]);

  if (loggedIn) {
    return (
      <>
        <Link href="/account/profile" className="text-slate-300 hover:text-white">
          Account
        </Link>
        <button onClick={logout} className="text-slate-300 hover:text-white">
          Log out
        </button>
      </>
    );
  }

  return (
    <Link href="/login" className="text-slate-300 hover:text-white">
      Log in
    </Link>
  );
}
