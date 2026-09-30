import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";

import { sendChat, type ChatRequest, type ChatTurn } from "../lib/backend";
import type { Capture } from "../lib/capture";
import type { CodeCapture } from "../lib/code";
import { Notice } from "./Notice";

/**
 * The conversation. Held in component state only — nothing is persisted yet,
 * so closing the panel ends the chat. Switching problems starts a fresh one,
 * since a transcript about Two Sum is noise for Number of Islands.
 */
export function Chat({ capture, code }: { capture: Capture | null; code: CodeCapture | null }) {
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottom = useRef<HTMLDivElement>(null);

  const slug = capture?.slug ?? null;

  useEffect(() => {
    setTurns([]);
    setError(null);
  }, [slug]);

  useEffect(() => {
    bottom.current?.scrollIntoView({ block: "end" });
  }, [turns, pending]);

  async function send() {
    const text = draft.trim();
    if (!text || pending) return;

    const next: ChatTurn[] = [...turns, { role: "user", content: text }];
    setTurns(next);
    setDraft("");
    setPending(true);
    setError(null);

    try {
      const response = await sendChat({
        messages: next,
        problem: problemContext(capture),
        code: codeContext(code, slug),
      });
      setTurns([...next, { role: "assistant", content: response.reply }]);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      // Put the message back where it was so a retry is one keypress away.
      setTurns(turns);
      setDraft(text);
    } finally {
      setPending(false);
    }
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void send();
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void send();
    }
  }

  return (
    <section className="chat">
      <div className="turns">
        {turns.length === 0 && !pending ? (
          <>
            <p className="muted small">Ask for a hint. It won't give you the answer.</p>
            {/* The data-sharing notice sits here until the first message: the
                one place the user is guaranteed to look before sending. */}
            <Notice />
          </>
        ) : null}

        {turns.map((turn, i) => (
          <div key={i} className={`turn turn-${turn.role}`}>
            {turn.content}
          </div>
        ))}

        {pending ? <div className="turn turn-assistant muted">Thinking…</div> : null}

        {error ? (
          <p role="alert" className="notice notice-error small">
            {error}
          </p>
        ) : null}

        <div ref={bottom} />
      </div>

      <form className="composer" onSubmit={onSubmit}>
        <textarea
          className="input composer-input"
          rows={2}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder={slug ? "Ask for a hint…" : "Open a LeetCode problem first"}
          disabled={pending}
        />
        <button type="submit" className="btn btn-primary btn-sm" disabled={pending || draft.trim().length === 0}>
          Send
        </button>
      </form>
    </section>
  );
}

function problemContext(capture: Capture | null): ChatRequest["problem"] {
  if (!capture) return undefined;

  if (capture.graphql) {
    const g = capture.graphql;
    return {
      slug: capture.slug,
      title: `${g.number}. ${g.title}`,
      difficulty: g.difficulty,
      statement: g.statement,
    };
  }

  return {
    slug: capture.slug,
    title: capture.dom.title,
    difficulty: null,
    statement: capture.dom.statement,
  };
}

/** Only send code that was read from the problem currently on screen. */
function codeContext(code: CodeCapture | null, slug: string | null): ChatRequest["code"] {
  if (!code || code.status !== "ok" || code.slug !== slug || code.code.trim().length === 0) {
    return undefined;
  }
  return { language: code.language, code: code.code };
}
