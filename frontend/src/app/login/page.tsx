"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { GoogleSignInButton } from "@/components/google-signin-button";
import { login, ApiError } from "@/lib/api";
import { setToken } from "@/lib/auth";

const GOOGLE_ERROR_MESSAGES: Record<string, string> = {
  google_not_configured: "Google sign-in isn't set up on this server yet.",
  google_denied: "Google sign-in was cancelled.",
  invalid_request: "That sign-in link was incomplete. Please try again.",
  invalid_state: "That sign-in link expired or was invalid. Please try again.",
  google_exchange_failed: "Couldn't complete Google sign-in. Please try again.",
  google_verification_failed: "Couldn't verify your Google account. Please try again.",
  invalid_google_token: "Couldn't verify your Google account. Please try again.",
  email_not_verified: "Your Google account's email isn't verified, so we can't sign you in with it.",
  google_account_exists_local:
    "An account already exists with this email. Sign in with your password, then connect Google from Settings.",
};

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(
    () => {
      const code = searchParams.get("error");
      return code ? (GOOGLE_ERROR_MESSAGES[code] ?? "Something went wrong signing you in.") : null;
    },
  );
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const result = await login(email, password);
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
        <CardTitle className="text-xl">Log in to TutorOS</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <GoogleSignInButton />
          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            <div className="h-px flex-1 bg-border" />
            or
            <div className="h-px flex-1 bg-border" />
          </div>
        </div>
        <form onSubmit={handleSubmit} className="mt-4 space-y-4">
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? "Logging in..." : "Log in"}
          </Button>
        </form>
        <p className="mt-4 text-sm text-muted-foreground">
          No account?{" "}
          <Link href="/register" className="font-medium text-primary underline-offset-4 hover:underline">
            Register
          </Link>
        </p>
      </CardContent>
    </Card>
  );
}

export default function LoginPage() {
  return (
    <div className="flex min-h-screen">
      <div className="relative hidden w-1/2 flex-col justify-between bg-primary p-10 text-primary-foreground lg:flex">
        <div
          className="pointer-events-none absolute inset-0 opacity-40"
          style={{
            background:
              "radial-gradient(circle at 20% 20%, color-mix(in oklch, var(--accent), transparent 40%), transparent 55%), radial-gradient(circle at 90% 90%, color-mix(in oklch, var(--sidebar-primary), transparent 55%), transparent 50%)",
          }}
        />
        <Link href="/" className="relative text-lg font-semibold tracking-tight">
          Tutor<span className="text-primary-foreground/70">OS</span>
        </Link>
        <div className="relative max-w-md">
          <h2 className="text-3xl font-semibold tracking-tight">
            Welcome back to your classroom, online.
          </h2>
          <p className="mt-4 text-primary-foreground/80">
            Pick up right where you left off — assessments, mastery tracking, and
            personalized practice, all in one place.
          </p>
        </div>
        <p className="relative text-sm text-primary-foreground/60">
          © {new Date().getFullYear()} TutorOS
        </p>
      </div>

      <div className="flex flex-1 items-center justify-center p-6">
        <Suspense fallback={null}>
          <LoginForm />
        </Suspense>
      </div>
    </div>
  );
}
