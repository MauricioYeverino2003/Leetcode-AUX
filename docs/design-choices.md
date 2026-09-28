# Design Choices

A running log of architectural decisions and the reasoning behind them.

_Last updated: 2026-09-20_

## How to read this

Each entry states the situation, the decision, the reasoning, and what it costs.
Entries are self-contained, so you can read one without the others.

A decision here isn't permanent. When one turns out wrong, add an entry that
supersedes it rather than editing history — reasoning that led somewhere wrong
is usually worth keeping.

---

## Chrome extension, not a standalone web app

Build the product as a browser extension that overlays leetcode.com, rather than
a Next.js site that hosts its own problems and code editor.

**Context.** The original plan was a web app with its own problem catalog, editor
and judge. That required solving test-case correctness from scratch: sourcing
problems, authoring test suites, and running untrusted code in a sandbox.

**Why.** The extension doesn't solve the test-correctness problem — it deletes
it. LeetCode's own judge becomes the oracle, and it's the one users already trust
and will be graded against in real interviews. It also gives the agent signals a
standalone app structurally cannot get:

- The real verdict. `Time Limit Exceeded` and `Wrong Answer` are completely
  different coaching conversations — TLE means the logic is right and the
  complexity is wrong.
- Which test case failed, and what it expected.
- The code as it is being written, not after the fact.

**Cost.** Dependence on a platform we don't control. LeetCode's DOM can change,
they can block extensions, and they are shipping their own AI assistant.
Mitigated by reading their GraphQL API rather than the DOM (see below), and by
accepting that this is a real risk rather than engineering around it.

**Consequence.** No code execution, no test authoring, no problem catalog, no
comparator design. Roughly three sessions of research into TACO, HackerRank and
test-generation pipelines became unnecessary.

**Status.** The Next.js app in `frontend/` was kept parked as a reference and a
possible home for a progress dashboard, then deleted on 2026-09-27 — nothing
used it, and a dead folder in a resume repo invites the wrong question. If a
web surface is ever wanted, it starts fresh. Its nested git repo went with it.

---

## `@supabase/ssr` → `@supabase/supabase-js` + `chrome.storage`

Drop `@supabase/ssr` and use `@supabase/supabase-js` with a custom storage
adapter over `chrome.storage.local`.

**Context.** The working login in `frontend/` uses `createBrowserClient` from
`@supabase/ssr`, server actions marked `"use server"`, and `src/proxy.ts` for
route protection. None of it survives the move to an extension.

**Why.** `createBrowserClient` is not "the browser version of Supabase." It is
the browser half of a server-rendering handshake: it writes the session into
`document.cookie` so that a server can read that cookie on the next request and
rebuild the same session server-side. That is its entire reason to exist.

An extension has no rendering server, so the handshake has no other side. Cookies
are also the wrong medium here — the side panel runs on `chrome-extension://<id>/`,
its own origin. A cookie set there is invisible to the service worker and
meaningless to leetcode.com.

Every Next-specific piece fails for the same underlying reason, not four separate
ones:

| In `frontend/` | Why it can't come | Replacement |
| --- | --- | --- |
| `createBrowserClient` | Persists the session to cookies for a server to read back | `createClient` + `chrome.storage.local` adapter |
| `"use server"` actions | Compiles to an RPC to a server that doesn't exist | Plain `async` submit handler |
| `useActionState`, `revalidatePath`, `redirect` | Assume a server round-trip and a server router | `useState` + conditional render |
| `src/proxy.ts` | Intercepts HTTP requests before render; a panel is a static file | `session ? <SignedIn/> : <LoginForm/>` |

**What makes the adapter work.** Supabase's `auth.storage` option takes
`SupportedStorage` — `getItem`, `setItem`, `removeItem` — and those methods are
allowed to return promises. That is the detail that matters: `chrome.storage` is
async while `localStorage` is not, so without promise support this approach would
not be possible at all.

Also set `detectSessionInUrl: false`. There is no OAuth fragment to parse in a
panel.

**What is unchanged.** The Supabase project, the users, RLS, and the local stack.
The `signInWithPassword`, `signUp` and `signOut` calls are identical — same
functions, same arguments, same error shapes. The form markup in
`frontend/src/app/login/page.tsx` ports over almost verbatim.

**Cost.** About an hour of Next-specific wiring is discarded. The auth _workflow_
is not rebuilt, only its plumbing.

---

## Agent logic lives in the backend, not the extension

Prompt construction, history retrieval and the Claude call all happen in
`backend/` (FastAPI). The extension reads the page, renders the chat, and holds
the session.

**Context.** The extension could do this work itself: query Supabase directly for
history, build the prompt client-side, and use the backend as a thin forwarding
proxy.

**Why.** Chrome Web Store review takes days. Prompt logic inside the extension
means every tweak is a new version and a wait in a review queue — and the system
prompt will be tuned dozens of times in the first month. On the server it is a
`git push`.

Secondary reasons: the system prompt stays private rather than sitting in a
bundle anyone can unzip, and the server holds the service role key, so it can
write assistant messages that RLS forbids the client to forge.

**Division of labour.**

```mermaid
flowchart LR
  A[Extension<br/>content script] --> B[Side panel<br/>chat UI]
  B -->|JWT + slug<br/>+ code| C[FastAPI<br/>agent]
  C --> D[(Supabase<br/>Postgres)]
  B -->|auth only| D
```

The extension uses `supabase-js` for authentication and simple history reads. The
backend verifies the Supabase JWT, does retrieval, calls Claude, and writes the
turn back.

**Consequence.** The extension gets thinner, not thicker. `patterns.json` also
lives server-side for the same reason — a mislabelled problem can be fixed
instantly instead of shipping a release.

**Cost.** A server to run and pay for. Bring-your-own-key would avoid that, but
then the project has no backend in it at all, which is a visible gap if the
target is backend or full-stack roles. Resolved in the next entry.

---

## One Anthropic key, held by the backend — not bring-your-own

The backend holds a single Anthropic API key in its environment and pays for
every request. Users never see or handle a key.

**Context.** The alternative is the "insert your own key" model common in
frontend-only AI products. Those products have nowhere to hide a key, so the
model is a constraint for them rather than a choice. With a backend (previous
entry) the constraint does not apply, which turns this into a real decision.

The two questions are independent: *where the Claude call runs* (settled:
backend) and *whose key pays*. This entry is only about the second.

**Why.**

- The demo has to work for strangers. Interviewers will not paste an API key
  into an unknown extension, and most LeetCode users do not have one — getting
  one means a Console account and a credit card. BYO-key makes the product work
  for exactly one person.
- It is the better engineering story. Holding the key forces the backend to
  solve JWT verification, per-user quotas, rate limiting, spend caps and usage
  logging. A BYO proxy solves none of them.
- BYO-key has its own security problem: a long-lived key in `chrome.storage`
  is readable by anyone at that browser.

**Cost.** Rough planning estimate per hint — ~3,000 input tokens and ~1,000
output tokens including thinking; measure once the prompt exists:

| Model | Per hint | Per active user / month* |
| --- | --- | --- |
| Claude Opus 5 (default) | ~$0.04 | ~$4 |
| Claude Sonnet 5 | ~$0.016 | ~$1.60 |
| Claude Haiku 4.5 | ~$0.008 | ~$0.80 |

\*10 hints per session, 3 sessions a week. Prompt caching on the system prompt
and statement brings real numbers below these. Start on Opus 5; step down only
on measured spend, not on a guess.

**Controls that make it safe** — signup is open, so without these any stranger
can spend the budget:

1. A monthly spend limit in the Anthropic Console, set before the backend
   exists. The guarantee against a surprise bill regardless of what ships.
2. A per-user daily hint quota, enforced server-side and tracked in Supabase.
3. A per-user rate limit — a few requests a minute.
4. `usage` from every response logged to Supabase, so cost per hint is a
   number rather than a feeling.
5. Prompt caching on the stable prefix, and `effort` tuned for hints.
6. The Supabase JWT is verified before Claude is called — already decided.

**Door left open.** The key is resolved per request through one function that
today returns the environment variable. A "bring your own key for unlimited
use" tier later is a settings field and a one-line change, not a redesign. Not
built now.

**See also.** *Two interchangeable model providers* below — "the key" is now
whichever vendor `LLM_PROVIDER` selects. The reasoning here (backend holds it,
users never do) is unchanged.

---

## Two interchangeable model providers, one tutor

`backend/app/providers/` holds one module per vendor — `claude.py` (Anthropic,
Messages API) and `gpt.py` (OpenAI, Responses API) — behind one contract,
selected by `LLM_PROVIDER` in `.env`. The tutor itself lives in
`app/prompt.py` and is shared, so switching vendors changes plumbing and
nothing the user experiences.

**Context.** Two corrections to earlier entries prompted this. Anthropic's API
has no free credit — the "$5 for new accounts" repeated above came from
secondary sources and the Console simply asks for a prepaid block. And OpenAI
offers free daily tokens (reportedly 1M/day on large models) in exchange for a
data-sharing opt-in. Whether that offer is real for this account, and whether
GPT holds the hint ladder under pressure as well as Claude does, are questions
worth answering with the same backend rather than two.

**Shape.**

| Shared (vendor-neutral) | Per provider |
| --- | --- |
| `prompt.py`: rules, problem block, code block | SDK client and its lazy, fail-clear construction |
| `schemas.py`: request/response, size limits | How the prompt is laid out for that API's caching |
| `providers/base.py`: `Provider` protocol, `ProviderError(status, detail)` | Translating the SDK's exceptions into `ProviderError` |
| `main.py`: auth, route, usage log — imports no vendor SDK | Reading the reply, refusal and cut-off signals |

Each provider's SDK is imported only when selected, so the other can be absent
or misconfigured with no effect.

**What the abstraction does not hide.** These differ by vendor and are
documented in each module rather than papered over:

- Prompt caching: Anthropic needs an explicit breakpoint after the problem
  statement; OpenAI caches matching prefixes automatically. Both providers
  order the prompt stable-first, so both benefit.
- Refusals: Anthropic's server-side fallback re-runs a declined request on
  another model; OpenAI returns a `refusal` part and the user sees a fixed
  message.
- Usage: OpenAI reports cached input but has no cache-write charge, so that
  field is always zero for it.

**Cost.** Two SDKs to keep current, and every provider-facing test runs twice.
Accepted because the alternative — rewriting one file each time the vendor
question comes up — is worse, and because the comparison itself is the point.

**Status.** Verified without spending: both providers import, `/health` reports
the active provider and model, the OpenAI input shape and reply parsing (text,
refusal, cut-short) are checked against constructed SDK objects, and a missing
key yields a 503 on either. Live calls await keys.

---

## First working chat: `POST /chat`, verified by JWKS, deliberately unstreamed

The first end-to-end milestone (2026-09-22): the panel sends the transcript
plus the captured problem and code to `backend/`, which calls Claude with the
backend's key and returns the reply. Three decisions inside it are worth
keeping.

**Tokens are verified against Supabase's JWKS, not a shared secret.** The
first version verified HS256 with the local stack's well-known JWT secret. The
first real token rejected it: current Supabase — the local CLI included — signs
access tokens with ES256 and publishes the public key at
`/auth/v1/.well-known/jwks.json`. Verification now fetches and caches those
keys; an HS256 path remains for instances still configured that way, selected
by the token's `alg` header against an allowlist. The anon key, a JWT from the
same issuer with `aud: anon`, is rejected by the audience check.

**Prompt layout is chosen for caching.** The cache is a prefix match, so the
system prompt holds the stable content — rules, then the problem statement with
the cache breakpoint — and the user's current code rides in the *last* user turn
as a separate text block. Putting the code anywhere earlier would invalidate
the cache on every keystroke.

**Refusal fallback is on.** `fallbacks: "default"` re-runs a safety-declined
request on Anthropic's recommended fallback model server-side, so a user gets an
answer rather than a refusal.

**Deliberately not in this milestone.**

| Left out | Why now, and what it costs |
| --- | --- |
| Streaming | One JSON round trip is simpler to debug. Cost: a visible pause of several seconds per reply. First thing to add once the loop is proven. |
| Persistence | Transcript lives in panel state; closing the panel ends the chat. |
| Quota, rate limit | The schema's size limits are the only cost control in code. The Console spend cap is the real one until these land. |

The size limits on the request schema are not cosmetic: every byte a client
sends becomes prompt tokens billed to the backend's key.

**Status.** Verified without a key: health, auth accept/reject (real token,
anon key, tampered payload), validation, and a clear 503 when no key is
configured. The Claude call itself awaits a key in `backend/.env`.

---

## Read problems via LeetCode's GraphQL, with DOM as fallback

The content script POSTs to `leetcode.com/graphql` same-origin using the user's
own session. DOM selectors stay as a secondary path.

**Context.** The obvious approach is scraping the page. It is also the fragile
one: LeetCode's class names are hashed build output that changes without notice,
and the statement is React-rendered so it is absent from the initial HTML.

**Why.** A content script running on leetcode.com can call their own API
same-origin with the user's cookies. It returns structured data — `title`,
`questionFrontendId`, `difficulty`, `topicTags`, and clean statement HTML —
instead of text scraped out of styled divs.

**Validated.** The spike ran both strategies and reported which won. On
`number-of-islands`:

| Strategy | Result |
| --- | --- |
| GraphQL | OK — full structured payload |
| DOM | statement found, `document.title` gave the name |
| Verdict | `graphql` |

Both paths work today, so the fallback is real rather than theoretical.

**Bug the spike caught.** Tracking `location.href` for navigation fires on every
tab switch between Description / Editorial / Submissions, because LeetCode
rewrites the URL without changing the problem. That meant a redundant GraphQL
request per tab click. Fixed by tracking the slug instead.

**A second bug, found while porting the spike.** The spike wrapped
`history.pushState` to notice SPA navigation. That can never work from a content
script: the isolated world has its own JavaScript wrappers around DOM objects, so
the wrapper replaced a copy of `pushState` that LeetCode's router never calls.
Navigation detection appeared to work only because a 1-second fallback poll was
quietly doing the whole job. Replaced with a `currententrychange` listener on the
Navigation API — events, unlike property overrides, are delivered to every world
— with the poll kept as insurance.

**Content script matches all of `leetcode.com`, not just `/problems/*`.** Content
scripts inject on page load. Landing on the problem list and clicking into a
problem is an SPA transition with no page load, so a `/problems/*` match would
never inject. The script no-ops until the URL is a problem page.

**Cost.** An undocumented endpoint can go behind auth at any time. The DOM
fallback is the insurance, and it is why both paths are kept rather than deleting
the loser.

---

## Read the editor from a MAIN-world script, bridged over `postMessage`

A second content script declared with `"world": "MAIN"` reads the user's code
from `window.monaco` and posts it to the isolated-world script, which stores it.

**Context.** The agent needs the code as it is being written. Two facts rule out
the obvious approaches: content scripts run in an isolated world and cannot see
page globals like `window.monaco`; and Monaco virtualizes rendering, so the DOM
only ever holds the lines currently scrolled into view.

**Why.** Chrome's `"world": "MAIN"` option runs a content script in the page's
own JavaScript context, where Monaco's API is reachable — the model's
`getValue()` returns the complete buffer, and `onDidChangeContent` makes it live.
The price is that `chrome.*` is unavailable there, so the result crosses back
over `window.postMessage` (same-origin target) to the isolated script, which
alone touches `chrome.storage`.

**Choosing the editor.** LeetCode may hold several Monaco instances. The one the
user is typing in is the largest visible one with a model. Older Monaco builds
lack `getEditors()`; then the fallback is the model with the most non-plaintext
content.

**No fallbacks — loud failure instead.** The first version shipped two
degraded paths for when Monaco was unreachable: LeetCode's `localStorage` draft
(complete but possibly stale) and a scrape of the rendered `.view-line`
elements (current but partial by construction). Both were removed the same day,
once the Monaco path was confirmed working, for three reasons:

- They were never exercised — Monaco worked on the first run — so they were
  untested code posing as insurance.
- For a tutor, wrong context is worse than no context. Stale or truncated code
  produces confidently wrong hints, and nobody notices for a while. A visible
  "can't read the editor" gets reported and fixed the same day.
- The realistic failure — LeetCode stops exposing `window.monaco` — would need a
  different MAIN-world technique to fix, not a storage scan.

This is a different call from the problem statement, where the DOM fallback
stays: statements are not virtualized, so that path is complete, and they do
not change under you.

If nothing arrives within 6 seconds, the capture is recorded as `unavailable`
with a reason, and the panel says so.

**Trust boundary.** The MAIN-world script is the least trusted code in the
extension: page scripts can see and call it. It holds no secrets and no auth
state, and its messages are treated as data — the code is rendered as text,
never executed. A page script could spoof a message; the worst outcome is a
wrong capture.

**Build.** IIFE output cannot code-split, so the two content scripts cannot share
one Vite pass. `vite.content.config.ts` is a function of `--mode` and runs once
per script.

**Status.** Validated 2026-09-21: `window.monaco` is a global on LeetCode, the
editor API is present, and the panel updates live as the user types.

---

## NeetCode's pattern map for "similar problems"

Use `.problemSiteData.json` from [neetcode-gh/leetcode](https://github.com/neetcode-gh/leetcode)
(MIT) as the source of problem similarity, not TACO and not LeetCode's own topic
tags.

**Context.** The feature is: recognise that the current problem resembles
something the user already solved, and open with that. It needs a notion of
similarity.

**What the file gives.** 450 problems, 188KB:

- `neetcode150` and `blind75` membership flags — a ready-made difficulty
  progression
- **19 patterns** — Arrays & Hashing, Two Pointers, Sliding Window, Binary
  Search, Backtracking, 1-D DP, 2-D DP, Greedy, Intervals, Bit Manipulation and
  others
- Difficulty (109 Easy / 289 Medium / 52 Hard), LeetCode slug, and a YouTube
  video id for every problem

**Why not LeetCode's tags.** GraphQL returns `topicTags` for free, but they are
structural labels and there are several per problem — Number of Islands carries
Array, DFS, BFS, Union Find and Matrix. For coaching, one canonical pedagogical
pattern beats five overlapping ones.

**Why not TACO.** Investigated seriously and rejected:

- The headline "202.3 test cases per problem" applies only to the
  **1,000-problem test split**, not the 25,443-problem train split. Verified in
  the dataset card.
- 218 of 1,000 test problems (21.8%) need a Special Judge — non-deterministic
  output, case-insensitive comparison, or float tolerance.
- Their harness compensates with a cascade of ~8 fallback comparisons, ending in
  unordered set comparison, which accepts answers printed in the wrong order.
- It is mostly stdin/stdout competitive programming, not LeetCode-shaped, and has
  no curriculum ordering.

Since the extension decision removed the need for test cases entirely, TACO's one
advantage — bundled tests — no longer applies.

**Cost.** Pinned to a community-maintained file. Pattern coverage stops at 450
problems, so anything outside that set has no pattern label.

---

## Never let an LLM assert an expected output

Code execution and test authoring are out of scope entirely. If they ever come
back, the rule is: an LLM may propose test _inputs_, never expected _outputs_.

**Context.** The web-app plan needed test cases, and generating them with Claude
was the obvious shortcut.

**Why the rule.** A missing test lets a sloppy solution pass. A **wrong** test
tells a correct user they are wrong — and the agent, which believes the test,
will then coach them into breaking working code. That is unrecoverable for trust,
and it is strictly worse than having no tests at all.

The fix is not better prompting. It is never asking the model for a fact it can
get wrong:

```
LLM proposes inputs  →  run a reference solution  →  that IS the expected output
```

The model asks questions; a known-good implementation answers them. Supporting
techniques if this is ever revisited: cross-validate across independently written
implementations, use a brute-force oracle on small random inputs, assert
properties rather than exact strings, and run mutation testing to check the suite
is strict enough to catch a deliberately broken solution.

**Per-problem comparators, not a global cascade.** TACO's harness tries eight
increasingly lenient comparisons until one passes, which is exactly how a strict
test becomes a permissive one. The right shape is one comparator declared per
problem — `exact`, `trimmed`, `float_eps`, `unordered`, `any_valid` — chosen
deliberately when the problem is authored.

**Status.** Moot under the extension architecture, since LeetCode's judge is the
oracle. Recorded because the reasoning survives the architecture that prompted it.

---

## Vite + React + TypeScript, UI in the side panel

The extension is a Vite project with React and TypeScript. The UI renders in
Chrome's side panel, not the toolbar popup.

**Side panel over popup.** A popup closes the moment you click away, which makes
it unusable for a chat you refer to while typing code. The side panel docks
beside the tab and stays open. Login becomes a gate inside it: signed out shows
the form, signed in shows the app.

**Vite over staying buildless.** The extraction spike is plain JS with no build
step, which was right for a spike. `@supabase/supabase-js` is an npm package and
needs bundling, so a build step arrives regardless. Doing it now means one
migration instead of two, and the login form JSX drops in from `frontend/` nearly
unchanged.

**Two Vite configs, not one.** Content scripts cannot be ES modules; panel pages
and MV3 service workers can. So:

| Config | Entries | Format |
| --- | --- | --- |
| `vite.config.ts` | panel HTML, service worker | ESM |
| `vite.content.config.ts` | content script | IIFE |

Filename hashing is disabled on all entries so `manifest.json` can reference
stable paths.

Not using `@crxjs/vite-plugin` — two small configs are less machinery than a
plugin whose maintenance has been intermittent.

**Tailwind deferred.** Not worth wiring into the extension build yet. The login
form's classes become one `panel.css` with the same visual result; revisit when
the chat UI gives it enough surface to justify.

**MV3 constraints worth remembering.**

- The service worker is killed when idle. Nothing survives in memory — state
  belongs in `chrome.storage` or Supabase.
- No remote code. Everything bundles, which is why the Anthropic key cannot ship
  in the extension.
- Content scripts run in an isolated world and cannot see page JavaScript.
  Reading the Monaco editor needs `world: "MAIN"`, because Monaco virtualizes and
  the DOM holds only the lines currently scrolled into view.
- Nothing may use `unload` or `beforeunload`; Chrome is deprecating them.
- Property overrides made in a content script are invisible to the page, but DOM
  _events_ reach every world. So SPA navigation is detected with the Navigation
  API's `currententrychange` event plus a slow poll — not by wrapping
  `history.pushState` (see the second spike bug above).

---

## Open and deferred

Decisions not yet made, and things deliberately postponed.

| Item | State |
| --- | --- |
| `pgvector` for similarity | Deferred. Pattern map first; upgrade when category matching proves too coarse |
| Git repo | The root has none yet. Worth initialising before anything is pushed anywhere |
| OAuth sign-in | Deferred. Needs `chrome.identity.launchWebAuthFlow` round-tripping through `chromiumapp.org` |
| Email confirmation | Off locally. Turning it on in production needs a hosted page, since confirmation links open in a browser tab, not the extension |
| Local host permissions | `http://127.0.0.1:54321/*` and `http://127.0.0.1:8000/*` are needed for dev and **must be replaced with the hosted URLs before shipping** |
| Streaming replies | Next after the chat loop is proven end to end. SSE from FastAPI, `ReadableStream` in the panel |
| Persisting sessions and messages | Needed for "you solved this pattern last week." First real migration |
| Quota and rate limit | Per-user daily hint count from a usage log; in-memory bucket per user |

**Scope guard.** The failure mode for this project is building forever and
shipping nothing. V1 is: panel opens on a problem, reads the statement and code,
gives graduated hints, remembers what you attempted, and says "you solved a Two
Pointers problem last week." No dashboard, no execution, no analytics.
