"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { setToken } from "@/lib/auth";

export default function GoogleCompletePage() {
  const router = useRouter();
  const [error, setError] = useState(false);

  useEffect(() => {
    // The token lives in the URL fragment (never sent to any server, unlike
    // a query param) -- window.location.hash is the only way to read it.
    const hash = window.location.hash.startsWith("#") ? window.location.hash.slice(1) : window.location.hash;
    const params = new URLSearchParams(hash);
    const token = params.get("token");

    if (!token) {
      setError(true);
      return;
    }

    setToken(token);
    router.replace("/dashboard");
  }, [router]);

  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <p className="text-sm text-muted-foreground">
        {error ? "Something went wrong signing you in. Please try again." : "Signing you in..."}
      </p>
    </div>
  );
}
