import { useState, type FormEvent } from "react";

import { supabase } from "../lib/supabase";

type Notice = { kind: "error" | "info"; text: string };

/**
 * Ported from the login page of the original Next.js app (since deleted). Same
 * form, same two-buttons-one-form design — but the server action is gone, so
 * the submit handler calls
 * Supabase directly. There is no redirect on success either: the auth listener
 * in App.tsx sees the new session and swaps this component out.
 */
export function LoginForm() {
  const [pending, setPending] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    // Which button submitted the form decides sign-in vs sign-up.
    const submitter = (event.nativeEvent as SubmitEvent).submitter as HTMLButtonElement | null;
    const intent = submitter?.value === "signup" ? "signup" : "signin";

    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") ?? "").trim();
    const password = String(form.get("password") ?? "");

    if (!email || !password) {
      setNotice({ kind: "error", text: "Email and password are both required." });
      return;
    }

    setPending(true);
    setNotice(null);

    try {
      if (intent === "signup") {
        const { data, error } = await supabase.auth.signUp({ email, password });

        if (error) {
          setNotice({ kind: "error", text: describe(error) });
        } else if (!data.session) {
          // No session means the project requires email confirmation. Locally
          // that is off, so this only fires against a real Supabase project.
          setNotice({ kind: "info", text: `Check ${email} for a confirmation link.` });
        }
      } else {
        const { error } = await supabase.auth.signInWithPassword({ email, password });

        if (error) {
          setNotice({ kind: "error", text: describe(error) });
        }
      }
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="screen screen-center">
      <div className="login">
        <h1 className="title">LeetCode AUX</h1>
        <p className="muted">Sign in to start a practice session.</p>

        <form onSubmit={handleSubmit} className="form">
          <label className="field">
            <span className="label">Email</span>
            <input type="email" name="email" autoComplete="email" required className="input" />
          </label>

          <label className="field">
            <span className="label">Password</span>
            <input
              type="password"
              name="password"
              autoComplete="current-password"
              required
              minLength={6}
              className="input"
            />
          </label>

          {notice ? (
            <p
              role={notice.kind === "error" ? "alert" : "status"}
              className={notice.kind === "error" ? "notice notice-error" : "notice notice-info"}
            >
              {notice.text}
            </p>
          ) : null}

          <div className="actions">
            <button type="submit" name="intent" value="signin" disabled={pending} className="btn btn-primary">
              {pending ? "Working…" : "Log in"}
            </button>
            <button type="submit" name="intent" value="signup" disabled={pending} className="btn btn-secondary">
              Sign up
            </button>
          </div>
        </form>
      </div>
    </main>
  );
}

/** Supabase reports an unreachable server as a bare "Failed to fetch", which
 *  tells a developer nothing. Everything else is already readable. */
function describe(error: { name: string; message: string }): string {
  if (error.name === "AuthRetryableFetchError") {
    return "Can't reach the auth server. Is Supabase running?";
  }
  return error.message;
}
