/**
 * The contract for the user's editor contents.
 *
 * Three parties share it: main-world.ts (reads Monaco in the page's own JS
 * world), content.ts (stores the result), and the panel (renders it). All
 * import from here so they cannot drift.
 */

/** Key under which the latest code capture lives in chrome.storage.local. */
export const CODE_KEY = "lastCode";

/**
 * Either the editor's contents, or an explicit record that they could not be
 * read. There is deliberately no degraded middle ground (a stale draft, a
 * partial scrape): a tutor reasoning about the wrong code is worse than one
 * that says it cannot see the editor.
 */
export type CodeCapture =
  | {
      status: "ok";
      capturedAt: string;
      /** The problem page the code was read from. */
      slug: string;
      /** Monaco's language id, e.g. "python", "cpp". Null when unknown. */
      language: string | null;
      code: string;
      /** Which editor was chosen and why — for debugging, not display. */
      detail: string;
    }
  | {
      status: "unavailable";
      capturedAt: string;
      slug: string;
      reason: string;
    };

// ---------------------------------------------------------------------------
// Bridge between the MAIN world and the isolated world.
//
// main-world.ts cannot call chrome.* and content.ts cannot see window.monaco,
// so they talk over window.postMessage. `source` namespaces our messages away
// from anything LeetCode itself posts.
// ---------------------------------------------------------------------------

export const BRIDGE_SOURCE = "lc-aux";

/** MAIN → isolated: here is the editor's current contents. */
export type CodeMessage = {
  source: typeof BRIDGE_SOURCE;
  type: "code";
  code: string;
  language: string | null;
  detail: string;
};

/** isolated → MAIN: please publish the editor's contents now. */
export type CodeRequest = {
  source: typeof BRIDGE_SOURCE;
  type: "get-code";
};
