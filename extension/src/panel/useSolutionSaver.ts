import { useEffect, useRef, useState } from "react";

import { BackendError, embedMissing, saveSolution } from "../lib/backend";
import type { Capture } from "../lib/capture";
import { ACCEPTED_PREFIX, SOLUTION_KEY, type AcceptedSubmission, type SavedSolution } from "../lib/submission";

/** `remaining` counts the accepted submissions still queued, including the
 *  one being saved — an import can queue dozens at once. */
export type SaveState =
  | { status: "idle"; remaining: 0 }
  | { status: "saving"; slug: string; remaining: number }
  | { status: "error"; slug: string; message: string; remaining: number };

/** A request the backend refused on its merits will be refused again, so that
 *  submission is dropped rather than retried every time the panel opens. */
function isPermanent(err: unknown): boolean {
  return err instanceof BackendError && (err.status === 400 || err.status === 422);
}

/**
 * Saves accepted submissions.
 *
 * content.ts leaves each one in chrome.storage.local under `accepted:<id>`;
 * this sends it to the backend, then removes it and records the outcome. It
 * lives in the panel because the panel holds the session — so a submission
 * accepted while the panel is closed waits in storage until it next opens.
 *
 * A save that fails stays in storage and is tried again the next time the
 * panel opens or another submission arrives. There is no retry loop.
 */
export function useSolutionSaver(capture: Capture | null): SaveState {
  const [state, setState] = useState<SaveState>({ status: "idle", remaining: 0 });

  // The saver runs outside the render cycle, so it reads the current problem
  // through a ref rather than restarting whenever the capture changes.
  const captureRef = useRef(capture);
  useEffect(() => {
    captureRef.current = capture;
  }, [capture]);

  useEffect(() => {
    let running = false;
    let again = false;

    async function saveOne(key: string, accepted: AcceptedSubmission, remaining: number): Promise<void> {
      setState({ status: "saving", slug: accepted.slug, remaining });

      // The statement makes for a better summary, and the panel has it when
      // the submission is for the problem currently open.
      const current = captureRef.current;
      const statement =
        current?.slug === accepted.slug ? (current.graphql?.statement ?? current.dom.statement) : null;

      try {
        const result = await saveSolution({
          submission_id: Number(accepted.submissionId),
          problem: {
            slug: accepted.slug,
            title: accepted.title,
            difficulty: accepted.difficulty,
            statement,
          },
          problem_number: accepted.number,
          topic_tags: accepted.topicTags,
          language: accepted.language,
          code: accepted.code,
          submitted_at: accepted.submittedAt ?? accepted.detectedAt,
        });

        const saved: SavedSolution = {
          submissionId: accepted.submissionId,
          slug: accepted.slug,
          summary: result.summary,
          alreadySaved: result.already_saved,
          savedAt: new Date().toISOString(),
        };
        await chrome.storage.local.set({ [SOLUTION_KEY]: saved });
        await chrome.storage.local.remove(key);

        setState(remaining > 1 ? { status: "saving", slug: accepted.slug, remaining: remaining - 1 } : { status: "idle", remaining: 0 });
      } catch (err) {
        if (isPermanent(err)) await chrome.storage.local.remove(key);

        setState({
          status: "error",
          slug: accepted.slug,
          message: err instanceof Error ? err.message : String(err),
          remaining: remaining - 1,
        });
      }
    }

    /** Indexes for recall whatever is saved but not yet embedded — the rows
     *  an import just added, or everything the first time this runs. Silent
     *  on failure: recall falls back to tags, and the next pass retries. */
    async function indexMissing(): Promise<void> {
      try {
        for (let batches = 0; batches < 100; batches++) {
          const { embedded, remaining } = await embedMissing();
          if (embedded > 0) console.log(`[LC-AUX] indexed ${embedded} solutions for recall, ${remaining} to go`);
          if (remaining === 0 || embedded === 0) return;
        }
      } catch (err) {
        console.warn("[LC-AUX] indexing for recall failed", err);
      }
    }

    /** Saves everything waiting, one at a time. If another submission arrives
     *  meanwhile, goes round once more instead of starting a second pass. */
    async function drain(): Promise<void> {
      if (running) {
        again = true;
        return;
      }

      running = true;
      try {
        do {
          again = false;
          const all = await chrome.storage.local.get(null);
          const queued = Object.entries(all).filter(([key]) => key.startsWith(ACCEPTED_PREFIX));
          for (const [i, [key, value]] of queued.entries()) {
            await saveOne(key, value as AcceptedSubmission, queued.length - i);
          }
        } while (again);

        await indexMissing();
      } finally {
        running = false;
      }
    }

    const onChanged = (changes: { [key: string]: chrome.storage.StorageChange }, area: string) => {
      if (area !== "local") return;

      // Only additions: removing a key after saving it must not start a pass.
      const added = Object.entries(changes).some(
        ([key, change]) => key.startsWith(ACCEPTED_PREFIX) && change.newValue !== undefined,
      );
      if (added) void drain();
    };

    chrome.storage.onChanged.addListener(onChanged);
    void drain();

    return () => chrome.storage.onChanged.removeListener(onChanged);
  }, []);

  return state;
}
