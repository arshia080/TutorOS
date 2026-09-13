import { AlertCircle } from "lucide-react";

export function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="flex items-start gap-2.5 rounded-lg border border-destructive/25 bg-destructive/5 px-3.5 py-2.5 text-sm text-destructive">
      <AlertCircle className="mt-0.5 size-4 shrink-0" />
      <span>{message}</span>
    </div>
  );
}
