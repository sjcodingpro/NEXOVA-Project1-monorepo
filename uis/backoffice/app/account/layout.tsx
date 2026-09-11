import RequireAuth from "@/components/RequireAuth";

export default function AccountLayout({ children }: { children: React.ReactNode }) {
  return <RequireAuth>{children}</RequireAuth>;
}
