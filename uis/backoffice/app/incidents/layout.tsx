import RequireAuth from "@/components/RequireAuth";

export default function IncidentsLayout({ children }: { children: React.ReactNode }) {
  return <RequireAuth>{children}</RequireAuth>;
}
