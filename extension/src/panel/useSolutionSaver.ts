import { useEffect, useRef, useState } from "react";

import { BackendError, saveSolution } from "../lib/backend";
import type { Capture } from "../lib/capture";
import { ACCEPTED_PREFIX, SOLUTION_KEY, type AcceptedSubmission, type SavedSolution } from "../lib/submission";

export type SaveState =
  | { status: "idle" }
  | { status: "saving"; slug: string }
  | { status: "error"; slug: string; message: string };

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
  const [state, setState] = useState<SaveState>({ status: "idle" });

  // The saver runs outside the render cycle, so it reads the current problem
  // through a ref rather than restarting whenever the capture changes.
  const captureRef = useRef(capture);
  useEffect(() => {
    captureRef.current = capture;
  }, [capture]);

  useEffect(() => {
    let running = false;
    let again = false;

    async function saveOne(key: string, accepted: AcceptedSubmission): Promise<void> {
      setState({ status: "saving", slug: accepted.slug });

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

        setState({ status: "idle" });
      } catch (err) {
        if (isPermanent(err)) await chrome.storage.local.remove(key);

        setState({
          status: "error",
          slug: accepted.slug,
          message: err instanceof Error ? err.message : String(err),
        });
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
          for (const [key, value] of Object.entries(all)) {
            if (key.startsWith(ACCEPTED_PREFIX)) await saveOne(key, value as AcceptedSubmission);
          }
        } while (again);
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
