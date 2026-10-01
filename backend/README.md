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
| `POST /chat` | bearer | transcript + problem + code in, Claude's reply out |
| `POST /solutions` | bearer | an accepted submission in; stores the code and a short model-written summary, once per submission |

Interactive docs at `http://127.0.0.1:8000/docs`.

## Saved solutions

`POST /solutions` writes to the `solutions` table through Supabase's REST API
(`app/db.py`), using the caller's own access token — so row-level security
decides what it can touch and the backend holds no service-role key. It needs
`SUPABASE_ANON_KEY` in `.env` (the public key the extension also uses) and the
table from `supabase/migrations/` (`npm run db:migrate` at the repo root).

A submission that is already saved is returned as-is with no model call.
Summaries always run at effort `low`, whatever `LLM_EFFORT` is.

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
```

`run` replays the canned requests in `benchmarks/cases.json` directly against
the configured provider — no HTTP, no auth — so two configurations can be
compared on identical input: change `LLM_PROVIDER` / `LLM_EFFORT` / the model
in `.env`, run again, regenerate the report. Rows are tagged `bench` vs
`panel` so real usage and replays stay separate in the summary.

Cost estimates come from `app/prices.py`, a hand-maintained table — check the
date at the top of it against the vendor's pricing page before quoting a
number.
