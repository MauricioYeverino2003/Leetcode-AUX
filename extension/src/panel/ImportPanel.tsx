import { useEffect, useState } from "react";

import { fetchSavedSlugs } from "../lib/backend";
import { IMPORT_KEY, SAVED_SLUGS_KEY, SUMMARY_COST_KEY, type ImportState } from "../lib/submission";
import { useStored } from "./useStored";

/** A scan or import that has not written progress for this long is taken to
 *  have died with its tab (a full reload kills the content script). */
const STALE_MS = 60_000;

function write(state: ImportState): Promise<void> {
  return chrome.storage.local.set({ [IMPORT_KEY]: state });
}

const now = () => new Date().toISOString();

/**
 * Importing past accepted submissions: the user's side of the import state in
 * lib/submission.ts. This asks, shows, confirms and stops; the content script
 * in the LeetCode tab does the work; the saver saves what it queues.
 */
export function ImportPanel({ saving }: { saving: number }) {
  const state = useStored<ImportState>(IMPORT_KEY) ?? { status: "idle" };
  const costPerSummary = useStored<number>(SUMMARY_COST_KEY);
  const [error, setError] = useState<string | null>(null);

  // Staleness is about wall-clock time, not storage changes, so re-check it.
  const [clock, setClock] = useState(Date.now());
  useEffect(() => {
    const timer = setInterval(() => setClock(Date.now()), 5_000);
    return () => clearInterval(timer);
  }, []);

  const stale =
    (state.status === "scanning" || state.status === "importing") &&
    clock - Date.parse(state.updatedAt) > STALE_MS;

  async function start() {
    setError(null);
    try {
      // What is already saved, so the scan can skip it before fetching code,
      // and what a summary costs on the model the backend has configured.
      const saved = await fetchSavedSlugs();
      await chrome.storage.local.set({
        [SAVED_SLUGS_KEY]: saved.slugs,
        [SUMMARY_COST_KEY]: saved.summary_cost_usd,
      });
      await write({ status: "requested", updatedAt: now() });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  function confirm() {
    if (state.status !== "scanned") return;
    void write({
      status: "importing",
      updatedAt: now(),
      problems: state.problems,
      total: state.problems.length,
      fetched: 0,
      current: null,
    });
  }

  const stop = () => void write({ status: "cancelling", updatedAt: now() });
  const reset = () => void write({ status: "idle" });

  const waiting = state.status === "requested";
  const running = state.status === "scanning" || state.status === "importing";
  // Waiting shows Import too: pressing it again re-asks, which is the way
  // out when no LeetCode tab had the content script the first time.
  const canStart = !running || stale;

  return (
    <section className="import">
      <div className="row">
        <span className="small">Past accepted submissions</span>
        <span className="header-actions">
          {canStart ? (
            <button type="button" onClick={() => void start()} className="btn btn-secondary btn-sm">
              {waiting ? "Try again" : "Import"}
            </button>
          ) : null}
          {waiting ? (
            <button type="button" onClick={reset} className="btn btn-secondary btn-sm">
              Cancel
            </button>
          ) : null}
          {running && !stale ? (
            <button type="button" onClick={stop} className="btn btn-secondary btn-sm">
              Stop
            </button>
          ) : null}
        </span>
      </div>

      {error ? <p className="notice notice-error small">{error}</p> : null}

      {stale ? (
        <p className="notice notice-warn small">
          Interrupted — the LeetCode tab reloaded? Press Import to continue; nothing is saved twice.
        </p>
      ) : (
        <Status state={state} saving={saving} costPerSummary={costPerSummary} onConfirm={confirm} onReset={reset} />
      )}
    </section>
  );
}

function Status({
  state,
  saving,
  costPerSummary,
  onConfirm,
  onReset,
}: {
  state: ImportState;
  saving: number;
  costPerSummary: number | null;
  onConfirm: () => void;
  onReset: () => void;
}) {
  switch (state.status) {
    case "idle":
      return (
        <p className="muted small">
          Save the latest accepted solution for every problem you&rsquo;ve solved on LeetCode. Scans first, then
          asks before anything is saved.
        </p>
      );

    case "requested":
      return (
        <p className="muted small">
          Waiting for a LeetCode tab… If one is open, refresh it (it needs the current extension) and press
          Try again.
        </p>
      );

    case "scanning":
      return (
        <p className="muted small">
          Scanning page {state.pages}… {state.seen} submissions seen, {state.found} problems to import.
        </p>
      );

    case "scanned":
      if (state.problems.length === 0) {
        return (
          <div className="row">
            <p className="muted small">Nothing new to import — all {state.seen} submissions are covered.</p>
            <button type="button" onClick={onReset} className="btn btn-secondary btn-sm">
              OK
            </button>
          </div>
        );
      }
      return (
        <div className="row">
          <p className="small">
            {state.problems.length} problems to import ({state.seen} submissions scanned). Each gets a summary
            from the model
            {costPerSummary !== null
              ? `: about $${(state.problems.length * costPerSummary).toFixed(2)} in all.`
              : " (cost unknown for the configured model)."}
          </p>
          <span className="header-actions">
            <button type="button" onClick={onConfirm} className="btn btn-primary btn-sm">
              Import {state.problems.length}
            </button>
            <button type="button" onClick={onReset} className="btn btn-secondary btn-sm">
              Cancel
            </button>
          </span>
        </div>
      );

    case "importing":
      return (
        <p className="muted small">
          Fetching {state.fetched} of {state.total}
          {state.current ? ` (${state.current})` : ""}
          {saving > 0 ? ` · saving, ${saving} left` : ""}
        </p>
      );

    case "cancelling":
      return <p className="muted small">Stopping…</p>;

    case "cancelled":
      return (
        <p className="muted small">
          Stopped after {state.fetched} fetched{saving > 0 ? `; still saving ${saving}` : ""}.
        </p>
      );

    case "done":
      return (
        <p className="notice notice-info small">
          Fetched {state.imported} problems{saving > 0 ? `; saving ${saving} more` : ", all saved"}.
        </p>
      );

    case "failed":
      return <p className="notice notice-warn small">Import failed: {state.error}</p>;
  }
}
