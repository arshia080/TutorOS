import { Badge } from "@/components/ui/badge";

export function TrendArrow({ trend }: { trend: string }) {
  if (trend === "IMPROVING") return <Badge variant="default">↑</Badge>;
  if (trend === "DECLINING") return <Badge variant="destructive">↓</Badge>;
  if (trend === "STABLE") return <Badge variant="secondary">→</Badge>;
  return <Badge variant="outline">–</Badge>;
}
