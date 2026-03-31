"use client";

import { useAuth } from "@clerk/nextjs";
import { useEffect } from "react";

export default function ClerkTokenSync() {
  const { getToken, isSignedIn } = useAuth();

  useEffect(() => {
    if (!isSignedIn) return;

    // Expose getToken on window so the axios interceptor can refresh on 401
    (window as Window & { __clerkGetToken?: () => Promise<string | null> }).__clerkGetToken = getToken;

    async function sync() {
      const token = await getToken();
      if (token) {
        (window as Window & { __clerkToken?: string }).__clerkToken = token;
      }
    }

    sync();
    // Refresh token every 50 seconds (Clerk tokens expire after 60s)
    const id = setInterval(sync, 50_000);
    return () => clearInterval(id);
  }, [isSignedIn, getToken]);

  return null;
}
