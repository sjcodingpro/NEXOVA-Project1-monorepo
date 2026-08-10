export function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="border border-red-200 bg-red-50 text-red-700 text-sm rounded-md px-4 py-3 flex items-center justify-between gap-4">
      <span>{message}</span>
      {onRetry && (
        <button onClick={onRetry} className="underline font-medium shrink-0">
          Retry
        </button>
      )}
    </div>
  );
}
