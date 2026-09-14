"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Settings as SettingsIcon, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/page-header";
import { ErrorBanner } from "@/components/error-banner";
import { getGoogleLinkUrl, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/use-auth";

function LinkStatusBanner() {
  const searchParams = useSearchParams();
  const linked = searchParams.get("google_linked");
  const linkError = searchParams.get("google_link_error");

  if (linked) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-primary/25 bg-primary/5 px-3.5 py-2.5 text-sm text-primary">
        <CheckCircle2 className="size-4 shrink-0" />
        Your Google account is now connected.
      </div>
    );
  }
  if (linkError) return <ErrorBanner message={linkError} />;
  return null;
}

export default function SettingsPage() {
  const { user, loading } = useAuth();
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleConnectGoogle() {
    setError(null);
    setConnecting(true);
    try {
      const { authorization_url } = await getGoogleLinkUrl();
      window.location.href = authorization_url;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to start Google connection");
      setConnecting(false);
    }
  }

  if (loading || !user) {
    return <div className="text-sm text-muted-foreground">Loading...</div>;
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Settings" description="Manage your account." icon={SettingsIcon} />

      <Suspense fallback={null}>
        <LinkStatusBanner />
      </Suspense>

      <Card className="max-w-md border-0 shadow-sm ring-1 ring-border">
        <CardHeader>
          <CardTitle className="text-base">Account</CardTitle>
        </CardHeader>
        <CardContent className="space-y-1 text-sm">
          <p>
            <span className="text-muted-foreground">Name:</span> {user.name}
          </p>
          <p>
            <span className="text-muted-foreground">Email:</span> {user.email}
          </p>
          <p>
            <span className="text-muted-foreground">Role:</span> {user.role}
          </p>
        </CardContent>
      </Card>

      <Card className="max-w-md border-0 shadow-sm ring-1 ring-border">
        <CardHeader>
          <CardTitle className="text-base">Sign-in methods</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {user.google_linked ? (
            <p className="flex items-center gap-2 text-sm text-muted-foreground">
              <CheckCircle2 className="size-4 text-primary" />
              Google account connected -- you can sign in with either your password or Google.
            </p>
          ) : (
            <>
              <p className="text-sm text-muted-foreground">
                Connect your Google account to sign in faster next time.
              </p>
              {error && <ErrorBanner message={error} />}
              <Button variant="outline" onClick={handleConnectGoogle} disabled={connecting} className="w-full">
                {connecting ? "Redirecting..." : "Connect Google account"}
              </Button>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
