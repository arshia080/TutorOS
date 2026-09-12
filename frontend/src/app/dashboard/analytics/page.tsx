"use client";

import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { TrendArrow } from "@/components/trend-arrow";
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
    <div>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Analytics</h1>
        {batches.length > 0 && (
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
        )}
      </div>

      {batches.length === 0 && <p className="mt-6 text-sm text-muted-foreground">Create a batch first.</p>}
      {error && <p className="mt-6 text-sm text-red-600">{error}</p>}

      {batchId && !error && (
        <>
          <div className="mt-6 grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Class Performance</CardTitle>
              </CardHeader>
              <CardContent>
                {classPerf === null ? (
                  <Skeleton className="h-64 w-full" />
                ) : (
                  <ResponsiveContainer width="100%" height={260}>
                    <BarChart data={summaryData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="name" />
                      <YAxis domain={[0, 100]} />
                      <Tooltip />
                      <Bar dataKey="value" fill="#2563eb" radius={[4, 4, 0, 0]} />
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

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Topic Mastery (class average)</CardTitle>
              </CardHeader>
              <CardContent>
                {classPerf === null ? (
                  <Skeleton className="h-64 w-full" />
                ) : classPerf.topics.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No topic performance data yet.</p>
                ) : (
                  <ResponsiveContainer width="100%" height={260}>
                    <BarChart data={classPerf.topics.map((t) => ({ name: t.topic_name, mastery: t.average_mastery }))}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="name" />
                      <YAxis domain={[0, 100]} />
                      <Tooltip />
                      <Legend />
                      <Bar dataKey="mastery" fill="#16a34a" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </CardContent>
            </Card>
          </div>

          <h2 className="mt-8 text-lg font-medium">Attention Panel</h2>
          <p className="text-sm text-muted-foreground">Each student's weakest topic right now.</p>
          <div className="mt-2">
            {attention === null && <Skeleton className="h-10 w-full" />}
            {attention !== null && attention.length === 0 && (
              <p className="text-sm text-muted-foreground">No graded test results in this batch yet.</p>
            )}
            {attention !== null && attention.length > 0 && (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Student</TableHead>
                    <TableHead>Topic</TableHead>
                    <TableHead>Mastery</TableHead>
                    <TableHead>Trend</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {attention.map((row) => (
                    <TableRow key={row.student_id}>
                      <TableCell>{row.student_name}</TableCell>
                      <TableCell>{row.topic_name}</TableCell>
                      <TableCell>{row.mastery_score}%</TableCell>
                      <TableCell>
                        <TrendArrow trend={row.trend} />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </div>
        </>
      )}
    </div>
  );
}
