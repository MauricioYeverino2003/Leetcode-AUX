# Future work

A working list of what could make LeetCode AUX better, cheaper or ready for
other people, with the evidence behind each item and how it would be judged.
Companion to `design-choices.md`, which records what was decided; this
records what hasn't been.

_Last updated: 2026-10-08_

## Where to start, in order

1. **Teach the tutor to use a recalled problem properly** (§1). The failure
   is in the log, the fix is prompt wording plus two replay cases, and it
   costs a few cents to verify.
2. **Run the effort experiment** (§4). Reasoning is 80–90% of every reply's
   cost and most of the wait; the replay set exists to judge `low`.
3. **Build a recall test set, then HyDE** (§2). Recall by meaning works for
   topic; the parentheses family shows why approach needs its own signal.
4. **Trial an open-weight host** (§3), judged on the same replay set.

Everything in §8 is a gate before anyone else gets an account.

---

## 1. The tutor names a recalled problem and stops

**Evidence.** On *32. Longest Valid Parentheses* (2026-10-08), with three
parentheses problems recalled, the reply opened:

> You've solved related ones like Valid Parentheses and Minimum Add to Make
> Parentheses Valid. This is a substring search in a parentheses string…

and went on to the hint. Nothing about what those problems asked or how
they were solved. A user who doesn't remember them gets nothing from the
mention; a user who does gets no bridge to this problem.

**The behaviour wanted.** A short protocol instead of a name-drop:

1. Name the related problem and ask whether they remember it.
2. If not: one sentence on what it asked.
3. Ask whether they remember how they solved it.
4. If not: the approach at the level the ladder is at — from the saved
   summary, never the code.
5. Then what carries over to this problem, in one sentence.

Each step is one turn; the ladder's "one level per reply" still applies.

**What it needs.**

- Prompt wording for the protocol, in the recall paragraph of
  `SYSTEM_PROMPT` (`backend/app/prompt.py`).
- Summaries that say what the problem asked. The summary prompt now opens
  with that sentence; the 171 imported summaries predate it. Either
  re-summarise them (~$0.17 on `gpt-5-mini`) or fetch their statements
  (§6) and let the tutor read those.
- Replay cases: a user who says "I don't remember that one" after a
  mention; a user who asks "is my approach similar to X?" (asked on 301 and
  not handled well: the tutor said no logic had been shared).

**Judged by** reading the replies to those cases, as with every prompt
change (`backend/benchmarks/cases.json`, `docs/benchmarks.md`).

**Reading before rewriting.** Two primary sources are worth an hour: OpenAI's
prompting guidance for reasoning models (platform.openai.com/docs/guides/
prompt-engineering) and Anthropic's prompt-engineering overview
(docs.claude.com). The techniques most likely to pay here: a few short
*contrasting* examples (a good level-0 hint next to a bad one that leaks the
technique), explicit output constraints (which the prompt already has), and
putting the recall protocol in the same imperative style as the rest.
Long explanations of *why* tend to hurt; the replay runs on versions 1–4
showed vagueness, not brevity, was the problem.

## 2. Recall by approach, not just topic — HyDE

**The gap.** Problems similar in wording are often different in approach.
The parentheses family is the proof: Valid Parentheses is a stack, Minimum
Add is greedy counting, Valid Parenthesis String is greedy bounds or DP,
Generate Parentheses is backtracking, Remove Invalid Parentheses is BFS over
strings, Longest Valid Parentheses is a stack of indices or DP. Recall by
meaning currently matches the *problem text* against *solution summaries*,
so topic words dominate: on 301 it recalled three parentheses problems, none
of which shares 301's BFS idea.

**The idea.** When a problem is opened, a cheap model writes two or three
plausible approaches in the saved summaries' style; each is embedded; a
saved solution scores by its best similarity against any of them —
approach text against approach text. Cached per problem in a shared
`problems` table (slug, statement, approaches, their embeddings): they
describe the problem, not the user, so each problem is paid for once across
all users. Never shown to the user or the tutor.

**A cheaper half-step to try first.** Two vectors per saved row — one of
the statement (topic) and one of the summary (approach) — and a combined
score. No extra model call; needs statements for imported rows (§6).

**Tested 2026-10-14, not shipped.** On the strict same-technique key HyDE
reached hit@3 69% against 65%; on the fairer "your technique works for it"
key (a saved solution counts when its technique is one of the query's
workable techniques) it reached 80–81% against 78%, with 10 fixes and 5–7
breaks of 168. A two-to-four-point edge, not enough to pay a model call and
several seconds per newly opened problem. The command stays in the
harness. The fairer key also showed today's recall is better than the
strict one suggested: 78% is the honest number. The next lever for recall
quality is the document side — statements on the imported rows, and
summaries that state their technique — judged on the same baselines; and
several remaining "misses" are label granularity rather than retrieval.

**Cost.** HyDE: one small-model call per *new* problem (~$0.001 on
`gpt-5-mini`), nothing for problems already cached; 2–3 embedding calls
per new problem, negligible.

## 3. Cheaper inference: open-weight models on a host

**The numbers**, verified 2026-10-08 on deepinfra.com, USD per million
tokens, against what the backend uses today:

| | Input | Output | Notes |
| --- | --- | --- | --- |
| `gpt-5` (chat today) | 1.25 | 10.00 | reasoning tokens billed as output |
| `gpt-5-mini` (summaries today) | 0.25 | 2.00 | |
| DeepSeek V3.2 | 0.26 | 0.38 | cached input 0.13 |
| Qwen3 235B | 0.09 | 0.55 | |
| Llama 3.3 70B | 0.10 | 0.32 | |
| `text-embedding-3-large` (today) | 0.13 | — | 3,072 dims |
| EmbeddingGemma-300m | 0.002 | — | 768 dims, 2,048-token input |
| bge-m3 | 0.01 | — | |

For chat the gap is 10–25× on output, which is where the money is. For
embeddings it is 65×, on a cost that is already negligible — so the
embedding switch is about principle, the chat switch is about money.

**What it would take.** Less than it sounds. The OpenAI provider speaks the
Responses/Chat API; DeepInfra and most hosts expose an OpenAI-compatible
endpoint, so a `base_url` setting on the existing provider (or a thin third
provider) is the whole plumbing — the design that made two vendors
interchangeable pays off here. Embeddings need a new column or migration
because the dimension count changes (768 vs 3,072), then a re-embed, which
is cents.

**What would be given up or has to be checked.**

- *Quality.* Hints at the right level are the product. The replay set is
  the test: run the 17 cases on DeepSeek V3.2 and Qwen3 and read them next
  to `gpt-5`'s. A model that leaks the technique on "help" is not cheaper,
  it is worse.
- *The free daily tokens.* OpenAI's data-sharing allowance has covered most
  usage so far. Paid open-weight inference competes with free, not with
  list price, until usage outgrows the allowance.
- *Data policy.* The privacy notice names OpenAI and its training terms.
  A new host means reading its terms and changing the notice; DeepInfra's
  pricing page says nothing about data use, so that has to be found.
- *Latency.* Unknown until measured; the benchmark log records it.

**Judged by** the replay set for quality, the benchmark report for latency
and cost, and the recall test set for embeddings.

## 4. Effort tuning

Pending since the benchmarks were built. `LLM_EFFORT=low` in `.env`, replay
the 17 cases, read whether hints hold up. The code-heavy cases spend 1,200–
2,600 reasoning tokens and 10–30 seconds at the default; this is the single
change most likely to halve both. If `low` hurts only some categories, that
is the evidence for §5.

## 5. Intent classifier and per-category effort

A small model labels each message (hint, approach check, debug, explain,
off-topic…), the backend assembles a category-specific prompt and effort,
and the label is logged and shown. Deferred until the replays show the
single prompt routing wrong — after version 4 they don't — or until §4
shows that one effort level can't serve every category. The categories and
cases already exist; the classifier would reuse them.

## 6. Data the tutor doesn't have yet

- **Statements for imported rows.** 171 rows have no statement. An "enrich"
  pass in the content script (one GraphQL `questionContent` per slug, a
  second apart, ~3 minutes) would fill them; then re-embed. Needed by the
  two-vector variant in §2 and useful for §1.
- **Re-summarise imported rows** with the prompt that restates the problem.
  ~$0.17.
- **Runtime and memory** from `submissionDetails` — free to store; lets the
  tutor say "your solution was in the slowest 20%" when asked about speed.
- **Several languages per problem.** The import keeps one row per problem;
  a C++ and a Python solution to the same problem would be worth both.
- **Failed attempts.** Only accepted submissions are saved. Wrong answers
  before the accepted one would let the tutor say what a user tends to get
  wrong; also the most sensitive data to hold.

## 7. Evaluation that doesn't depend on reading everything

- **A recall test set** — done 2026-10-13 (`app/recall_eval.py`,
  `docs/recall-eval.md`): LeetCode's Similar Questions and per-solution
  technique labels as two label sets, hit@k / recall@k / MRR for tags vs
  embeddings. Round 2 (same day) added two-level labels — a pattern and
  one of 72 specific techniques, chosen by number — and the DP problems
  that had come back unknown. The hand check (16 of 20 answered) put 81%
  of LeetCode-similar pairs as genuinely solved alike and found the labels
  agreeing with the human 15 of 16 times. A fourth key, "your technique
  works for it", built from labeled HyDE approaches, is now the primary
  metric: embeddings 78% hit@3 vs tags 64%.
- **Thumbs up / down on replies** in the panel, written to the benchmark
  log: the cheapest way to grow the case set from real use.
- **An LLM judge**, only once the rubric per case is stable enough to
  trust a model with it, and always spot-checked by reading.

## 8. Before anyone else gets an account

Each of these is a gate, not a feature.

- **Consent**: accept at sign-up, a one-time screen for existing accounts, a
  settings tab with revoke and delete, enforced in the backend.
- **Quota and rate limit** per user: the only cost control today is the
  schema's size caps and the spend cap on the key.
- **Hosting**: Supabase cloud, the backend on a host, host permissions in
  the manifest switched from `127.0.0.1` to real URLs.
- **Chrome Web Store**: privacy policy page, data-use disclosure, a store
  listing.
- **Streaming replies**: the 5–10 second wait is the most visible flaw for a
  new user.

## 9. Smaller things worth doing when nearby

- Record summary and embedding calls in the benchmark log, so their cost is
  measurable rather than estimated.
- Show "Indexing N solutions…" in the panel during a backfill.
- A list of saved solutions in the panel, with the summary, for the user's
  own review.
- The NeetCode pattern map as a curated label on each saved row — a third
  signal for recall and a way to say "that's a two-pointers problem" in the
  tutor's own words.
- Persist chats per problem, so returning to a problem resumes the thread.
