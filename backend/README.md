# backend

The tutoring agent behind the extension. FastAPI, one route that matters.

## Run

```
uv sync                                   # first time: creates .venv, installs
uv run uvicorn app.main:app --reload      # http://127.0.0.1:8000
```

Needs `.env` (see `.env.example`) and the local Supabase stack running
(`npm run db:start` at the repo root), since it verifies Supabase tokens.

## Switching the model vendor

`LLM_PROVIDER=anthropic` or `LLM_PROVIDER=openai` in `.env`, then restart.
Nothing else changes — not the extension, not the `/chat` contract, not the
tutor's behaviour, which lives in `app/prompt.py` and is shared by both.

| | `app/providers/claude.py` | `app/providers/gpt.py` |
| --- | --- | --- |
| API | Messages (beta, for refusal fallback) | Responses |
| Prompt caching | explicit breakpoint after the problem statement | automatic on matching prefixes |
| Refusal | server-side fallback to another model | reported as a refusal part; user sees a fixed message |
| Key | `ANTHROPIC_API_KEY` | `OPENAI_API_KEY` |

`GET /health` reports which provider and model are active.

## Routes

| Route | Auth | Does |
| --- | --- | --- |
| `GET /health` | no | liveness + which model is configured |
| `GET /me` | bearer | echoes the verified user — test auth without a Claude call |
| `POST /chat` | bearer | transcript + problem + code in, the tutor's reply out — with the user's related saved solutions recalled into the prompt |
| `POST /solutions` | bearer | an accepted submission in; stores the code and a short model-written summary, once per submission |
| `GET /solutions/slugs` | bearer | the problems the user already has solutions for — the extension's import skips them |
| `POST /solutions/embed` | bearer | indexes up to 50 of the user's solutions that have no embedding yet; the panel calls it until none remain |

Interactive docs at `http://127.0.0.1:8000/docs`.

## Saved solutions

`POST /solutions` writes to the `solutions` table through Supabase's REST API
(`app/db.py`), using the caller's own access token — so row-level security
decides what it can touch and the backend holds no service-role key. It needs
`SUPABASE_ANON_KEY` in `.env` (the public key the extension also uses) and the
table from `supabase/migrations/` (`npm run db:migrate` at the repo root).

A submission that is already saved is returned as-is with no model call. So is
one whose code is identical to a solution already saved for the same problem
— resubmitting the same code gets a new id from LeetCode but is not stored
twice. Summaries always run at effort `low`, whatever `LLM_EFFORT` is, and on
`SUMMARY_MODEL` if set (a smaller model of the same vendor; an import makes
one summary per solved problem).

Past accepted submissions arrive the same way: the extension's **Import**
button has the content script page through the user's submission list on
LeetCode (one request a second, latest accepted per problem, skipping the
slugs from `GET /solutions/slugs`), fetch each one's code, and queue it
exactly as a live accepted submission is queued. The backend sees ordinary
`POST /solutions` calls and never touches LeetCode.

## Recall

On every `/chat`, the backend finds the user's saved solutions most similar
to the current problem and puts up to three of their summaries — never their
code — after the problem statement in the prompt (`app/recall.py`).

Similarity is by meaning: every saved solution is embedded (title, tags,
summary, and the statement when the row has one) with `EMBEDDING_MODEL` into
a `pgvector` column, the current problem is embedded the same way, and the
`match_solutions` SQL function returns the nearest rows by cosine similarity
— inside row-level security, so only the caller's rows are searched. Shared
topic tags add a small bonus; rows below a minimum similarity are dropped;
the same problem, if solved before, always comes first. If embeddings are
unavailable (no OpenAI key, endpoint down), recall falls back to topic-tag
overlap; the log line says which (`recall=embedding|tags`).

Rows are embedded when saved. Rows saved before this existed, or saved while
embedding was failing, are indexed by `POST /solutions/embed`, which the
panel calls after each save pass until nothing remains. The response lists
the recalled problems in `prior_solutions` with their similarity, and the
panel shows them under the reply.

## Try it by hand

```
TOKEN=<a user's access token>
curl -s http://127.0.0.1:8000/me -H "Authorization: Bearer $TOKEN"

curl -s http://127.0.0.1:8000/chat \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Where do I start?"}],
       "problem":{"slug":"two-sum","title":"Two Sum","difficulty":"Easy",
                  "statement":"Given an array of integers nums and an integer target..."}}'
```

Every chat logs one line with the user id, token usage, timing and estimated
cost — the seed of the usage log that quotas will be built on.

## Benchmarks

Every model call is also appended to `benchmarks/runs.jsonl` (gitignored — it
holds prompts and user code) with timing, tokens, reasoning tokens, estimated
cost, the exact prompt and the reply. Turn `BENCHMARKS_PATH=` empty in `.env`
to disable.

```
uv run python -m app.benchmarks report            # -> docs/benchmarks.md
uv run python -m app.benchmarks run               # estimate only
uv run python -m app.benchmarks run --yes         # replay benchmarks/cases.json
uv run python -m app.benchmarks run --yes --repeat 3
uv run python -m app.benchmarks run --yes --case help-empty-stub --case off-topic
```

`run` replays the canned requests in `benchmarks/cases.json` directly against
the configured provider — no HTTP, no auth — so two configurations can be
compared on identical input: change `LLM_PROVIDER` / `LLM_EFFORT` / the model
in `.env`, or the prompt, run again, regenerate the report. Rows are tagged
`bench` vs `panel` so real usage and replays stay separate in the summary.

Each case is one frozen moment of a chat — problem, editor code, transcript so
far — plus an `expect` line saying what a good reply does, and optionally a
`prior` list standing in for the saved solutions recall would have found.
Nothing grades a reply against `expect`; the report's **Replay cases** section
prints it above the replies, one per prompt version, and the judging is done
by reading. `PROMPT_VERSION` in `app/prompt.py` is bumped on every wording
change and recorded with each call, which is what makes versions comparable.
Most cases come from real chats that went wrong, so a later change can't
quietly bring the failure back.

Cost estimates come from `app/prices.py`, a hand-maintained table — check the
date at the top of it against the vendor's pricing page before quoting a
number.

## Recall evaluation

How often recall finds what it should, measured over the developer's own
solved problems, against three label sets: LeetCode's curated Similar
Questions (external, mixes same-technique with same-series), and two levels
of labels assigned to each saved solution by a cheap model reading its
summary — a coarse *pattern* (one of 19) and a specific *technique* (one of
about 70 under those patterns, the fixed list in `app/recall_eval.py`).
"Same technique" is the definition of *solved similarly*: the technique used
for one would be the right first hint for the other. The model answers with
the entry's number, not its wording. Each command prompts for the Supabase
email and password so every query runs under row-level security, exactly as
the panel's do.

```
uv run python -m app.recall_eval fetch        # LeetCode's data on every solved problem -> benchmarks/problems.json (cached, gitignored)
uv run python -m app.recall_eval label --yes  # a pattern + technique per solution on SUMMARY_MODEL -> benchmarks/techniques.json
uv run python -m app.recall_eval check        # 20 LeetCode-similar pairs to judge by hand -> benchmarks/recall-handcheck.json
uv run python -m app.recall_eval hyde --yes   # three plausible approaches per problem, embedded -> benchmarks/problems-hyde.json
uv run python -m app.recall_eval run          # hit@k, recall@k, MRR for every method -> docs/recall-eval.md
```

`hyde` is the query-side experiment: instead of embedding the problem's
statement (which says what is asked, not how it is solved), the summary
model writes three plausible approaches in the saved summaries' style and
those are embedded. `run` then scores `hyde` (best match against any
approach) and `hyde + statement` beside the plain-statement method, on the
same queries and labels, and says what each fixes or breaks relative to it.

`hyde` also labels each generated approach with the taxonomy, which gives
a fourth answer key, *your technique works for it*: a saved solution counts
for a query when the technique the user used for it is one of the query's
workable techniques (its approaches' labels plus the user's own). It is
looser than *same technique* — it credits a solution whose approach is *a*
way into the problem, not only *the* way the user took — and the closest of
the four to what the tutor needs.

For each solved problem with a statement and at least one relative,
retrieval runs with the query's own row excluded, by tags and by embeddings,
on the same rows with the production floor, and the top k is scored at
k = 1, 3, 5. The report also lists every miss at k = 3 with what was
returned instead, for reading.
