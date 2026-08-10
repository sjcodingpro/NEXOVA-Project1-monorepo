export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return <div className="text-center text-sm text-gray-500 py-12">{label}</div>;
}
