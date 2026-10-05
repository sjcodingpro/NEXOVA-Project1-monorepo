"use client";

import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";
import { track } from "@/lib/telemetry";

const SECTIONS: Record<string, string> = {
  "/": "home",
  "/incidents": "incidents_list",
  "/suppliers": "suppliers_list",
  "/inventory/products": "inventory_dashboard",
  "/inventory/orders": "inventory_orders",
  "/inventory/orders/inbound": "inbound_order_form",
  "/inventory/orders/outbound": "outbound_order_form",
  "/login": "login",
  "/register": "register",
  "/account/profile": "account_profile",
  "/forgot-password": "forgot_password",
  "/reset-password": "reset_password",
};

function sectionFor(pathname: string): string {
  return SECTIONS[pathname] ?? (pathname.replace(/^\/|\/$/g, "").replace(/\//g, "_") || "home");
}

export default function TelemetryProvider() {
  const pathname = usePathname();
  const lastSection = useRef<string | undefined>(undefined);

  useEffect(() => {
    const section = sectionFor(pathname);
    if (lastSection.current === section) return; // also absorbs React strict-mode double effects
    track("backoffice_section_viewed", { section, referrer_section: lastSection.current });
    lastSection.current = section;
  }, [pathname]);

  useEffect(() => {
    const onError = (e: ErrorEvent) =>
      track("frontend_error_raised", {
        error_class: e.error?.name ?? "Error", // class name only, never the message or stack
        source: "window_onerror",
        section: lastSection.current,
      });
    const onRejection = (e: PromiseRejectionEvent) =>
      track("frontend_error_raised", {
        error_class: e.reason instanceof Error ? e.reason.name : "UnhandledRejection",
        source: "unhandledrejection",
        section: lastSection.current,
      });
    window.addEventListener("error", onError);
    window.addEventListener("unhandledrejection", onRejection);
    return () => {
      window.removeEventListener("error", onError);
      window.removeEventListener("unhandledrejection", onRejection);
    };
  }, []);

  return null;
}
