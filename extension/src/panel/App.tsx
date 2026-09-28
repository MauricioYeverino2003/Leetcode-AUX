import { useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";

import { supabase } from "../lib/supabase";
import { LoginForm } from "./LoginForm";
import { SignedIn } from "./SignedIn";

/**
 * The auth gate. This is what replaces proxy.ts from the Next.js app: there
 * are no requests to intercept in an extension page, so "route protection" is
 * just deciding which component to render.
 *
 * The stored session is trusted for that decision and nothing more. That is
 * sound here in a way it was not on the server: only this extension can write
 * its chrome.storage, whereas request cookies are attacker-controlled input.
 * Actual enforcement stays where it belongs — RLS, and the backend verifying
 * the JWT.
 */
export function App() {
  // undefined = still loading the stored session; null = signed out.
  const [session, setSession] = useState<Session | null | undefined>(undefined);

  useEffect(() => {
    // Every new subscriber is sent INITIAL_SESSION with whatever was persisted
    // in chrome.storage, so this one subscription covers the first load as well
    // as every later sign-in, sign-out and token refresh.
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, next) => setSession(next));

    return () => subscription.unsubscribe();
  }, []);

  if (session === undefined) {
    return <main className="screen screen-center muted">Loading…</main>;
  }

  return session ? <SignedIn session={session} /> : <LoginForm />;
}
