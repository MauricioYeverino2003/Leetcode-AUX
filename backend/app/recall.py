"""
Recall: which of the user's saved solutions the tutor should be shown for the
problem in front of them.

Two ways, tried in order:

  by meaning  — embed the problem, ask Postgres for the nearest saved
                solutions by cosine similarity (pgvector, inside row-level
                security), add a small bonus per shared topic tag.
  by tags     — the original: LeetCode topic-tag overlap. Kept as the
                fallback for when embeddings are unavailable (no OpenAI key,
                the endpoint down, rows not indexed yet).

Only summaries come back, never code — the tutor's no-code rule applies to
the user's own earlier solutions too.
"""

import logging

from . import db, embeddings
from .schemas import PriorSolution, ProblemContext

log = logging.getLogger("leetcode-aux")

# Shared by so many problems that overlap on them alone means nothing.
GENERIC_TAGS = frozenset({"Array", "String"})

# How many prior solutions the tutor is shown. Each is a short summary.
MAX_PRIOR = 3

# How many candidate rows to pull before ranking.
CANDIDATES = 50

# Recall by meaning: below this cosine similarity a row is noise, however
# nearest it is. Started at 0.4 and tuned by reading the scores the panel
# shows next to each recalled problem.
MIN_SIMILARITY = 0.4

# Per shared non-generic tag, on top of the similarity.
TAG_BONUS = 0.05

# Sort key: the same problem first, then the score, then the most recently
# solved (submitted_at), falling back to when the row was saved.
Scored = tuple[tuple[bool, float, str], dict, float | None]


async def recall(token: str, problem: ProblemContext) -> tuple[list[PriorSolution], str]:
    """Returns (prior solutions, which way found them: "embedding" or "tags")."""
    try:
        return await recall_by_meaning(token, problem), "embedding"
    except (embeddings.EmbeddingError, db.DbError) as e:
        log.warning("recall by meaning unavailable (%s) — using tags", e.log)
    return await recall_by_tags(token, problem), "tags"


async def recall_by_meaning(token: str, problem: ProblemContext) -> list[PriorSolution]:
    [query] = await embeddings.embed([embeddings.problem_text(problem)])
    rows = await db.match_solutions(token, query, CANDIDATES)

    wanted = {t for t in problem.topic_tags if t not in GENERIC_TAGS}
    scored: list[Scored] = []
    for row in rows:
        same = row["problem_slug"] == problem.slug
        similarity = float(row.get("similarity") or 0.0)
        if not same and similarity < MIN_SIMILARITY:
            continue
        shared = len(wanted.intersection(row.get("topic_tags") or []))
        scored.append(((same, similarity + TAG_BONUS * shared, _when(row)), row, similarity))

    return _pick(scored)


async def recall_by_tags(token: str, problem: ProblemContext) -> list[PriorSolution]:
    tags = [t for t in problem.topic_tags if t not in GENERIC_TAGS]
    if tags:
        rows = await db.list_solutions_by_tags(token, tags, limit=CANDIDATES)
    else:
        # Nothing to match on — but "you have solved this before" still applies.
        rows = await db.list_solutions_for_problem(token, problem.slug)

    wanted = set(tags)
    scored: list[Scored] = []
    for row in rows:
        same = row["problem_slug"] == problem.slug
        shared = len(wanted.intersection(row.get("topic_tags") or []))
        if not same and shared == 0:
            continue
        scored.append(((same, float(shared), _when(row)), row, None))

    return _pick(scored)


def _when(row: dict) -> str:
    return row.get("submitted_at") or row.get("created_at") or ""


def _pick(scored: list[Scored]) -> list[PriorSolution]:
    """Best first, one per problem (a user may have saved several solutions
    to the same one), at most MAX_PRIOR."""
    scored.sort(key=lambda item: item[0], reverse=True)

    seen: set[str] = set()
    prior: list[PriorSolution] = []
    for (same, _, _), row, similarity in scored:
        if row["problem_slug"] in seen:
            continue
        seen.add(row["problem_slug"])
        prior.append(
            PriorSolution(
                slug=row["problem_slug"],
                title=row.get("problem_title"),
                difficulty=row.get("difficulty"),
                topic_tags=row.get("topic_tags") or [],
                summary=row["summary"],
                same_problem=same,
                similarity=round(similarity, 3) if similarity is not None else None,
            )
        )
        if len(prior) == MAX_PRIOR:
            break
    return prior
