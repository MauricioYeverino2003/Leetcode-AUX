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
