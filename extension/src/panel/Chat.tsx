import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";

import { sendChat, type ChatRequest, type ChatResult, type ChatTurn } from "../lib/backend";
import type { Capture } from "../lib/capture";
import type { CodeCapture } from "../lib/code";
import { Notice } from "./Notice";

/** What one reply cost, shown under it. Kept on the turn, never sent back. */
type TurnMeta = {
  model: string;
  modelMs: number;
  roundTripMs: number;
  inputTokens: number;
  outputTokens: number;
  reasoningTokens: number;
  cachedTokens: number;
  costUsd: number | null;
  /** Titles of the saved solutions the tutor was shown. */
  recalled: string[];
};

type Turn = ChatTurn & { meta?: TurnMeta };

/**
 * The conversation. Held in component state only — nothing is persisted yet,
 * so closing the panel ends the chat. Switching problems starts a fresh one,
 * since a transcript about Two Sum is noise for Number of Islands.
 */
export function Chat({ capture, code }: { capture: Capture | null; code: CodeCapture | null }) {
  const [turns, setTurns] = useState<Turn[]>([]);
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

    const next: Turn[] = [...turns, { role: "user", content: text }];
    setTurns(next);
    setDraft("");
    setPending(true);
    setError(null);

    try {
      const result = await sendChat({
        // Only role and content go over the wire; the metrics stay local.
        messages: next.map(({ role, content }) => ({ role, content })),
        problem: problemContext(capture),
        code: codeContext(code, slug),
      });
      setTurns([...next, { role: "assistant", content: result.reply, meta: metaFrom(result) }]);
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
          <div key={i} className={`turn-group turn-group-${turn.role}`}>
            <div className={`turn turn-${turn.role}`}>{turn.content}</div>
            {turn.meta ? <div className="turn-meta">{formatMeta(turn.meta)}</div> : null}
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

function metaFrom(result: ChatResult): TurnMeta {
  return {
    model: result.model,
    modelMs: result.timing.model_ms,
    roundTripMs: result.round_trip_ms,
    inputTokens: result.usage.input_tokens,
    outputTokens: result.usage.output_tokens,
    reasoningTokens: result.usage.reasoning_tokens,
    cachedTokens: result.usage.cache_read_input_tokens,
    costUsd: result.cost_usd,
    recalled: result.prior_solutions.map(
      (s) => (s.title ?? s.slug) + (s.similarity !== null ? ` ${s.similarity.toFixed(2)}` : ""),
    ),
  };
}

/** e.g. "gpt-5 · 2.1s model / 2.4s total · 3.2k in / 640 out (410 reasoning) · 2.9k cached · ~$0.021 · recalled: Two Sum 0.71" */
function formatMeta(m: TurnMeta): string {
  const secs = (ms: number) => `${(ms / 1000).toFixed(1)}s`;
  const k = (n: number) => (n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n));

  const parts = [
    m.model,
    `${secs(m.modelMs)} model / ${secs(m.roundTripMs)} total`,
    `${k(m.inputTokens)} in / ${k(m.outputTokens)} out` +
      (m.reasoningTokens > 0 ? ` (${k(m.reasoningTokens)} reasoning)` : ""),
  ];
  if (m.cachedTokens > 0) parts.push(`${k(m.cachedTokens)} cached`);
  if (m.costUsd !== null) parts.push(`~$${m.costUsd < 0.01 ? m.costUsd.toFixed(4) : m.costUsd.toFixed(3)}`);
  if (m.recalled.length > 0) parts.push(`recalled: ${m.recalled.join(", ")}`);
  return parts.join(" · ");
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
      topic_tags: g.topicTags,
    };
  }

  return {
    slug: capture.slug,
    title: capture.dom.title,
    difficulty: null,
    statement: capture.dom.statement,
    // The DOM path has no tags, so nothing is recalled on it.
    topic_tags: [],
  };
}

/** Only send code that was read from the problem currently on screen. */
function codeContext(code: CodeCapture | null, slug: string | null): ChatRequest["code"] {
  if (!code || code.status !== "ok" || code.slug !== slug || code.code.trim().length === 0) {
    return undefined;
  }
  return { language: code.language, code: code.code };
}
