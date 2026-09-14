"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorBanner } from "@/components/error-banner";
import { completeGoogleSignup, ApiError, type GoogleSignupRole } from "@/lib/api";
import { setToken } from "@/lib/auth";

function ChooseRoleForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const pendingToken = searchParams.get("token");

  const [role, setRole] = useState<GoogleSignupRole>("STUDENT");
  const [phone, setPhone] = useState("");
  const [locality, setLocality] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (!pendingToken) {
    return (
      <Card className="w-full max-w-sm border-0 shadow-sm ring-border">
        <CardContent className="py-6">
          <ErrorBanner message="This sign-up link is missing or invalid. Please start over." />
          <Link href="/register" className="mt-4 block text-sm font-medium text-primary underline-offset-4 hover:underline">
            Back to sign up
          </Link>
        </CardContent>
      </Card>
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const result = await completeGoogleSignup(
        pendingToken!,
        role,
        role === "PARENT" ? { phone: phone || undefined, locality: locality || undefined } : {},
      );
      setToken(result.access_token);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card className="w-full max-w-sm border-0 shadow-sm ring-border">
      <CardHeader>
        <CardTitle className="text-xl">Almost there</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="mb-4 text-sm text-muted-foreground">
          One last step -- tell us who you are so we can set up the right dashboard.
        </p>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="role">I am a</Label>
            <select
              id="role"
              className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm"
              value={role}
              onChange={(e) => setRole(e.target.value as GoogleSignupRole)}
            >
              <option value="STUDENT">Student</option>
              <option value="TEACHER">Teacher</option>
              <option value="PARENT">Parent</option>
            </select>
          </div>
          {role === "PARENT" && (
            <>
              <div className="space-y-2">
                <Label htmlFor="phone">Phone (optional)</Label>
                <Input id="phone" value={phone} onChange={(e) => setPhone(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="locality">Locality (optional)</Label>
                <Input id="locality" value={locality} onChange={(e) => setLocality(e.target.value)} />
              </div>
            </>
          )}
          {error && <ErrorBanner message={error} />}
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? "Setting up your account..." : "Continue"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

export default function ChooseRolePage() {
  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <Suspense fallback={null}>
        <ChooseRoleForm />
      </Suspense>
    </div>
  );
}
