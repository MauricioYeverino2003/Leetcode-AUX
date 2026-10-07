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

On every `/chat`, the backend looks for the user's saved solutions whose
LeetCode topic tags overlap the current problem's (`app/recall.py`), ignoring
tags that nearly every problem carries, and puts up to three of their
summaries — never their code — after the problem statement in the prompt. The
response lists them in `prior_solutions`, and the panel shows them under the
reply. If the lookup fails, the chat goes ahead without it.

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
