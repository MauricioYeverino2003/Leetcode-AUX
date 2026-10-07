/**
 * Content script — reads the current LeetCode problem and stores it for the
 * side panel.
 *
 * Two independent strategies, because they fail in different ways:
 *
 *   A. GraphQL — a same-origin POST to leetcode.com/graphql using the user's
 *      own session. Structured, stable, and gives difficulty + topic tags for
 *      free. Validated by the extraction spike; this is the primary path.
 *
 *   B. DOM — a list of candidate selectors. LeetCode's class names are hashed
 *      build output and change without notice, so this is the fallback, and we
 *      try several candidates rather than betting on one.
 *
 * It also watches for a submission's result page and asks LeetCode what the
 * verdict was — see "Submissions" below.
 *
 * This script deliberately holds no auth state and never touches Supabase.
 * It runs alongside leetcode.com's page; its only job is to read and report.
 */

import { CAPTURE_KEY, type Capture } from "./lib/capture";
import {
  BRIDGE_SOURCE,
  CODE_KEY,
  type CodeCapture,
  type CodeMessage,
  type CodeRequest,
} from "./lib/code";
import {
  ACCEPTED_PREFIX,
  IMPORT_KEY,
  SAVED_SLUGS_KEY,
  type AcceptedSubmission,
  type ImportCandidate,
  type ImportState,
} from "./lib/submission";

const LOG = "[LC-AUX]";

/** How long to wait for main-world.ts to report the editor contents before
 *  recording that the editor could not be read. */
const CODE_TIMEOUT_MS = 6_000;

/** Per-selector report in the console. Keep on while the DOM path is young —
 *  it is what tells you which selectors died after a LeetCode redesign. */
const DEBUG = true;

/** Candidate selectors, most specific first. */
const TITLE_SELECTORS = [
  '[data-cy="question-title"]',
  "div.text-title-large a",
  'a[href^="/problems/"].no-underline',
  "div.flexlayout__tab a[href^='/problems/']",
];

const STATEMENT_SELECTORS = [
  '[data-track-load="description_content"]',
  "div.elfjS",
  ".question-content__JfgR",
  'div[class*="elfjS"]',
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getSlug(): string | null {
  const match = location.pathname.match(/^\/problems\/([^/]+)/);
  return match ? match[1] : null;
}

/** The submission whose result page is open, if any. */
function getSubmissionId(): string | null {
  const match = location.pathname.match(/\/submissions\/(?:detail\/)?(\d+)/);
  return match ? match[1] : null;
}

/**
 * HTML → plain text via DOMParser rather than innerHTML on a scratch element.
 * A parsed document is inert: no image requests, no inline event handlers. A
 * content script carries extension privileges, so it should not give markup it
 * did not write any chance to run.
 */
function htmlToText(html: string | null | undefined): string {
  if (!html) return "";
  const doc = new DOMParser().parseFromString(html, "text/html");
  return (doc.body.textContent ?? "").trim();
}

function preview(text: string | null | undefined, n = 400): string {
  if (!text) return "";
  const flat = text.replace(/\s+/g, " ").trim();
  return flat.length > n ? flat.slice(0, n) + "…" : flat;
}

/** LeetCode sets a csrftoken cookie; harmless to send, required by some of
 *  their endpoints. */
function csrfToken(): string | null {
  const match = document.cookie.match(/csrftoken=([^;]+)/);
  return match ? match[1] : null;
}

// ---------------------------------------------------------------------------
// Strategy A — GraphQL
// ---------------------------------------------------------------------------

const QUESTION_QUERY = `
  query questionContent($titleSlug: String!) {
    question(titleSlug: $titleSlug) {
      questionFrontendId
      title
      titleSlug
      difficulty
      isPaidOnly
      content
      topicTags { name slug }
    }
  }
`;

type GraphQLQuestion = {
  questionFrontendId: string;
  title: string;
  titleSlug: string;
  difficulty: string;
  isPaidOnly: boolean;
  /** Statement HTML. Null for premium problems the user cannot access. */
  content: string | null;
  topicTags: { name: string; slug: string }[] | null;
};

/** One same-origin POST to LeetCode's GraphQL endpoint, as the signed-in user. */
async function graphql<T>(operationName: string, query: string, variables: Record<string, unknown>): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = csrfToken();
  if (token) headers["x-csrftoken"] = token;

  const res = await fetch("https://leetcode.com/graphql", {
    method: "POST",
    credentials: "include",
    headers,
    body: JSON.stringify({ operationName, variables, query }),
  });

  if (!res.ok) {
    // A rejected query (unknown field, wrong type) comes back as an error
    // status whose body says which part — worth keeping.
    const body = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status} ${res.statusText}` + (body ? `: ${body.slice(0, 300)}` : ""));
  }

  const json = (await res.json()) as { data?: T | null; errors?: unknown };
  if (json.errors) {
    throw new Error("GraphQL errors: " + JSON.stringify(json.errors).slice(0, 300));
  }
  if (!json.data) throw new Error("No data in response");

  return json.data;
}

async function viaGraphQL(slug: string): Promise<GraphQLQuestion> {
  const data = await graphql<{ question?: GraphQLQuestion | null }>("questionContent", QUESTION_QUERY, {
    titleSlug: slug,
  });
  if (!data.question) throw new Error("No question in response");

  return data.question;
}

// ---------------------------------------------------------------------------
// Strategy B — DOM
// ---------------------------------------------------------------------------

type SelectorHit = { sel: string; ok: boolean; chars: number; text: string | null };

function probe(selectors: string[]): SelectorHit[] {
  return selectors.map((sel) => {
    const text = document.querySelector(sel)?.textContent?.trim() ?? null;
    return { sel, ok: text !== null, chars: text?.length ?? 0, text };
  });
}

function viaDOM() {
  const titleHits = probe(TITLE_SELECTORS);
  const statementHits = probe(STATEMENT_SELECTORS);

  // document.title is "Two Sum - LeetCode" and survives redesigns, so it is
  // worth keeping as a last resort.
  const fromDocTitle = document.title.replace(/\s*-\s*LeetCode.*$/i, "").trim();

  const bestTitle = titleHits.find((h) => h.ok && h.chars > 0);
  const bestStatement = statementHits.find((h) => h.chars > 50);

  return {
    titleHits,
    statementHits,
    title: bestTitle?.text ?? (fromDocTitle || null),
    statementText: bestStatement?.text ?? null,
  };
}

/** The statement is React-rendered, so it is not there on first paint. */
function waitForStatement(timeoutMs = 10_000): Promise<boolean> {
  return new Promise((resolve) => {
    const found = () =>
      STATEMENT_SELECTORS.some(
        (sel) => (document.querySelector(sel)?.textContent?.trim().length ?? 0) > 50,
      );

    if (found()) return resolve(true);

    const observer = new MutationObserver(() => {
      if (found()) {
        observer.disconnect();
        clearTimeout(timer);
        resolve(true);
      }
    });

    observer.observe(document.body, { childList: true, subtree: true });

    const timer = setTimeout(() => {
      observer.disconnect();
      resolve(false);
    }, timeoutMs);
  });
}

// ---------------------------------------------------------------------------
// The user's code
//
// The only source is Monaco, which main-world.ts reads and posts here. There
// are deliberately no fallbacks: a localStorage draft can be stale and a DOM
// scrape is partial by construction (Monaco renders only the lines in view),
// and a tutor reasoning about the wrong code is worse than one that says it
// cannot see the editor. So if nothing arrives in time, that is recorded
// explicitly and the panel says so.
// ---------------------------------------------------------------------------

/** Slug for which a Monaco payload has arrived; the timeout skips that problem. */
let reportedSlug: string | null = null;
let codeTimeout: number | undefined;

function storeCode(capture: CodeCapture): void {
  void chrome.storage.local.set({ [CODE_KEY]: capture });
  console.log(
    capture.status === "ok"
      ? `${LOG} code: ${capture.code.length} chars` + (capture.language ? ` (${capture.language})` : "")
      : `${LOG} code unavailable for "${capture.slug}": ${capture.reason}`,
  );
}

window.addEventListener("message", (event) => {
  // Page scripts could post a message shaped like ours. The worst case is a
  // wrong code capture, which is rendered as text and never executed.
  if (event.source !== window) return;
  const data = event.data as Partial<CodeMessage> | null;
  if (data?.source !== BRIDGE_SOURCE || data.type !== "code" || typeof data.code !== "string") return;

  const slug = getSlug();
  if (!slug) return;

  reportedSlug = slug;
  clearTimeout(codeTimeout);

  storeCode({
    status: "ok",
    capturedAt: new Date().toISOString(),
    slug,
    language: data.language ?? null,
    code: data.code,
    detail: data.detail ?? "",
  });
});

function requestCode(): void {
  const request: CodeRequest = { source: BRIDGE_SOURCE, type: "get-code" };
  window.postMessage(request, location.origin);
}

/** If main-world.ts has not reported this problem's editor within the timeout,
 *  say so explicitly rather than leaving the previous problem's code — or
 *  nothing — on display. A later Monaco message simply overwrites this. */
function scheduleCodeTimeout(slug: string): void {
  clearTimeout(codeTimeout);

  codeTimeout = window.setTimeout(() => {
    if (reportedSlug === slug || getSlug() !== slug) return;

    storeCode({
      status: "unavailable",
      capturedAt: new Date().toISOString(),
      slug,
      reason: `no editor contents reported within ${CODE_TIMEOUT_MS / 1000}s`,
    });
  }, CODE_TIMEOUT_MS);
}

// ---------------------------------------------------------------------------
// Extract + store
// ---------------------------------------------------------------------------

async function extract(): Promise<void> {
  const slug = getSlug();
  if (!slug) return;

  // Ask main-world.ts for the editor contents right away, and note it if
  // nothing comes. Independent of the statement extraction below.
  requestCode();
  scheduleCodeTimeout(slug);

  const domReady = await waitForStatement();

  let question: GraphQLQuestion | null = null;
  let graphqlError: string | null = null;
  try {
    question = await viaGraphQL(slug);
  } catch (err) {
    graphqlError = err instanceof Error ? err.message : String(err);
  }

  const dom = viaDOM();

  // Extraction is async. If the user has already clicked through to another
  // problem, this result is stale — drop it rather than overwrite the capture
  // that the newer extraction is about to (or already did) store.
  if (getSlug() !== slug) {
    console.log(`${LOG} "${slug}" finished after navigation — discarded`);
    return;
  }

  const winner: Capture["winner"] = question ? "graphql" : dom.statementText ? "dom" : "none";
  const statementText = htmlToText(question?.content);

  const capture: Capture = {
    capturedAt: new Date().toISOString(),
    url: location.href,
    slug,
    winner,
    graphql: question
      ? {
          title: question.title,
          number: question.questionFrontendId,
          difficulty: question.difficulty,
          paidOnly: question.isPaidOnly,
          topicTags: (question.topicTags ?? []).map((t) => t.name),
          statement: statementText,
          statementChars: statementText.length,
          statementPreview: preview(statementText),
        }
      : null,
    graphqlError,
    dom: {
      title: dom.title,
      titleSelectorsMatched: dom.titleHits.filter((h) => h.ok).map((h) => h.sel),
      statementSelectorsMatched: dom.statementHits.filter((h) => h.ok).map((h) => h.sel),
      statement: dom.statementText,
      statementChars: dom.statementText?.length ?? 0,
      statementPreview: preview(dom.statementText),
    },
  };

  await chrome.storage.local.set({ [CAPTURE_KEY]: capture });

  console.log(
    `${LOG} captured "${slug}" via ${winner}` +
      (question ? ` — ${question.questionFrontendId}. ${question.title} (${question.difficulty})` : ""),
  );

  if (DEBUG) {
    console.groupCollapsed(`${LOG} details`);
    console.log("statement rendered in DOM before timeout:", domReady);
    if (graphqlError) console.log("GraphQL error:", graphqlError);
    console.table([
      ...dom.titleHits.map((h) => ({ kind: "title", sel: h.sel, ok: h.ok, chars: h.chars })),
      ...dom.statementHits.map((h) => ({ kind: "statement", sel: h.sel, ok: h.ok, chars: h.chars })),
    ]);
    console.groupEnd();
  }
}

// ---------------------------------------------------------------------------
// SPA navigation
//
// LeetCode does not reload between problems, so a script that only ran once
// would go stale the moment you click "Next".
//
// The obvious trick — wrapping history.pushState — does NOT work from a content
// script. Content scripts run in an isolated world with their own JavaScript
// wrappers around DOM objects, so replacing history.pushState here replaces a
// copy the page's router never calls. (The extraction spike had exactly that
// patch; it was the fallback poll that was really doing the work.)
//
// Events are different: they are dispatched to listeners in every world. So we
// listen for the Navigation API's `currententrychange`, which fires for
// pushState / replaceState / back / forward alike, and keep a slow poll as
// insurance for browsers or routers where that event does not fire.
// ---------------------------------------------------------------------------

/** Runs `check` whenever the URL may have changed. */
function onUrlChange(check: () => void): void {
  const navigation = (window as Window & { navigation?: EventTarget }).navigation;
  navigation?.addEventListener("currententrychange", check);

  window.addEventListener("popstate", check);
  setInterval(check, 1000);
}

function onProblemChange(callback: () => void): void {
  // Track the slug, not the href. LeetCode rewrites the URL when you switch
  // between the Description / Editorial / Submissions tabs, and re-fetching
  // the same problem on every tab click is wasted work.
  let last = getSlug();

  onUrlChange(() => {
    const slug = getSlug();
    if (slug && slug !== last) {
      last = slug;
      callback();
    }
  });
}

// ---------------------------------------------------------------------------
// Submissions
//
// After Submit, LeetCode moves to /problems/<slug>/submissions/<id>/. Seeing
// that URL is the trigger; the verdict comes from asking LeetCode about that
// id, which also returns the exact code that was judged.
//
// Validated by a spike on a live account: the result page opens while the
// submission is still being judged (statusCode 16), and the same query
// answers 10 a few seconds later once it is accepted.
//
// An accepted submission is left in chrome.storage.local for the panel, which
// holds the session and does the saving. Opening an old accepted submission
// from the Submissions tab lands here too; the backend stores each id once.
// ---------------------------------------------------------------------------

const SUBMISSION_QUERY = `
  query submissionDetails($submissionId: Int!) {
    submissionDetails(submissionId: $submissionId) {
      statusCode
      code
      lang { name verboseName }
      question {
        questionFrontendId
        title
        titleSlug
        difficulty
        topicTags { name }
      }
    }
  }
`;

type GraphQLSubmission = {
  statusCode: number | null;
  code: string | null;
  lang: { name: string; verboseName: string } | null;
  question: {
    questionFrontendId: string;
    title: string;
    titleSlug: string;
    difficulty: string;
    topicTags: { name: string }[] | null;
  } | null;
};

const STATUS_ACCEPTED = 10;
const STATUS_JUDGING = 16;

const SUBMISSION_POLL_MS = 1_500;
/** About 30 seconds in all — well past how long judging normally takes. */
const SUBMISSION_POLL_TRIES = 20;

async function viaSubmissionDetails(id: string): Promise<GraphQLSubmission | null> {
  const data = await graphql<{ submissionDetails?: GraphQLSubmission | null }>(
    "submissionDetails",
    SUBMISSION_QUERY,
    { submissionId: Number(id) },
  );
  return data.submissionDetails ?? null;
}

async function storeAccepted(id: string, submission: GraphQLSubmission): Promise<void> {
  const q = submission.question;
  const slug = q?.titleSlug ?? getSlug();

  if (!submission.code || !slug) {
    console.log(`${LOG} submission ${id}: accepted, but LeetCode returned no code — nothing to save`);
    return;
  }

  const accepted: AcceptedSubmission = {
    submissionId: id,
    detectedAt: new Date().toISOString(),
    slug,
    title: q?.title ?? null,
    number: q?.questionFrontendId ?? null,
    difficulty: q?.difficulty ?? null,
    topicTags: (q?.topicTags ?? []).map((t) => t.name),
    language: submission.lang?.name ?? null,
    code: submission.code,
  };

  await chrome.storage.local.set({ [ACCEPTED_PREFIX + id]: accepted });

  console.log(
    `${LOG} submission ${id}: accepted — ${accepted.code.length} chars` +
      (accepted.language ? ` (${accepted.language})` : "") +
      ", queued for saving",
  );
}

/** Asks until LeetCode has a verdict: the result page opens while the
 *  submission is still being judged. A failed request counts as "ask again",
 *  so one dropped connection does not lose an accepted submission. */
async function watchSubmission(id: string): Promise<void> {
  let lastError: string | null = null;

  for (let attempt = 1; attempt <= SUBMISSION_POLL_TRIES; attempt++) {
    try {
      const submission = await viaSubmissionDetails(id);
      const status = submission?.statusCode ?? null;

      if (submission && status !== null && status !== STATUS_JUDGING) {
        if (status === STATUS_ACCEPTED) {
          await storeAccepted(id, submission);
        } else {
          console.log(`${LOG} submission ${id}: not accepted (statusCode ${status})`);
        }
        return;
      }
    } catch (err) {
      lastError = err instanceof Error ? err.message : String(err);
    }

    await sleep(SUBMISSION_POLL_MS);
  }

  const waited = Math.round((SUBMISSION_POLL_TRIES * SUBMISSION_POLL_MS) / 1000);
  console.log(
    `${LOG} submission ${id}: no verdict after ${waited}s — giving up` + (lastError ? ` (${lastError})` : ""),
  );
}

function onSubmissionView(callback: (id: string) => void): void {
  // Each id once per page load: LeetCode rewrites the URL as you move between
  // tabs, and coming back to the same result is not a new submission.
  const seen = new Set<string>();

  const check = () => {
    const id = getSubmissionId();
    if (id && !seen.has(id)) {
      seen.add(id);
      callback(id);
    }
  };

  check();
  onUrlChange(check);
}

// ---------------------------------------------------------------------------
// Importing past accepted submissions
//
// LeetCode's own site lists a user's submissions through the same GraphQL
// endpoint, 20 per page, newest first, without the code; the code comes from
// submissionDetails, as for a live verdict. Both run here, in the logged-in
// tab, so the browser attaches the user's own cookies and nothing is copied.
// Validated by a spike on a live account (2026-10-07): the query as written,
// statusDisplay "Accepted", numeric-string ids, Unix-second timestamps.
//
// Two phases, driven by the import state in chrome.storage (lib/submission.ts):
// the panel sets `requested`, this scans every page and reports what it would
// import; the panel shows that with a cost estimate and sets `importing`;
// this fetches each submission's code into the same accepted:<id> queue the
// live detection uses, and the panel saves them as usual. Requests to
// LeetCode are spaced one second apart with backoff on failure — the pacing
// leetcode-sync uses on whole histories.
// ---------------------------------------------------------------------------

const SUBMISSION_LIST_QUERY = `
  query submissionList($offset: Int!, $limit: Int!) {
    submissionList(offset: $offset, limit: $limit) {
      hasNext
      submissions {
        id
        statusDisplay
        lang
        timestamp
        title
        titleSlug
      }
    }
  }
`;

type GraphQLSubmissionList = {
  hasNext: boolean;
  submissions: {
    id: string;
    statusDisplay: string;
    lang: string;
    timestamp: string;
    title: string;
    titleSlug: string;
  }[];
};

async function viaSubmissionList(offset: number, limit: number): Promise<GraphQLSubmissionList> {
  const data = await graphql<{ submissionList?: GraphQLSubmissionList | null }>(
    "submissionList",
    SUBMISSION_LIST_QUERY,
    { offset, limit },
  );
  if (!data.submissionList) throw new Error("No submissionList in response");
  return data.submissionList;
}

const IMPORT_PAGE_SIZE = 20;
const IMPORT_PACE_MS = 1_000;
const IMPORT_RETRIES = 5;

const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

let lastLeetCodeRequest = 0;

/** Runs one LeetCode request no sooner than a second after the previous one,
 *  retrying failures with exponential backoff (3s, 9s, 27s, …). A rejected
 *  query is not retried: it would be rejected again. */
async function paced<T>(call: () => Promise<T>): Promise<T> {
  for (let attempt = 1; ; attempt++) {
    const wait = lastLeetCodeRequest + IMPORT_PACE_MS - Date.now();
    if (wait > 0) await sleep(wait);
    lastLeetCodeRequest = Date.now();

    try {
      return await call();
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      if (message.startsWith("GraphQL errors") || attempt >= IMPORT_RETRIES) throw err;
      const backoff = 3 ** attempt * 1000;
      console.log(`${LOG} import: request failed (${message}) — retrying in ${backoff / 1000}s`);
      await sleep(backoff);
    }
  }
}

/** ImportState minus the heartbeat, which setImport stamps. Written as a
 *  conditional type so it distributes over the union: a plain Omit would
 *  keep only the fields every variant shares. */
type StoredImport = ImportState extends infer S ? (S extends ImportState ? Omit<S, "updatedAt"> : never) : never;

function setImport(state: StoredImport): Promise<void> {
  return chrome.storage.local.set({ [IMPORT_KEY]: { ...state, updatedAt: new Date().toISOString() } });
}

async function importStatus(): Promise<ImportState["status"] | undefined> {
  const stored = await chrome.storage.local.get(IMPORT_KEY);
  return (stored[IMPORT_KEY] as ImportState | undefined)?.status;
}

/** Every page of the user's submissions, kept down to the latest accepted
 *  one per problem, minus the problems already saved. Fetches no code. */
async function scanSubmissions(): Promise<void> {
  // Another LeetCode tab may have picked the request up first.
  if ((await importStatus()) !== "requested") return;

  const stored = await chrome.storage.local.get(SAVED_SLUGS_KEY);
  const saved = new Set<string>((stored[SAVED_SLUGS_KEY] as string[] | undefined) ?? []);

  const seen = new Set<string>();
  const problems: ImportCandidate[] = [];
  let pages = 0;
  let total = 0;
  await setImport({ status: "scanning", pages, seen: total, found: 0 });

  for (;;) {
    if ((await importStatus()) === "cancelling") {
      await setImport({ status: "cancelled", fetched: 0 });
      return;
    }

    const page = await paced(() => viaSubmissionList(total, IMPORT_PAGE_SIZE));
    pages += 1;
    total += page.submissions.length;

    // Newest first, so the first accepted entry for a slug is its latest.
    for (const s of page.submissions) {
      if (s.statusDisplay !== "Accepted" || seen.has(s.titleSlug)) continue;
      seen.add(s.titleSlug);
      if (saved.has(s.titleSlug)) continue;
      problems.push({ submissionId: s.id, slug: s.titleSlug, title: s.title, language: s.lang || null });
    }

    await setImport({ status: "scanning", pages, seen: total, found: problems.length });
    if (!page.hasNext || page.submissions.length === 0) break;
  }

  console.log(
    `${LOG} import: scanned ${total} submission(s) on ${pages} page(s) — ` +
      `${problems.length} problem(s) to import, ${saved.size} already saved`,
  );
  await setImport({ status: "scanned", pages, seen: total, problems });
}

/** Fetches each candidate's code and queues it exactly as a live accepted
 *  submission is queued; the panel does the saving. */
async function importSubmissions(problems: ImportCandidate[]): Promise<void> {
  let fetched = 0;

  for (const p of problems) {
    if ((await importStatus()) === "cancelling") {
      await setImport({ status: "cancelled", fetched });
      return;
    }
    await setImport({ status: "importing", problems, total: problems.length, fetched, current: p.slug });

    try {
      const details = await paced(() => viaSubmissionDetails(p.submissionId));
      if (details && details.statusCode === STATUS_ACCEPTED) {
        await storeAccepted(p.submissionId, details);
      } else {
        console.log(`${LOG} import: ${p.slug} (${p.submissionId}) — not returned as accepted, skipped`);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      console.log(`${LOG} import: ${p.slug} (${p.submissionId}) — gave up (${message}), skipped`);
    }
    fetched += 1;
  }

  await setImport({ status: "done", imported: fetched });
}

let importBusy = false;

async function runImportStep(step: () => Promise<void>): Promise<void> {
  if (importBusy) return;
  importBusy = true;
  try {
    await step();
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    console.log(`${LOG} import: failed — ${message}`);
    await setImport({ status: "failed", error: message });
  } finally {
    importBusy = false;
  }
}

chrome.storage.onChanged.addListener((changes, area) => {
  if (area !== "local" || !changes[IMPORT_KEY]) return;
  const prev = changes[IMPORT_KEY].oldValue as ImportState | undefined;
  const next = changes[IMPORT_KEY].newValue as ImportState | undefined;
  if (!next) return;

  // Every `requested` write is a request — including one that overwrites a
  // stale `requested` nobody answered. `importing` only counts when the panel
  // just confirmed a scan; this script's own progress writes keep that status
  // and must not restart the run.
  if (next.status === "requested") void runImportStep(scanSubmissions);
  if (next.status === "importing" && prev?.status === "scanned") {
    void runImportStep(() => importSubmissions(next.problems));
  }
});

void extract();
onProblemChange(() => {
  console.log(`${LOG} problem changed → re-extracting`);
  void extract();
});
onSubmissionView((id) => void watchSubmission(id));
