"use client";

import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { BarChart3, LayoutGrid, AlertTriangle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { TrendArrow } from "@/components/trend-arrow";
import { PageHeader } from "@/components/page-header";
import { ErrorBanner } from "@/components/error-banner";
import { EmptyState } from "@/components/empty-state";
import {
  listBatches,
  getAttentionPanel,
  getClassPerformance,
  type Batch,
  type AttentionPanelEntry,
  type ClassPerformance,
  ApiError,
} from "@/lib/api";

export default function AnalyticsPage() {
  const [batches, setBatches] = useState<Batch[]>([]);
  const [batchId, setBatchId] = useState<string | null>(null);
  const [attention, setAttention] = useState<AttentionPanelEntry[] | null>(null);
  const [classPerf, setClassPerf] = useState<ClassPerformance | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listBatches()
      .then((data) => {
        setBatches(data);
        if (data.length > 0) setBatchId(data[0].id);
      })
      .catch(() => setBatches([]));
  }, []);

  useEffect(() => {
    if (!batchId) return;
    setAttention(null);
    setClassPerf(null);
    setError(null);
    Promise.all([getAttentionPanel(batchId), getClassPerformance(batchId)])
      .then(([a, c]) => {
        setAttention(a);
        setClassPerf(c);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load analytics"));
  }, [batchId]);

  const summaryData = classPerf
    ? [
        { name: "Avg Score", value: classPerf.average_score ?? 0 },
        { name: "Avg Attendance", value: classPerf.average_attendance_percentage ?? 0 },
        { name: "Avg Mastery", value: classPerf.average_mastery },
      ]
    : [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Analytics"
        description="Class performance and where students need help."
        icon={BarChart3}
        action={
          batches.length > 0 && (
            <Select value={batchId ?? undefined} onValueChange={(v: string | null) => v && setBatchId(v)}>
              <SelectTrigger className="w-56">
                <SelectValue placeholder="Select batch" />
              </SelectTrigger>
              <SelectContent>
                {batches.map((b) => (
                  <SelectItem key={b.id} value={b.id}>
                    {b.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )
        }
      />

      {batches.length === 0 && (
        <EmptyState
          icon={LayoutGrid}
          title="Create a batch first"
          description="Analytics appear once you have a batch with graded results."
        />
      )}
      {error && <ErrorBanner message={error} />}

      {batchId && !error && (
        <>
          <div className="grid gap-5 lg:grid-cols-2">
            <Card className="border-0 shadow-sm ring-1 ring-border">
              <CardHeader>
                <CardTitle className="text-base">Class performance</CardTitle>
              </CardHeader>
              <CardContent>
                {classPerf === null ? (
                  <Skeleton className="h-64 w-full" />
                ) : (
                  <ResponsiveContainer width="100%" height={260}>
                    <BarChart data={summaryData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                      <XAxis dataKey="name" stroke="var(--muted-foreground)" fontSize={12} />
                      <YAxis domain={[0, 100]} stroke="var(--muted-foreground)" fontSize={12} />
                      <Tooltip
                        contentStyle={{
                          background: "var(--popover)",
                          border: "1px solid var(--border)",
                          borderRadius: "0.5rem",
                          fontSize: "0.8rem",
                        }}
                      />
                      <Bar dataKey="value" fill="var(--chart-1)" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                )}
                {classPerf && (
                  <p className="mt-2 text-xs text-muted-foreground">
                    Score distribution: median {classPerf.median_score ?? "—"}%, high {classPerf.high_score ?? "—"}%,
                    low {classPerf.low_score ?? "—"}%. Attendance/performance shown together for context only --
                    this is not a claim that attendance causes performance.
                  </p>
                )}
              </CardContent>
            </Card>

            <Card className="border-0 shadow-sm ring-1 ring-border">
              <CardHeader>
                <CardTitle className="text-base">Topic mastery (class average)</CardTitle>
              </CardHeader>
              <CardContent>
                {classPerf === null ? (
                  <Skeleton className="h-64 w-full" />
                ) : classPerf.topics.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No topic performance data yet.</p>
                ) : (
                  <ResponsiveContainer width="100%" height={260}>
                    <BarChart data={classPerf.topics.map((t) => ({ name: t.topic_name, mastery: t.average_mastery }))}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                      <XAxis dataKey="name" stroke="var(--muted-foreground)" fontSize={12} />
                      <YAxis domain={[0, 100]} stroke="var(--muted-foreground)" fontSize={12} />
                      <Tooltip
                        contentStyle={{
                          background: "var(--popover)",
                          border: "1px solid var(--border)",
                          borderRadius: "0.5rem",
                          fontSize: "0.8rem",
                        }}
                      />
                      <Legend wrapperStyle={{ fontSize: "0.8rem" }} />
                      <Bar dataKey="mastery" fill="var(--chart-2)" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </CardContent>
            </Card>
          </div>

          <div>
            <div className="mb-1 flex items-center gap-2">
              <AlertTriangle className="size-4 text-primary" />
              <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Attention panel</h2>
            </div>
            <p className="mb-3 text-sm text-muted-foreground">Each student&apos;s weakest topic right now.</p>

            {attention === null && <Skeleton className="h-10 w-full" />}
            {attention !== null && attention.length === 0 && (
              <EmptyState title="No graded test results in this batch yet" />
            )}
            {attention !== null && attention.length > 0 && (
              <div className="overflow-hidden rounded-lg border border-border">
                <Table>
                  <TableHeader>
                    <TableRow className="hover:bg-transparent">
                      <TableHead>Student</TableHead>
                      <TableHead>Topic</TableHead>
                      <TableHead>Mastery</TableHead>
                      <TableHead>Trend</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {attention.map((row) => (
                      <TableRow key={row.student_id}>
                        <TableCell className="font-medium">{row.student_name}</TableCell>
                        <TableCell className="text-muted-foreground">{row.topic_name}</TableCell>
                        <TableCell className="font-medium text-destructive">{row.mastery_score}%</TableCell>
                        <TableCell>
                          <TrendArrow trend={row.trend} />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
