"""
Recall evaluation: how often does recall find what it should?

    uv run python -m app.recall_eval fetch   # LeetCode's data on every solved problem -> benchmarks/problems.json
    uv run python -m app.recall_eval label   # one technique per saved solution      -> benchmarks/techniques.json
    uv run python -m app.recall_eval check   # 20 pairs for a hand check             -> benchmarks/recall-handcheck.json
    uv run python -m app.recall_eval run     # score both methods                     -> docs/recall-eval.md

"Should" is defined two ways, and both are scored:

  LeetCode tier   — LeetCode's own curated "Similar Questions" list, in either
                    direction, restricted to problems the user has solved. An
                    external baseline; it mixes same-technique with same-series.
  technique tier  — one technique per saved solution, chosen from a fixed list
                    by a cheap model reading the summary. Two problems match if
                    they share it. Closest to what the tutor needs: a recalled
                    problem whose approach carries over.

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
TECHNIQUES_FILE = BENCH / "techniques.json"  # committed: slug -> technique
HANDCHECK_FILE = BENCH / "recall-handcheck.json"  # committed once filled in
REPORT_FILE = BACKEND_DIR.parent / "docs" / "recall-eval.md"

LEETCODE_GRAPHQL = "https://leetcode.com/graphql"
LEETCODE_PACE_S = 1.0

KS = (1, 3, 5)

# NeetCode's patterns, lightly adapted. One per saved solution.
TECHNIQUES = [
    "arrays & hashing",
    "two pointers",
    "sliding window",
    "stack",
    "binary search",
    "linked list",
    "trees",
    "tries",
    "heap",
    "backtracking",
    "graph traversal",
    "advanced graphs",
    "1-D dynamic programming",
    "2-D dynamic programming",
    "greedy",
    "intervals",
    "math & geometry",
    "bit manipulation",
    "simulation",
]

LABEL_PROMPT = (
    "You classify how a LeetCode solution was solved. Reply with exactly one label from this list and "
    "nothing else:\n" + "\n".join(f"- {t}" for t in TECHNIQUES) + "\n\n"
    "Pick the technique the solution actually uses, as described in its summary — not what the problem "
    "is usually solved with. If several apply, pick the one that carries the solution."
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


# --- label: one technique per saved solution -----------------------------------


async def label(token: str | None, yes: bool) -> None:
    from .providers import get_provider

    token = await sign_in(token)
    rows = await db.list_solutions(token)
    # One label per problem; the newest row's summary speaks for it.
    by_slug: dict[str, dict] = {}
    for row in rows:
        by_slug[row["problem_slug"]] = row

    techniques = _load(TECHNIQUES_FILE, {})
    todo = [s for s in by_slug if s not in techniques]
    provider = get_provider()
    model = settings.summary_model or provider.model
    print(f"{len(by_slug)} problems, {len(techniques)} labeled, {len(todo)} to label on {model} "
          f"— rough estimate ${len(todo) * 0.0004:.2f}")
    if not yes:
        print("Dry run. Re-run with --yes to spend it.")
        return

    for i, slug in enumerate(todo, 1):
        row = by_slug[slug]
        text = f"{row.get('problem_number') or ''}. {row.get('problem_title') or slug}\n\n{row['summary']}"
        choice = "unknown"
        for attempt in range(2):
            response = await provider.complete(
                instructions=LABEL_PROMPT if attempt == 0 else LABEL_PROMPT + "\n\nReply with the label only.",
                text=text,
                effort="low",
                model=settings.summary_model,
            )
            answer = response.reply.strip().strip(".").lower()
            match = next((t for t in TECHNIQUES if t == answer), None) or next(
                (t for t in TECHNIQUES if t in answer), None
            )
            if match:
                choice = match
                break
        techniques[slug] = choice
        print(f"  [{i}/{len(todo)}] {slug}: {choice}")
        _save(TECHNIQUES_FILE, techniques)

    counts: dict[str, int] = {}
    for t in techniques.values():
        counts[t] = counts.get(t, 0) + 1
    print("labels:", ", ".join(f"{t} {n}" for t, n in sorted(counts.items(), key=lambda x: -x[1])))
    print(f"{len(techniques)} labels -> {TECHNIQUES_FILE}")


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


def technique_relevant(techniques: dict, solved: set[str]) -> dict[str, set[str]]:
    groups: dict[str, set[str]] = {}
    for slug in solved:
        t = techniques.get(slug)
        if t and t != "unknown":
            groups.setdefault(t, set()).add(slug)
    return {slug: (groups.get(techniques.get(slug, ""), set()) - {slug}) for slug in solved}


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


def check(seed: int) -> None:
    problems = _load(PROBLEMS_FILE, {})
    techniques = _load(TECHNIQUES_FILE, {})
    if not problems:
        sys.exit("Run `fetch` first.")
    solved = set(problems)
    related = leetcode_relevant(problems, solved)
    pairs = sorted({tuple(sorted((a, b))) for a, bs in related.items() for b in bs})
    random.Random(seed).shuffle(pairs)

    existing = {(e["a"], e["b"]) for e in _load(HANDCHECK_FILE, [])}
    entries = _load(HANDCHECK_FILE, [])
    for a, b in pairs:
        if len(entries) >= 20:
            break
        if (a, b) in existing:
            continue
        entries.append({
            "a": a, "a_title": problems[a]["title"],
            "b": b, "b_title": problems[b]["title"],
            "same_technique_by_labels": (techniques.get(a) == techniques.get(b)) if techniques else None,
            "technique_a": techniques.get(a), "technique_b": techniques.get(b),
            # Fill in: "yes" if the technique used for one would be the right first
            # hint for the other; "no" otherwise.
            "human": None,
        })
    _save(HANDCHECK_FILE, entries)
    print(f"{len(entries)} pairs -> {HANDCHECK_FILE}  (fill in each \"human\" with \"yes\" or \"no\")")


# --- run: score ----------------------------------------------------------------


async def run(token: str | None) -> None:
    problems = _load(PROBLEMS_FILE, {})
    techniques = _load(TECHNIQUES_FILE, {})
    if not problems:
        sys.exit("Run `fetch` first.")
    if not techniques:
        print("No techniques.json — the technique tier will be skipped (run `label`).")

    token = await sign_in(token)
    rows = await db.list_solutions(token)
    solved = {r["problem_slug"] for r in rows}
    tiers = {
        "LeetCode similar": leetcode_relevant(problems, solved),
        "same technique": technique_relevant(techniques, solved) if techniques else {},
    }

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

    # method -> slug -> ranked slugs (top 5)
    results: dict[str, dict[str, list[str]]] = {"tags": {}, "embeddings": {}, "embeddings, no floor": {}}
    detail: dict[str, dict] = {}
    for n, slug in enumerate(queries, 1):
        problem = _context(slug, problems)
        own = lambda rs: [r for r in rs if r["problem_slug"] != slug]  # noqa: E731

        tag_rows = own(await recall.fetch_by_tags(token, problem))
        results["tags"][slug] = [p.slug for p in recall.rank_by_tags(tag_rows, problem, limit=5)]

        near = own(await db.match_solutions(token, query_vectors[slug], recall.CANDIDATES))
        results["embeddings"][slug] = [p.slug for p in recall.rank_by_meaning(near, problem, limit=5)]
        results["embeddings, no floor"][slug] = [
            p.slug for p in recall.rank_by_meaning(near, problem, limit=5, min_similarity=0.0)
        ]
        detail[slug] = {"similarities": {r["problem_slug"]: round(float(r["similarity"]), 2) for r in near[:5]}}
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
        "same rows, same k, the production similarity floor (0.4) — and the top k was scored against two "
        "label sets. **hit@k**: a relative in the top k. **recall@k**: share of the relatives in the "
        "top k. **MRR**: 1 / rank of the first relative."
    )
    out.append("")
    out.append("- **LeetCode similar**: LeetCode's curated Similar Questions, either direction, among solved problems. "
               "External; mixes same-technique with same-series.")
    out.append("- **same technique**: one technique per saved solution, from its summary (`benchmarks/techniques.json`). "
               "What the tutor needs; our model's judgment of our own summaries.")
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
        out.append(f"## {tier} — n = {len(scored)} queries ({covered} of {len(solved)} solved problems have a relative)")
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
        lc, tech = tiers["LeetCode similar"], tiers["same technique"]
        pairs = [(a, b) for a, bs in lc.items() for b in bs]
        agree = sum(1 for a, b in pairs if b in tech.get(a, set()))
        if pairs:
            out.append(f"**Label agreement:** {agree} of {len(pairs)} LeetCode-similar pairs "
                       f"({100 * agree / len(pairs):.0f}%) also share a technique label.")
            out.append("")

    # Misses at k=3 on the technique tier (or LeetCode tier if no techniques)
    tier_name = "same technique" if techniques else "LeetCode similar"
    relevant = tiers[tier_name]
    misses = [s for s in results["embeddings"] if relevant.get(s) and not hit_at(results["embeddings"][s], relevant[s], 3)]
    out.append(f"## Misses at k = 3 — embeddings, {tier_name} tier ({len(misses)})")
    out.append("")
    out.append("| Query | Technique | Expected (up to 3) | Embeddings top 3 (similarity) | Tags top 3 |")
    out.append("| --- | --- | --- | --- | --- |")
    for s in misses[:60]:
        sims = detail[s]["similarities"]
        emb = ", ".join(f"{x} ({sims.get(x, '?')})" for x in results["embeddings"][s][:3]) or "—"
        tags = ", ".join(results["tags"][s][:3]) or "—"
        out.append(f"| {s} | {techniques.get(s, '—')} | {', '.join(sorted(relevant[s])[:3])} | {emb} | {tags} |")
    out.append("")
    return "\n".join(out) + "\n"


# --- CLI -------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.recall_eval")
    parser.add_argument("--token", help="a Supabase access token, instead of signing in at the prompt")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("fetch", help="LeetCode's data on every solved problem (cached)")
    p_label = sub.add_parser("label", help="one technique per saved solution (cached)")
    p_label.add_argument("--yes", action="store_true", help="actually spend tokens; without it, only estimate")
    p_check = sub.add_parser("check", help="write 20 LeetCode-similar pairs for a hand check")
    p_check.add_argument("--seed", type=int, default=7)
    sub.add_parser("run", help="score both methods against both label sets")

    args = parser.parse_args(argv)
    if args.command == "fetch":
        asyncio.run(fetch(args.token))
    elif args.command == "label":
        asyncio.run(label(args.token, args.yes))
    elif args.command == "check":
        check(args.seed)
    elif args.command == "run":
        asyncio.run(run(args.token))


if __name__ == "__main__":
    main(sys.argv[1:])
