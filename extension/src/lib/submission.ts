/**
 * The contract for accepted submissions.
 *
 * content.ts detects one and leaves it in chrome.storage.local; the panel picks
 * it up, has the backend save it, and records the outcome. Both import from
 * here so they cannot drift.
 */

/**
 * Each accepted submission waiting to be saved lives under its own key,
 * `accepted:<submissionId>`.
 *
 * One key per submission rather than one list under one key: content.ts only
 * ever adds keys and the panel only ever removes them, so neither can
 * overwrite a change the other just made.
 */
export const ACCEPTED_PREFIX = "accepted:";

export type AcceptedSubmission = {
  /** LeetCode's id for the submission. Kept as a string: it is an identifier,
   *  not a quantity, and it is already past the 32-bit range. */
  submissionId: string;
  detectedAt: string;
  slug: string;
  title: string | null;
  /** The problem's number as shown on the site, e.g. "200". */
  number: string | null;
  difficulty: string | null;
  topicTags: string[];
  /** LeetCode's language name, e.g. "python3". */
  language: string | null;
  /** The code LeetCode judged — not whatever is in the editor now. */
  code: string;
};

// ---------------------------------------------------------------------------
// Importing past accepted submissions.
//
// The panel asks for it (it holds the session, and the user's button lives
// there); the content script does it (it runs in the logged-in LeetCode tab,
// so LeetCode's own API answers with the user's cookies). They talk through
// this one state object in chrome.storage.local, the same way everything
// else crosses that boundary.
// ---------------------------------------------------------------------------

export const IMPORT_KEY = "import";

/** Problems the user already has solutions for, fetched from the backend by
 *  the panel right before it asks for a scan, so the scan can skip them
 *  before any code is fetched. */
export const SAVED_SLUGS_KEY = "savedSlugs";

/** What the backend expects one summary to cost, fetched with the slugs, so
 *  the panel's "about $X" reflects the model actually configured. Null when
 *  the backend has no price for it. */
export const SUMMARY_COST_KEY = "summaryCostUsd";

/** One past accepted submission the scan found and the import will fetch. */
export type ImportCandidate = {
  submissionId: string;
  slug: string;
  title: string;
  language: string | null;
};

/**
 * `updatedAt` is a heartbeat as much as a timestamp: the content script
 * refreshes it on every page and every fetch, and the panel treats a
 * `scanning` or `importing` state that has gone quiet for a minute as
 * interrupted — a full page reload kills the content script mid-run.
 */
export type ImportState =
  | { status: "idle" }
  /** The panel asked; a content script on a LeetCode tab will pick it up. */
  | { status: "requested"; updatedAt: string }
  | { status: "scanning"; updatedAt: string; pages: number; seen: number; found: number }
  /** The scan finished: these are the problems the import would save. */
  | { status: "scanned"; updatedAt: string; pages: number; seen: number; problems: ImportCandidate[] }
  /** The user confirmed; the content script is fetching code, one per second. */
  | {
      status: "importing";
      updatedAt: string;
      problems: ImportCandidate[];
      total: number;
      fetched: number;
      current: string | null;
    }
  /** The user pressed Stop; the content script stops at the next request. */
  | { status: "cancelling"; updatedAt: string }
  | { status: "cancelled"; updatedAt: string; fetched: number }
  | { status: "done"; updatedAt: string; imported: number }
  | { status: "failed"; updatedAt: string; error: string };

/** Key under which the outcome of the most recent save lives. */
export const SOLUTION_KEY = "lastSolution";

export type SavedSolution = {
  submissionId: string;
  slug: string;
  summary: string;
  /** True when the backend already had this submission, so nothing was
   *  written and no model call was made. */
  alreadySaved: boolean;
  savedAt: string;
};
