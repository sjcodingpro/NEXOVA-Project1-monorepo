import RequireAuth from "@/components/RequireAuth";

export default function ReportingLayout({ children }: { children: React.ReactNode }) {
  return <RequireAuth>{children}</RequireAuth>;
}
