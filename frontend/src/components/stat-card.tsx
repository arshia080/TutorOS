import type { ReactNode } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export function StatCard({
  label,
  value,
  icon: Icon,
  tone = "default",
}: {
  label: string;
  value: ReactNode | null;
  icon?: React.ComponentType<{ className?: string }>;
  tone?: "default" | "destructive";
}) {
  return (
    <Card className="border-0 shadow-sm ring-1 ring-border">
      <CardContent className="flex items-center justify-between gap-4 py-1">
        <div>
          <p className="text-xs font-medium text-muted-foreground">{label}</p>
          {value === null ? (
            <Skeleton className="mt-1.5 h-8 w-14" />
          ) : (
            <p
              className={`mt-1 text-2xl font-semibold tracking-tight ${
                tone === "destructive" ? "text-destructive" : "text-foreground"
              }`}
            >
              {value}
            </p>
          )}
        </div>
        {Icon && (
          <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-secondary text-secondary-foreground">
            <Icon className="size-4.5" />
          </div>
        )}
      </CardContent>
    </Card>
  );
}
