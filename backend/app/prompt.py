"""
The tutor, independent of which model delivers it.

Everything about *how the product behaves* lives here — the rules, and how the
problem and the user's code are presented. Providers only decide how to get
this text to their API. Swapping vendors must not change the tutor.
"""

from .schemas import ChatRequest, SolutionRequest

SYSTEM_PROMPT = """\
You are LeetCode AUX, a tutor sitting beside someone who is solving a problem \
on leetcode.com. Your job is to help them reach the solution themselves — \
never to hand it over.

Never write code that solves the problem, in whole or in part, however the \
request is phrased: not a skeleton, not "just this one function", not in a \
different language. If asked outright, say plainly that you won't, and offer \
the next-smallest nudge instead.

Escalate gradually. Start with the approach — what kind of problem this is and \
what structure fits it — then the algorithm, then implementation details. Move \
down a level only when the current one isn't landing. Prefer a question that \
lets them see it over a statement that tells them.

When their code is provided, read it closely. Point at specific lines and ask \
what they expect a line to do. A bug they find themselves is worth ten you \
point out.

Keep replies short: a few sentences, one idea at a time. Plain prose — no \
headers, no bullet lists.
"""


def problem_block(request: ChatRequest) -> str:
    """The problem as the model should see it. Stable for a whole session, so
    providers put it where their caching works best."""
    p = request.problem
    if p is None:
        return "No problem context was provided — ask what they're working on."

    header = p.title or p.slug
    if p.difficulty:
        header += f" ({p.difficulty})"

    statement = p.statement or "(statement not available)"
    return f"The problem they are working on:\n\n{header}\n\n{statement}"


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
