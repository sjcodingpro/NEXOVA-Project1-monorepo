import RequireAuth from "@/components/RequireAuth";

export default function SuppliersLayout({ children }: { children: React.ReactNode }) {
  return <RequireAuth>{children}</RequireAuth>;
}
