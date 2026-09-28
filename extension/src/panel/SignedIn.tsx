import { useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";

import { CAPTURE_KEY, type Capture } from "../lib/capture";
import { CODE_KEY, type CodeCapture } from "../lib/code";
import { supabase } from "../lib/supabase";
import { Chat } from "./Chat";

/** A value in chrome.storage.local, kept live: the content script writes
 *  whenever something changes on the page, and onChanged delivers it here. */
function useStored<T>(key: string): T | null {
  const [value, setValue] = useState<T | null>(null);

  useEffect(() => {
    let cancelled = false;

    chrome.storage.local.get(key).then((result) => {
      if (!cancelled) setValue((result[key] as T | undefined) ?? null);
    });

    const onChanged = (changes: { [key: string]: chrome.storage.StorageChange }, area: string) => {
      if (area === "local" && changes[key]) {
        setValue((changes[key].newValue as T | undefined) ?? null);
      }
    };

    chrome.storage.onChanged.addListener(onChanged);

    return () => {
      cancelled = true;
      chrome.storage.onChanged.removeListener(onChanged);
    };
  }, [key]);

  return value;
}

export function SignedIn({ session }: { session: Session }) {
  const capture = useStored<Capture>(CAPTURE_KEY);
  const code = useStored<CodeCapture>(CODE_KEY);
  const [signingOut, setSigningOut] = useState(false);

  async function handleSignOut() {
    setSigningOut(true);

    // "local" ends this extension's session only. The default, "global", would
    // also revoke the same user's sessions everywhere else — signing out of
    // the extension should not log them out of the web app.
    const { error } = await supabase.auth.signOut({ scope: "local" });

    // On success App.tsx unmounts this component; only a failure lands here.
    if (error) {
      console.error("[LC-AUX] sign out failed", error);
      setSigningOut(false);
    }
  }

  return (
    <main className="screen screen-fill">
      <header className="header">
        <div>
          <h1 className="title title-sm">LeetCode AUX</h1>
          <p className="muted small">{session.user.email}</p>
        </div>
        <button type="button" onClick={handleSignOut} disabled={signingOut} className="btn btn-secondary btn-sm">
          {signingOut ? "Signing out…" : "Sign out"}
        </button>
      </header>

      <section className="context">
        {capture ? (
          <ProblemLine capture={capture} />
        ) : (
          <p className="muted small">Open a LeetCode problem to get started.</p>
        )}
        <CodeLine code={code} problemSlug={capture?.slug ?? null} />
      </section>

      <Chat capture={capture} code={code} />
    </main>
  );
}

function ProblemLine({ capture }: { capture: Capture }) {
  const g = capture.graphql;
  const title = g ? `${g.number}. ${g.title}` : (capture.dom.title ?? capture.slug);

  return (
    <div className="row">
      <span className="strong">{title}</span>
      {g ? <span className={`difficulty difficulty-${g.difficulty.toLowerCase()}`}>{g.difficulty}</span> : null}
    </div>
  );
}

/** What the agent will see of the editor, in one line. */
function CodeLine({ code, problemSlug }: { code: CodeCapture | null; problemSlug: string | null }) {
  if (!code || code.slug !== problemSlug) {
    return <p className="muted small">No code read yet.</p>;
  }

  if (code.status === "unavailable") {
    return <p className="notice notice-warn small">Couldn't read the editor — hints will go without your code.</p>;
  }

  const lines = code.code.length > 0 ? code.code.split("\n").length : 0;
  return (
    <p className="muted small">
      {code.language ?? "code"} · {lines} {lines === 1 ? "line" : "lines"} · sent with each message
    </p>
  );
}
