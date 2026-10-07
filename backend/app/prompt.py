"""
The tutor, independent of which model delivers it.

Everything about *how the product behaves* lives here — the rules, and how the
problem and the user's code are presented. Providers only decide how to get
this text to their API. Swapping vendors must not change the tutor.
"""

from collections.abc import Sequence

from .schemas import ChatRequest, PriorSolution, SolutionRequest

# Bump on every change to SYSTEM_PROMPT's wording. Recorded with each call, so
# the benchmark report can put replies from different versions side by side.
PROMPT_VERSION = 4

# Kept deliberately tight: numbered levels and hard limits rather than
# explanation. Version 1 was vague ("escalate gradually", "a few sentences")
# and the replays showed what vague buys — praise openers, whole approaches on
# the first message, the same hint repeated. Version 2 fixed those but treated
# every message as a request for a hint once code existed, so a direct question
# got another line-level hint instead of an answer; version 3 added the "first
# decide what they are asking" rules. Version 4 split the approach rule in two
# (a bare yes/no question was getting the whole method as "the gap"), stopped
# "can it be faster" from volunteering the better method, and banned the
# labels that leaked ("Hint:", "Key observation:"). Add words only where a
# replay case fails. See docs/design-choices.md.
SYSTEM_PROMPT = """\
You are LeetCode AUX, a tutor beside someone solving a LeetCode problem. Help \
them reach the solution themselves. Never write code that solves it, in any \
form or language; if asked, say no and offer a hint.

First decide what they are asking, then answer that and nothing else:
- A hint ("help", "stuck", "another one", "what do I do about…"): the next \
hint level, below.
- A yes/no question about an approach ("can a stack do it?"): yes or no in one \
sentence, and nothing they didn't ask.
- A question about their own reasoning or code ("is this right?", "so my logic \
is… no?"): say whether it's right, then name the one flaw in a sentence — what \
is wrong, not how to fix it.
- A question about something you said: explain that one point more plainly. \
No new hint.
- Why their code fails: the one line responsible, and a question about what \
they expect it to do.
- Whether it can be better or faster: yes or no, and what limits the current \
approach. Stop there; hint toward the better one only when asked.
- Anything off the problem: one sentence steering back. Don't answer it.

Hint levels — exactly one per reply, nothing from a later one:
0. The kind of problem, plus one question. No observation, no technique.
1. The key observation.
2. The technique or data structure.
3. The algorithm's steps, in words.
4. A specific line of their code to reconsider.
Start at 0 if they've written nothing; a bare starter signature is nothing. \
Each new request for a hint moves one level down.

Never repeat a point you've already made. If it didn't land, say it more \
plainly or ask which part is unclear.

If a problem they've already solved (listed after the statement) is related, \
name it in your first sentence; say what carries over only when you reach that \
level. If it's this same problem, say so and ask what they remember — nothing \
more.

No praise or filler openers. Never label parts of your reply (no "Hint:", \
"Key observation:", "The gap:"). At most three sentences before they have \
code, five after. Plain prose, no lists.
"""


def problem_block(request: ChatRequest, prior: Sequence[PriorSolution] = ()) -> str:
    """The problem as the model should see it, followed by any recalled prior
    solutions. Stable for a whole session — it changes only when a new
    solution is saved — so providers put it where their caching works best."""
    p = request.problem
    if p is None:
        text = "No problem context was provided — ask what they're working on."
    else:
        header = p.title or p.slug
        if p.difficulty:
            header += f" ({p.difficulty})"
        statement = p.statement or "(statement not available)"
        text = f"The problem they are working on:\n\n{header}\n\n{statement}"

    recalled = prior_block(prior)
    return f"{text}\n\n{recalled}" if recalled else text


def prior_block(prior: Sequence[PriorSolution]) -> str | None:
    """The user's recalled solutions — summaries only, never code."""
    if not prior:
        return None

    lines = ["Problems they have already solved, from their saved solutions:"]
    for s in prior:
        name = s.title or s.slug
        if s.difficulty:
            name += f" ({s.difficulty})"
        head = f"- {name}"
        if s.topic_tags:
            head += " [" + ", ".join(s.topic_tags) + "]"
        if s.same_problem:
            head += " — this is the problem they are working on now"
        lines.append(head)
        lines.append(f"  {s.summary.strip()}")
    return "\n".join(lines)


def code_block(request: ChatRequest) -> str | None:
    """The user's current code, or None if there is nothing worth showing.
    Changes every message, so it belongs in the final turn, never earlier."""
    c = request.code
    if c is None or not c.code.strip():
        return None
    language = c.language or "unknown language"
    return f"Their current code ({language}):\n\n```\n{c.code}\n```"


# ---------------------------------------------------------------------------
# Summaries of accepted solutions
#
# Not the tutor: a one-off note about code that has already been accepted, so
# the "never write code" rules above do not apply and are not sent. Kept
# deliberately simple for now.
# ---------------------------------------------------------------------------

SUMMARY_PROMPT = """\
You are writing a note for someone's own record of a LeetCode problem they \
just solved. Summarise the accepted solution below in two to four plain \
sentences: the approach or pattern it uses, the key data structures, and its \
time and space complexity.

Describe what this code actually does, not what an ideal solution would do. \
No code, no headers, no bullet lists.
"""


def solution_block(request: SolutionRequest) -> str:
    """The problem and the accepted code, as the model should see them."""
    p = request.problem

    header = p.title or p.slug
    if p.difficulty:
        header += f" ({p.difficulty})"

    parts = [f"The problem:\n\n{header}"]
    if request.topic_tags:
        parts.append("Topics: " + ", ".join(request.topic_tags))
    if p.statement:
        parts.append(p.statement)

    language = request.language or "unknown language"
    parts.append(f"The accepted solution ({language}):\n\n```\n{request.code}\n```")

    return "\n\n".join(parts)
