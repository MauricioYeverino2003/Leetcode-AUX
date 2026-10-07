import { useState } from "react";
import type { Session } from "@supabase/supabase-js";

import { CAPTURE_KEY, type Capture } from "../lib/capture";
import { CODE_KEY, type CodeCapture } from "../lib/code";
import { SOLUTION_KEY, type SavedSolution } from "../lib/submission";
import { supabase } from "../lib/supabase";
import { Chat } from "./Chat";
import { ImportPanel } from "./ImportPanel";
import { Notice } from "./Notice";
import { type SaveState, useSolutionSaver } from "./useSolutionSaver";
import { useStored } from "./useStored";

export function SignedIn({ session }: { session: Session }) {
  const capture = useStored<Capture>(CAPTURE_KEY);
  const code = useStored<CodeCapture>(CODE_KEY);
  const solution = useStored<SavedSolution>(SOLUTION_KEY);
  const saver = useSolutionSaver(capture);
  const [signingOut, setSigningOut] = useState(false);
  const [showPrivacy, setShowPrivacy] = useState(false);

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
        <div className="header-actions">
          <button
            type="button"
            onClick={() => setShowPrivacy((open) => !open)}
            aria-expanded={showPrivacy}
            className="btn btn-secondary btn-sm"
          >
            Privacy
          </button>
          <button type="button" onClick={handleSignOut} disabled={signingOut} className="btn btn-secondary btn-sm">
            {signingOut ? "Signing out…" : "Sign out"}
          </button>
        </div>
      </header>

      <section className="context">
        {capture ? (
          <ProblemLine capture={capture} />
        ) : (
          <p className="muted small">Open a LeetCode problem to get started.</p>
        )}
        <CodeLine code={code} problemSlug={capture?.slug ?? null} />
        <SolutionLine saver={saver} solution={solution} problemSlug={capture?.slug ?? null} />
      </section>

      <ImportPanel saving={saver.remaining} />

      {showPrivacy ? (
        <section className="privacy">
          <Notice title="What gets sent, and to whom" />
          <button type="button" onClick={() => setShowPrivacy(false)} className="btn btn-secondary btn-sm">
            Close
          </button>
        </section>
      ) : null}

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

/** Whether an accepted solution is being saved, and — for the problem that is
 *  open — the summary stored with the last one. */
function SolutionLine({
  saver,
  solution,
  problemSlug,
}: {
  saver: SaveState;
  solution: SavedSolution | null;
  problemSlug: string | null;
}) {
  if (saver.status === "saving") {
    return (
      <p className="muted small">
        {saver.remaining > 1 ? `Saving ${saver.remaining} accepted solutions…` : "Accepted — saving your solution…"}
      </p>
    );
  }

  if (saver.status === "error") {
    return <p className="notice notice-warn small">Couldn't save your accepted solution: {saver.message}</p>;
  }

  if (!solution || solution.slug !== problemSlug) return null;

  return (
    <div className="solution">
      <p className="notice notice-info small">
        {solution.alreadySaved ? "Accepted solution already saved" : "Accepted solution saved"}
      </p>
      <p className="muted small">{solution.summary}</p>
    </div>
  );
}
