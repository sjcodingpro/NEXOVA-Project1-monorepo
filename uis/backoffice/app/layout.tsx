import type { Metadata } from "next";
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
            <div className="flex items-center gap-3">
              <span className="font-semibold tracking-tight text-lg">
                Nexova
              </span>
              <span className="text-xs uppercase tracking-widest text-slate-500">
                Backoffice
              </span>
            </div>
          </header>
          <main className="flex-1">{children}</main>
        </div>
      </body>
    </html>
  );
}
