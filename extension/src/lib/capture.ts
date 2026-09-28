/**
 * The contract between the content script (which writes a capture) and the
 * side panel (which reads it). Both import from here so they cannot drift.
 */

/** Key under which the latest capture lives in chrome.storage.local. */
export const CAPTURE_KEY = "lastCapture";

export type Capture = {
  capturedAt: string;
  url: string;
  slug: string;
  /** Which strategy produced the usable result. */
  winner: "graphql" | "dom" | "none";

  graphql: {
    title: string;
    number: string;
    difficulty: string;
    paidOnly: boolean;
    topicTags: string[];
    /** Full statement as plain text — this is what the backend receives. */
    statement: string;
    statementChars: number;
    statementPreview: string;
  } | null;
  graphqlError: string | null;

  dom: {
    title: string | null;
    titleSelectorsMatched: string[];
    statementSelectorsMatched: string[];
    statement: string | null;
    statementChars: number;
    statementPreview: string;
  };
};
