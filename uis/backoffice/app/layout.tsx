import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Nexova Backoffice",
  description: "Internal operations dashboard for Nexova.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-slate-950 text-slate-100 antialiased">
        <div className="min-h-screen flex flex-col">
          <header className="border-b border-slate-800 px-6 py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="font-semibold tracking-tight text-lg">
                  Nexova
                </span>
                <span className="text-xs uppercase tracking-widest text-slate-500">
                  Backoffice
                </span>
              </div>
              <nav className="flex items-center gap-4 text-sm">
                <Link href="/" className="text-slate-300 hover:text-white">
                  Home
                </Link>
                <Link href="/incidents" className="text-slate-300 hover:text-white">
                  Incident Analysis
                </Link>
              </nav>
            </div>
          </header>
          <main className="flex-1">{children}</main>
        </div>
      </body>
    </html>
  );
}
