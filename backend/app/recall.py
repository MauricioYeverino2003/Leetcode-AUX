"""
Recall: which of the user's saved solutions the tutor should be shown for the
problem in front of them.

Similarity is LeetCode topic-tag overlap. Tags are stored with every saved
solution, so this needs no new data and no embeddings. The design log keeps
the NeetCode pattern map and pgvector as the upgrade path for when tags prove
too coarse. Tags that nearly every problem carries are ignored: overlap on
them alone says nothing.

Only summaries come back, never code — the tutor's no-code rule applies to
the user's own earlier solutions too.
"""

from . import db
from .schemas import PriorSolution, ProblemContext

# Shared by so many problems that overlap on them alone means nothing.
GENERIC_TAGS = frozenset({"Array", "String"})

# How many prior solutions the tutor is shown. Each is a short summary.
MAX_PRIOR = 3

# How many candidate rows to pull before ranking.
CANDIDATES = 50


async def recall(token: str, problem: ProblemContext) -> list[PriorSolution]:
    tags = [t for t in problem.topic_tags if t not in GENERIC_TAGS]
    if tags:
        rows = await db.list_solutions_by_tags(token, tags, limit=CANDIDATES)
    else:
        # Nothing to match on — but "you have solved this before" still applies.
        rows = await db.list_solutions_for_problem(token, problem.slug)

    wanted = set(tags)
    scored: list[tuple[tuple[bool, int, str], dict]] = []
    for row in rows:
        same = row["problem_slug"] == problem.slug
        shared = len(wanted.intersection(row.get("topic_tags") or []))
        if not same and shared == 0:
            continue
        # The same problem first, then the most tags in common, then newest.
        scored.append(((same, shared, row.get("created_at") or ""), row))

    scored.sort(key=lambda item: item[0], reverse=True)

    # One per problem: a user may have saved several solutions to the same one.
    seen: set[str] = set()
    prior: list[PriorSolution] = []
    for (same, _, _), row in scored:
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
            )
        )
        if len(prior) == MAX_PRIOR:
            break
    return prior
