"""
Recall evaluation: how often does recall find what it should?

    uv run python -m app.recall_eval fetch         # LeetCode's data on every solved problem -> benchmarks/problems.json
    uv run python -m app.recall_eval label --yes   # a pattern + technique per saved solution -> benchmarks/techniques.json
    uv run python -m app.recall_eval check         # 20 pairs for a hand check               -> benchmarks/recall-handcheck.json
    uv run python -m app.recall_eval hyde --yes    # three written approaches per problem     -> benchmarks/problems-hyde.json
    uv run python -m app.recall_eval run           # score every method                       -> docs/recall-eval.md

HyDE (hypothetical document embeddings) is the experiment on the query side:
instead of embedding the problem statement — which says what is asked, not
how it is solved — a cheap model writes what the solution summaries for this
problem would look like, and those are embedded. Scored beside the plain
statement query; ships to production only if the same-technique number moves.

"Should" is defined three ways, and all are scored:

  LeetCode similar — LeetCode's own curated "Similar Questions" list, in either
                     direction, restricted to problems the user has solved. An
                     external baseline; it mixes same-technique with same-series.
  same pattern     — the saved solutions share a coarse pattern (one of 19,
                     NeetCode's). Big buckets; a hit here says little.
  same technique   — the saved solutions share a specific technique (one of
                     ~65 under those patterns). This is "solved similarly":
                     the technique used for one is the right first hint for
                     the other. The definition lives in TAXONOMY below.

Labels come from a cheap model reading each solution's summary and answering
with the NUMBER of a taxonomy entry — numbers, because the first version
matched on the label's exact wording and silently lost every dynamic-
programming problem to "unknown".

For each solved problem with a statement and at least one relative, retrieval
runs over the user's own rows with the query's own row excluded — by tags and
by embeddings, same rows, same k, production threshold — and the top k is
scored with hit@k, recall@k and MRR for k = 1, 3, 5.

Everything that talks to the database goes through the user's own token (the
developer signs in at the prompt), so row-level security applies exactly as in
the panel. Everything that talks to LeetCode is the public question query, one
request a second, cached so it runs once.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import random
import re
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

import httpx2

from . import db, embeddings, recall
from .config import BACKEND_DIR, settings
from .schemas import ProblemContext

BENCH = BACKEND_DIR / "benchmarks"
PROBLEMS_FILE = BENCH / "problems.json"  # gitignored: LeetCode's text
QUERY_EMBEDDINGS_FILE = BENCH / "problems-embeddings.json"  # gitignored: large
TECHNIQUES_FILE = BENCH / "techniques.json"  # committed: slug -> {pattern, technique}
HANDCHECK_FILE = BENCH / "recall-handcheck.json"  # committed once filled in
HYDE_FILE = BENCH / "problems-hyde.json"  # gitignored: model text about LeetCode problems, large
REPORT_FILE = BACKEND_DIR.parent / "docs" / "recall-eval.md"

LEETCODE_GRAPHQL = "https://leetcode.com/graphql"
LEETCODE_PACE_S = 1.0

KS = (1, 3, 5)

# The definition of "solved similarly", as a fixed list: (pattern, technique,
# one-line gloss). Patterns are NeetCode's, lightly adapted; techniques are the
# specific idea that carries a solution. Two saved solutions are solved
# similarly when they share the technique. Hand-written, so it is versioned.
TAXONOMY: list[tuple[str, str, str]] = [
    ("arrays & hashing", "hash map of complements", "look up target minus x as you scan"),
    ("arrays & hashing", "counting / frequency map", "count occurrences, then compare or pick"),
    ("arrays & hashing", "prefix sums", "running totals, often with a map of seen sums"),
    ("arrays & hashing", "sort then scan", "sort first, then one pass"),
    ("arrays & hashing", "set membership", "a set of seen values"),
    ("arrays & hashing", "matrix traversal", "walk rows, columns or boxes of a grid"),
    ("arrays & hashing", "value as index or bucket", "use the value itself as an index or bucket"),
    ("two pointers", "opposite ends", "pointers from both ends moving inward"),
    ("two pointers", "fast and slow", "two pointers at different speeds"),
    ("two pointers", "in-place partition", "read and write pointers over one array"),
    ("sliding window", "fixed size", "a window of constant length"),
    ("sliding window", "variable size with counts", "grow and shrink a window tracked by a count map"),
    ("stack", "bracket matching", "push opens, pop on closes"),
    ("stack", "monotonic stack", "a stack kept increasing or decreasing"),
    ("stack", "expression evaluation", "evaluate tokens with a stack"),
    ("stack", "stack simulation", "a stack as the problem's own structure"),
    ("binary search", "on a sorted array", "bisection over values"),
    ("binary search", "on the answer space", "bisect a numeric answer, test feasibility"),
    ("binary search", "on a rotated array", "bisection around a pivot"),
    ("linked list", "reversal", "reverse pointers in place"),
    ("linked list", "fast and slow pointers", "cycle, middle, k-th from the end"),
    ("linked list", "merge", "merge sorted lists"),
    ("linked list", "dummy-head splicing", "rewire nodes behind a dummy head"),
    ("linked list", "copy with a map", "map old nodes to new nodes"),
    ("trees", "DFS recursion", "recursive traversal returning values"),
    ("trees", "BFS level order", "a queue, level by level"),
    ("trees", "BST property", "use the ordering to prune or locate"),
    ("trees", "build from traversals", "construct a tree from traversal orders"),
    ("trees", "tree DP (postorder returns)", "each node returns a value combined from its children"),
    ("trees", "lowest common ancestor", "find where two paths meet"),
    ("tries", "prefix trie", "a character trie for prefix queries"),
    ("heap", "top-k", "keep the k best in a heap"),
    ("heap", "k-way merge", "merge k sorted streams"),
    ("heap", "two heaps", "balanced heaps, e.g. for a running median"),
    ("heap", "scheduling with a heap", "repeatedly take the best available item"),
    ("backtracking", "subsets and combinations", "choose or skip each element"),
    ("backtracking", "permutations", "arrange with used flags"),
    ("backtracking", "grid DFS with marking", "explore a grid, mark visited, unmark on return"),
    ("backtracking", "constraint search", "place with checks, undo on failure"),
    ("graph traversal", "BFS shortest steps", "unweighted shortest path in a graph"),
    ("graph traversal", "BFS over states", "nodes are states, edges are moves"),
    ("graph traversal", "DFS components / flood fill", "mark everything reachable"),
    ("graph traversal", "cycle detection", "visited colors or sets to find a cycle"),
    ("graph traversal", "topological sort", "Kahn's algorithm or DFS ordering"),
    ("graph traversal", "union-find", "disjoint sets with union and find"),
    ("graph traversal", "build adjacency and walk", "build a graph, then a plain traversal"),
    ("advanced graphs", "Dijkstra", "weighted shortest path with a heap"),
    ("advanced graphs", "minimum spanning tree", "Kruskal or Prim"),
    ("advanced graphs", "Bellman-Ford", "relax all edges repeatedly"),
    ("1-D dynamic programming", "take-or-skip", "dp[i] from earlier states with a take/skip choice"),
    ("1-D dynamic programming", "Fibonacci-style", "dp[i] = dp[i-1] + dp[i-2]"),
    ("1-D dynamic programming", "1-D knapsack", "ways or min cost to reach an amount"),
    ("1-D dynamic programming", "longest subsequence", "dp over prefixes, O(n^2) or patience"),
    ("1-D dynamic programming", "Kadane", "best subarray ending here"),
    ("1-D dynamic programming", "string segmentation", "dp[i]: can the prefix of length i be split"),
    ("2-D dynamic programming", "grid paths", "dp[r][c] from neighboring cells"),
    ("2-D dynamic programming", "edit distance / LCS", "dp over two sequences"),
    ("2-D dynamic programming", "interval DP", "dp[i][j] over substrings or ranges"),
    ("2-D dynamic programming", "game DP", "optimal play over a range"),
    ("greedy", "interval scheduling", "sort by end, take greedily"),
    ("greedy", "one-pass local optimum", "track the best so far in one pass"),
    ("greedy", "counting balance", "a running balance, fixed when it goes negative"),
    ("greedy", "furthest reach", "the furthest index reachable so far"),
    ("intervals", "sort and merge", "sort by start, merge overlaps"),
    ("intervals", "sweep line", "events in order with a running count"),
    ("math & geometry", "matrix rotation / spiral", "index arithmetic on a grid"),
    ("math & geometry", "digits and number theory", "digits, gcd, modular arithmetic"),
    ("math & geometry", "arithmetic simulation", "carry, big numbers, step-by-step arithmetic"),
    ("bit manipulation", "XOR trick", "XOR cancels pairs"),
    ("bit manipulation", "bit counting", "count or shift bits"),
    ("simulation", "follow the rules", "do what the statement says, step by step"),
    ("simulation", "design a data structure", "a class with operations over maps, lists or queues"),
]

PATTERNS = list(dict.fromkeys(p for p, _, _ in TAXONOMY))

LABEL_PROMPT = (
    "You classify how a LeetCode solution was solved. Below is a numbered list of techniques. "
    "Read the solution's summary and reply with the NUMBER of the single best match, and nothing else. "
    "Pick the technique the solution actually uses, as the summary describes it — not what the problem "
    "is usually solved with. If several apply, pick the one that carries the solution.\n\n"
    + "\n".join(f"{i}. {p} / {t} — {g}" for i, (p, t, g) in enumerate(TAXONOMY, 1))
)

QUESTION_QUERY = """
query question($slug: String!) {
  question(titleSlug: $slug) {
    questionFrontendId
    title
    difficulty
    isPaidOnly
    topicTags { name }
    similarQuestions
    content
  }
}
"""


# --- files -------------------------------------------------------------------


def _load(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _save(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# --- auth --------------------------------------------------------------------


async def sign_in(token: str | None) -> str:
    """The developer's own access token: given, or from an email + password
    sign-in against the project's auth endpoint. Row-level security then
    applies to every query exactly as it does for the panel."""
    if token:
        return token
    if not settings.supabase_anon_key:
        sys.exit("SUPABASE_ANON_KEY is not set; the evaluation needs it to sign in.")

    email = input("Supabase email: ").strip()
    password = getpass.getpass("Supabase password: ")
    async with httpx2.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            settings.supabase_url.rstrip("/") + "/auth/v1/token",
            params={"grant_type": "password"},
            headers={"apikey": settings.supabase_anon_key, "Content-Type": "application/json"},
            json={"email": email, "password": password},
        )
    if response.is_error:
        sys.exit(f"Sign-in failed: {response.status_code} {response.text[:200]}")
    return response.json()["access_token"]


# --- fetch: LeetCode's data on every solved problem ----------------------------


class _TextOnly(HTMLParser):
    """Statement HTML -> plain text. Block tags become line breaks; entities are
    decoded by the parser itself."""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in ("p", "br", "li", "pre", "div", "ul", "ol"):
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def html_to_text(html: str | None) -> str | None:
    if not html:
        return None
    parser = _TextOnly()
    parser.feed(html)
    text = "".join(parser.parts).replace("\xa0", " ")
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


async def fetch_question(client: httpx2.AsyncClient, slug: str) -> dict:
    response = await client.post(
        LEETCODE_GRAPHQL,
        json={"operationName": "question", "variables": {"slug": slug}, "query": QUESTION_QUERY},
        headers={"Content-Type": "application/json", "Referer": "https://leetcode.com/"},
    )
    response.raise_for_status()
    q = response.json()["data"]["question"]
    if q is None:
        raise ValueError(f"LeetCode has no question {slug!r}")
    similar = json.loads(q.get("similarQuestions") or "[]")
    return {
        "number": q["questionFrontendId"],
        "title": q["title"],
        "difficulty": q["difficulty"],
        "paid": bool(q["isPaidOnly"]),
        "tags": [t["name"] for t in q.get("topicTags") or []],
        "similar": [s["titleSlug"] for s in similar],
        "statement": html_to_text(q.get("content")),
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


async def fetch(token: str | None) -> None:
    token = await sign_in(token)
    slugs = await db.list_solution_slugs(token)
    problems = _load(PROBLEMS_FILE, {})
    todo = [s for s in slugs if s not in problems]
    print(f"{len(slugs)} solved problems, {len(problems)} already fetched, {len(todo)} to fetch "
          f"(about {len(todo) * LEETCODE_PACE_S:.0f}s at one request per second)")

    async with httpx2.AsyncClient(timeout=20.0) as client:
        for i, slug in enumerate(todo, 1):
            try:
                problems[slug] = await fetch_question(client, slug)
                note = "" if problems[slug]["statement"] else " (no statement — paid?)"
                print(f"  [{i}/{len(todo)}] {slug}: {len(problems[slug]['similar'])} similar{note}")
            except Exception as e:  # keep going; the slug is retried next run
                print(f"  [{i}/{len(todo)}] {slug}: failed — {e}")
            _save(PROBLEMS_FILE, problems)
            await asyncio.sleep(LEETCODE_PACE_S)

    print(f"{len(problems)} problems -> {PROBLEMS_FILE}")


# --- label: a pattern + technique per saved solution ---------------------------


def parse_choice(reply: str) -> tuple[str, str] | None:
    """The taxonomy entry the model chose, from a reply like "7", "7." or
    "Choice: 7". None if there is no usable number."""
    match = re.search(r"\d+", reply)
    if not match:
        return None
    n = int(match.group())
    if not 1 <= n <= len(TAXONOMY):
        return None
    pattern, technique, _ = TAXONOMY[n - 1]
    return pattern, technique


def labels_of(techniques: dict, slug: str) -> tuple[str | None, str | None]:
    """(pattern, technique) for a slug; (None, None) if unlabeled or in the
    old one-level shape."""
    entry = techniques.get(slug)
    if isinstance(entry, dict):
        return entry.get("pattern"), entry.get("technique")
    return None, None


async def label(token: str | None, yes: bool) -> None:
    from .providers import get_provider

    token = await sign_in(token)
    rows = await db.list_solutions(token)
    # One label per problem; the newest row's summary speaks for it.
    by_slug: dict[str, dict] = {}
    for row in rows:
        by_slug[row["problem_slug"]] = row

    techniques = _load(TECHNIQUES_FILE, {})
    todo = [s for s in by_slug if labels_of(techniques, s) == (None, None)]
    provider = get_provider()
    model = settings.summary_model or provider.model
    print(f"{len(by_slug)} problems, {len(by_slug) - len(todo)} labeled, {len(todo)} to label on {model} "
          f"— rough estimate ${len(todo) * 0.0004:.2f}")
    if not yes:
        print("Dry run. Re-run with --yes to spend it.")
        return

    for i, slug in enumerate(todo, 1):
        row = by_slug[slug]
        text = f"{row.get('problem_number') or ''}. {row.get('problem_title') or slug}\n\n{row['summary']}"
        choice = None
        for attempt in range(2):
            instructions = LABEL_PROMPT if attempt == 0 else LABEL_PROMPT + "\n\nReply with the number only."
            response = await provider.complete(
                instructions=instructions, text=text, effort="low", model=settings.summary_model
            )
            choice = parse_choice(response.reply)
            if choice:
                break
            print(f"  [{i}/{len(todo)}] {slug}: could not parse {response.reply.strip()[:60]!r}")
        if choice:
            techniques[slug] = {"pattern": choice[0], "technique": choice[1]}
            print(f"  [{i}/{len(todo)}] {slug}: {choice[0]} / {choice[1]}")
        else:
            techniques[slug] = {"pattern": None, "technique": None}
        _save(TECHNIQUES_FILE, techniques)

    _print_distribution(techniques)
    print(f"{len(techniques)} labels -> {TECHNIQUES_FILE}")


def _print_distribution(techniques: dict) -> None:
    patterns: dict[str, int] = {}
    fine: dict[str, int] = {}
    for slug in techniques:
        p, t = labels_of(techniques, slug)
        patterns[p or "unknown"] = patterns.get(p or "unknown", 0) + 1
        fine[t or "unknown"] = fine.get(t or "unknown", 0) + 1
    print("patterns:", ", ".join(f"{k} {n}" for k, n in sorted(patterns.items(), key=lambda x: -x[1])))
    print(f"techniques used: {len(fine)} of {len(TAXONOMY)}; largest: "
          + ", ".join(f"{k} {n}" for k, n in sorted(fine.items(), key=lambda x: -x[1])[:8]))


# --- hyde: approach-shaped queries ---------------------------------------------

HYDE_APPROACHES = 3

HYDE_PROMPT = (
    "Given this LeetCode problem, write the two or three most plausible efficient approaches a strong "
    "candidate would consider. Write each as its own paragraph of two to four plain sentences in the "
    "style of a solution summary: the approach or pattern, the key data structures, and the time and "
    "space complexity. Don't pick one or compare them. Separate the paragraphs with a blank line. "
    "No headers, no numbering, no code."
)


def split_approaches(reply: str, limit: int = HYDE_APPROACHES) -> list[str]:
    """The model's reply as separate approach texts. Paragraphs first; if it
    came back as one block with numbering or bullets, split on those."""
    blocks = [b.strip() for b in re.split(r"\n\s*\n", reply.strip()) if b.strip()]
    if len(blocks) < 2:
        blocks = [b.strip() for b in re.split(r"(?m)^\s*(?:\d+[.)]|[-*•])\s+", reply.strip()) if b.strip()]
    cleaned = [re.sub(r"^\s*(?:\d+[.)]|[-*•]|approach\s*\d*\s*[:.-])\s*", "", b, flags=re.I).strip() for b in blocks]
    return [c for c in cleaned if c][:limit]


async def hyde(token: str | None, yes: bool) -> None:
    from .providers import get_provider

    problems = _load(PROBLEMS_FILE, {})
    if not problems:
        sys.exit("Run `fetch` first.")
    token = await sign_in(token)
    solved = {r["problem_slug"] for r in await db.list_solutions(token)}
    usable = sorted(s for s in solved if problems.get(s, {}).get("statement"))

    cache = _load(HYDE_FILE, {})
    todo = [s for s in usable if s not in cache]
    provider = get_provider()
    model = settings.summary_model or provider.model
    print(f"{len(usable)} usable problems, {len(cache)} done, {len(todo)} to write approaches for on {model} "
          f"— rough estimate ${len(todo) * 0.0015:.2f} plus about a cent of embeddings")
    if not yes:
        print("Dry run. Re-run with --yes to spend it.")
        return

    for i, slug in enumerate(todo, 1):
        response = await provider.complete(
            instructions=HYDE_PROMPT,
            text=embeddings.problem_text(_context(slug, problems)),
            effort="low",
            model=settings.summary_model,
        )
        approaches = split_approaches(response.reply)
        if not approaches:
            print(f"  [{i}/{len(todo)}] {slug}: no usable approaches in reply — skipped")
            continue
        vectors = await embeddings.embed(approaches)
        cache[slug] = {
            "model": response.model,
            "approaches": approaches,
            "vectors": [[round(x, 6) for x in v] for v in vectors],
        }
        _save(HYDE_FILE, cache)
        print(f"  [{i}/{len(todo)}] {slug}: {len(approaches)} approach(es) — {approaches[0][:70]}…")

    print(f"{len(cache)} problems -> {HYDE_FILE}")


def merge_candidates(lists: list[list[dict]]) -> list[dict]:
    """Rows from several match_solutions calls, one per query vector, merged
    by row id with each row's similarity = its best across the vectors."""
    best: dict[str, dict] = {}
    for rows in lists:
        for row in rows:
            key = row.get("id") or row["problem_slug"]
            if key not in best or float(row.get("similarity") or 0) > float(best[key].get("similarity") or 0):
                best[key] = row
    return sorted(best.values(), key=lambda r: -float(r.get("similarity") or 0))


# --- relevance sets ------------------------------------------------------------


def leetcode_relevant(problems: dict, solved: set[str]) -> dict[str, set[str]]:
    """For each solved problem: LeetCode-similar problems the user also solved,
    in either direction (the list is not always symmetric), minus itself."""
    related: dict[str, set[str]] = {s: set() for s in solved}
    for slug, p in problems.items():
        if slug not in solved:
            continue
        for other in p.get("similar", []):
            if other in solved and other != slug:
                related[slug].add(other)
                related[other].add(slug)
    return related


def _group_relevant(techniques: dict, solved: set[str], level: int) -> dict[str, set[str]]:
    groups: dict[str, set[str]] = {}
    for slug in solved:
        key = labels_of(techniques, slug)[level]
        if key:
            groups.setdefault(key, set()).add(slug)
    return {slug: groups.get(labels_of(techniques, slug)[level] or "", set()) - {slug} for slug in solved}


def pattern_relevant(techniques: dict, solved: set[str]) -> dict[str, set[str]]:
    return _group_relevant(techniques, solved, 0)


def technique_relevant(techniques: dict, solved: set[str]) -> dict[str, set[str]]:
    return _group_relevant(techniques, solved, 1)


# --- metrics (pure) ------------------------------------------------------------


def hit_at(ranked: list[str], relevant: set[str], k: int) -> float:
    return 1.0 if any(s in relevant for s in ranked[:k]) else 0.0


def recall_at(ranked: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    return len(set(ranked[:k]) & relevant) / len(relevant)


def reciprocal_rank(ranked: list[str], relevant: set[str]) -> float:
    for i, s in enumerate(ranked, 1):
        if s in relevant:
            return 1.0 / i
    return 0.0


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


# --- check: pairs for a hand check ---------------------------------------------


def _excerpt(text: str | None, limit: int) -> str | None:
    """The start of a statement or summary, on one line, for reading in the
    hand-check file."""
    if not text:
        return None
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"


async def check(token: str | None, seed: int) -> None:
    """Twenty LeetCode-similar pairs for a human to judge by the definition of
    "solved similarly", with enough context to judge: each problem's title,
    labels, the start of its statement, and the start of the user's own
    summary of how they solved it."""
    problems = _load(PROBLEMS_FILE, {})
    techniques = _load(TECHNIQUES_FILE, {})
    if not problems:
        sys.exit("Run `fetch` first.")

    token = await sign_in(token)
    summaries = {row["problem_slug"]: row["summary"] for row in await db.list_solutions(token)}

    solved = set(problems)
    related = leetcode_relevant(problems, solved)
    pairs = sorted({tuple(sorted((a, b))) for a, bs in related.items() for b in bs})
    random.Random(seed).shuffle(pairs)

    # Answers already given survive a refresh.
    answers = {(e["a"], e["b"]): e.get("human") for e in _load(HANDCHECK_FILE, [])}
    entries = []
    for a, b in pairs[:20]:
        pa, ta = labels_of(techniques, a)
        pb, tb = labels_of(techniques, b)
        entries.append({
            "a": a,
            "a_title": problems[a]["title"],
            "a_labels": f"{pa} / {ta}",
            "a_statement": _excerpt(problems[a].get("statement"), 240),
            "a_how_you_solved_it": _excerpt(summaries.get(a), 320),
            "b": b,
            "b_title": problems[b]["title"],
            "b_labels": f"{pb} / {tb}",
            "b_statement": _excerpt(problems[b].get("statement"), 240),
            "b_how_you_solved_it": _excerpt(summaries.get(b), 320),
            "same_pattern": (pa == pb) if pa and pb else None,
            "same_technique": (ta == tb) if ta and tb else None,
            # Fill in: "yes" if the way you solved one would be the right first
            # hint for the other; "no" if the link is topic or series only.
            "human": answers.get((a, b)),
        })
    _save(HANDCHECK_FILE, entries)
    answered = sum(1 for e in entries if e["human"] in ("yes", "no"))
    print(f"{len(entries)} pairs ({answered} answered) -> {HANDCHECK_FILE}  "
          "(fill in each \"human\" with \"yes\" or \"no\")")


# --- run: score ----------------------------------------------------------------


async def run(token: str | None) -> None:
    problems = _load(PROBLEMS_FILE, {})
    techniques = _load(TECHNIQUES_FILE, {})
    if not problems:
        sys.exit("Run `fetch` first.")
    if not techniques:
        print("No techniques.json — the pattern and technique tiers will be skipped (run `label`).")

    token = await sign_in(token)
    rows = await db.list_solutions(token)
    solved = {r["problem_slug"] for r in rows}
    tiers = {"LeetCode similar": leetcode_relevant(problems, solved)}
    if techniques:
        tiers["same pattern"] = pattern_relevant(techniques, solved)
        tiers["same technique"] = technique_relevant(techniques, solved)

    query_vectors = _load(QUERY_EMBEDDINGS_FILE, {})
    queries = [s for s in solved if problems.get(s, {}).get("statement")]
    queries = [s for s in queries if any(tiers[t].get(s) for t in tiers)]
    to_embed = [s for s in queries if s not in query_vectors]
    print(f"{len(solved)} solved, {len(queries)} usable queries, {len(to_embed)} to embed "
          f"(about ${len(to_embed) * 0.00006:.3f})")

    for i in range(0, len(to_embed), 50):
        batch = to_embed[i : i + 50]
        vectors = await embeddings.embed([embeddings.problem_text(_context(s, problems)) for s in batch])
        for slug, vector in zip(batch, vectors):
            query_vectors[slug] = [round(x, 6) for x in vector]
        _save(QUERY_EMBEDDINGS_FILE, query_vectors)

    # HyDE variants are scored only when every query has cached approaches,
    # so every method is measured on the same queries.
    hyde_cache = _load(HYDE_FILE, {})
    missing_hyde = [s for s in queries if s not in hyde_cache]
    use_hyde = bool(hyde_cache) and not missing_hyde
    if hyde_cache and missing_hyde:
        print(f"HyDE cache lacks {len(missing_hyde)} of {len(queries)} queries — run `hyde --yes`; skipping HyDE methods")

    # method -> slug -> ranked slugs (top 5)
    methods = ["tags", "embeddings", "embeddings, no floor"] + (["hyde", "hyde + statement"] if use_hyde else [])
    results: dict[str, dict[str, list[str]]] = {m: {} for m in methods}
    # method -> slug -> {candidate slug: similarity}, for the misses table
    detail: dict[str, dict[str, dict]] = {m: {} for m in methods}

    def top5(rows: list[dict], problem: ProblemContext, floor: float = recall.MIN_SIMILARITY) -> list[str]:
        return [p.slug for p in recall.rank_by_meaning(rows, problem, limit=5, min_similarity=floor)]

    def sims(rows: list[dict]) -> dict[str, float]:
        return {r["problem_slug"]: round(float(r["similarity"]), 2) for r in rows[:8]}

    for n, slug in enumerate(queries, 1):
        problem = _context(slug, problems)
        own = lambda rs: [r for r in rs if r["problem_slug"] != slug]  # noqa: E731

        tag_rows = own(await recall.fetch_by_tags(token, problem))
        results["tags"][slug] = [p.slug for p in recall.rank_by_tags(tag_rows, problem, limit=5)]

        near = own(await db.match_solutions(token, query_vectors[slug], recall.CANDIDATES))
        results["embeddings"][slug] = top5(near, problem)
        results["embeddings, no floor"][slug] = top5(near, problem, floor=0.0)
        detail["embeddings"][slug] = sims(near)

        if use_hyde:
            nears = [own(await db.match_solutions(token, v, recall.CANDIDATES)) for v in hyde_cache[slug]["vectors"]]
            by_approach = merge_candidates(nears)
            with_statement = merge_candidates(nears + [near])
            results["hyde"][slug] = top5(by_approach, problem)
            results["hyde + statement"][slug] = top5(with_statement, problem)
            detail["hyde"][slug] = sims(by_approach)
            detail["hyde + statement"][slug] = sims(with_statement)

        if n % 25 == 0:
            print(f"  {n}/{len(queries)} queries scored")

    report = build_report(problems, techniques, tiers, results, detail, solved, len(rows))
    REPORT_FILE.write_text(report, encoding="utf-8")
    print(report.split("## Misses")[0])
    print(f"-> {REPORT_FILE}")


def _context(slug: str, problems: dict) -> ProblemContext:
    p = problems[slug]
    return ProblemContext(
        slug=slug,
        title=f"{p['number']}. {p['title']}",
        difficulty=p["difficulty"],
        statement=p["statement"],
        topic_tags=p["tags"],
    )


def build_report(problems, techniques, tiers, results, detail, solved, n_rows) -> str:
    out: list[str] = []
    out.append("# Recall evaluation")
    out.append("")
    out.append(
        f"_Generated {datetime.now(timezone.utc).isoformat(timespec='minutes')} by "
        f"`uv run python -m app.recall_eval run` over {n_rows} saved solutions ({len(solved)} problems). "
        "Do not edit by hand._"
    )
    out.append("")
    out.append(
        "For each solved problem with a statement and at least one relative, retrieval ran over the "
        "user's own rows with the query's own row excluded — by topic tags and by embedding similarity, "
        f"same rows, same k, the production similarity floor ({recall.MIN_SIMILARITY}) — and the top k "
        "was scored against three label sets. **hit@k**: a relative in the top k. **recall@k**: share of "
        "the relatives in the top k. **MRR**: 1 / rank of the first relative."
    )
    out.append("")
    out.append("- **LeetCode similar**: LeetCode's curated Similar Questions, either direction, among solved problems. "
               "External; mixes same-technique with same-series.")
    out.append("- **same pattern**: the saved solutions share a coarse pattern (one of 19). Big buckets; a hit says little.")
    out.append("- **same technique**: the saved solutions share a specific technique (one of "
               f"{len(TAXONOMY)}, `app/recall_eval.py`). This is \"solved similarly\".")
    out.append("")
    if "hyde" in results:
        out.append(f"Methods: **tags** (topic-tag overlap); **embeddings** (the problem's statement embedded, "
                   f"today's production recall); **hyde** ({HYDE_APPROACHES} plausible approaches written by the "
                   "summary model and embedded, a row scoring by its best match against any of them); "
                   "**hyde + statement** (best match against the statement or any approach).")
        out.append("")

    handcheck = _load(HANDCHECK_FILE, [])
    judged = [e for e in handcheck if e.get("human") in ("yes", "no")]
    if judged:
        yes = sum(1 for e in judged if e["human"] == "yes")
        out.append(f"**Hand check:** of {len(judged)} LeetCode-similar pairs judged by hand, {yes} "
                   f"({100 * yes / len(judged):.0f}%) are solved similarly by the definition above.")
        out.append("")

    for tier, relevant in tiers.items():
        scored = [s for s in results["tags"] if relevant.get(s)]
        if not scored:
            continue
        covered = sum(1 for s in solved if relevant.get(s))
        sizes = [len(relevant[s]) for s in scored]
        out.append(f"## {tier} — n = {len(scored)} queries ({covered} of {len(solved)} solved problems have a "
                   f"relative; median relatives per query {sorted(sizes)[len(sizes) // 2]})")
        out.append("")
        out.append("| Method | " + " | ".join(f"hit@{k}" for k in KS) + " | " + " | ".join(f"recall@{k}" for k in KS) + " | MRR |")
        out.append("| --- | " + " | ".join("---:" for _ in range(2 * len(KS) + 1)) + " |")
        for method, ranked in results.items():
            hits = [_mean([hit_at(ranked[s], relevant[s], k) for s in scored]) for k in KS]
            recs = [_mean([recall_at(ranked[s], relevant[s], k) for s in scored]) for k in KS]
            mrr = _mean([reciprocal_rank(ranked[s], relevant[s]) for s in scored])
            out.append(f"| {method} | " + " | ".join(f"{100 * h:.0f}%" for h in hits) + " | "
                       + " | ".join(f"{100 * r:.0f}%" for r in recs) + f" | {mrr:.2f} |")
        out.append("")

    if techniques:
        lc = tiers["LeetCode similar"]
        pairs = [(a, b) for a, bs in lc.items() for b in bs]
        if pairs:
            same_p = sum(1 for a, b in pairs if b in tiers["same pattern"].get(a, set()))
            same_t = sum(1 for a, b in pairs if b in tiers["same technique"].get(a, set()))
            out.append(f"**Label agreement:** of {len(pairs)} LeetCode-similar pairs, {same_p} "
                       f"({100 * same_p / len(pairs):.0f}%) share a pattern and {same_t} "
                       f"({100 * same_t / len(pairs):.0f}%) share a technique.")
            out.append("")

    tier_name = "same technique" if techniques else "LeetCode similar"
    relevant = tiers[tier_name]
    scored = [s for s in results["tags"] if relevant.get(s)]

    # Which method does best on this tier, and what each one fixes or breaks
    # relative to today's production method.
    def hit3(method: str, s: str) -> bool:
        return bool(hit_at(results[method][s], relevant[s], 3))

    best = max(results, key=lambda m: sum(hit3(m, s) for s in scored)) if scored else "embeddings"
    if "hyde" in results and scored:
        out.append(f"**Against `embeddings` on the {tier_name} tier (hit@3):**")
        out.append("")
        for method in results:
            if method == "embeddings":
                continue
            fixes = sum(1 for s in scored if hit3(method, s) and not hit3("embeddings", s))
            breaks = sum(1 for s in scored if hit3("embeddings", s) and not hit3(method, s))
            out.append(f"- `{method}`: fixes {fixes}, breaks {breaks}")
        out.append("")

    shown = best if best in detail and detail[best] else "embeddings"
    misses = [s for s in scored if not hit3(shown, s)]
    out.append(f"## Misses at k = 3 — {shown}, {tier_name} tier ({len(misses)})")
    out.append("")
    out.append(f"| Query | Pattern / technique | Expected (up to 3) | {shown} top 3 (similarity) | Tags top 3 |")
    out.append("| --- | --- | --- | --- | --- |")
    for s in misses[:80]:
        sims = detail[shown].get(s, {})
        got = ", ".join(f"{x} ({sims.get(x, '?')})" for x in results[shown][s][:3]) or "—"
        tags = ", ".join(results["tags"][s][:3]) or "—"
        p, t = labels_of(techniques, s)
        out.append(f"| {s} | {p or '—'} / {t or '—'} | {', '.join(sorted(relevant[s])[:3])} | {got} | {tags} |")
    out.append("")
    return "\n".join(out) + "\n"


# --- CLI -------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.recall_eval")
    parser.add_argument("--token", help="a Supabase access token, instead of signing in at the prompt")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("fetch", help="LeetCode's data on every solved problem (cached)")
    p_label = sub.add_parser("label", help="a pattern + technique per saved solution (cached)")
    p_label.add_argument("--yes", action="store_true", help="actually spend tokens; without it, only estimate")
    p_check = sub.add_parser("check", help="write 20 LeetCode-similar pairs for a hand check")
    p_check.add_argument("--seed", type=int, default=7)
    p_hyde = sub.add_parser("hyde", help="write and embed three plausible approaches per problem (cached)")
    p_hyde.add_argument("--yes", action="store_true", help="actually spend tokens; without it, only estimate")
    sub.add_parser("run", help="score every method against all label sets")

    args = parser.parse_args(argv)
    if args.command == "fetch":
        asyncio.run(fetch(args.token))
    elif args.command == "label":
        asyncio.run(label(args.token, args.yes))
    elif args.command == "check":
        asyncio.run(check(args.token, args.seed))
    elif args.command == "hyde":
        asyncio.run(hyde(args.token, args.yes))
    elif args.command == "run":
        asyncio.run(run(args.token))


if __name__ == "__main__":
    main(sys.argv[1:])
