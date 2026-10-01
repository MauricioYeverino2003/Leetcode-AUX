"""
Benchmarks: one JSON line per model call, a generated markdown report, and a
replay runner for comparing configurations on identical input.

    uv run python -m app.benchmarks report            -> docs/benchmarks.md
    uv run python -m app.benchmarks run --yes         -> replay benchmarks/cases.json

Every call — from the panel or from `run` — lands in the same JSONL file with
the same shape, so the report can compare them. The file holds prompts and
user code and is gitignored; the markdown it generates is committed.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from .config import BACKEND_DIR, settings
from .prices import PRICES_AS_OF, estimate_cost, lookup
from .schemas import ChatRequest, ChatResponse, Timing

CASES_FILE = BACKEND_DIR / "benchmarks" / "cases.json"
REPORT_FILE = BACKEND_DIR.parent / "docs" / "benchmarks.md"

# ---------------------------------------------------------------------------
# Recording
# ---------------------------------------------------------------------------


def record(
    *,
    source: str,
    user_id: str | None,
    provider: str,
    request: ChatRequest,
    response: ChatResponse,
    case: str | None = None,
) -> None:
    """Append one line describing a model call. No-op when disabled."""
    path = settings.benchmarks_file
    if path is None:
        return

    last_user = request.messages[-1].content
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": source,
        "case": case,
        "user_id": user_id,
        "provider": provider,
        "model": response.model,
        "effort": settings.llm_effort,
        "timing": response.timing.model_dump(),
        "usage": response.usage.model_dump(),
        "cost_usd": response.cost_usd,
        "request": {
            "slug": request.problem.slug if request.problem else None,
            "title": request.problem.title if request.problem else None,
            "difficulty": request.problem.difficulty if request.problem else None,
            "statement_chars": len(request.problem.statement or "") if request.problem else 0,
            "code_chars": len(request.code.code) if request.code else 0,
            "code_language": request.code.language if request.code else None,
            "turns": len(request.messages),
            "last_message": last_user,
        },
        "prompt": response.prompt,
        "reply": response.reply,
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def load() -> list[dict]:
    path = settings.benchmarks_file
    if path is None or not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def _percentile(values: list[int], p: float) -> int:
    if not values:
        return 0
    s = sorted(values)
    k = (len(s) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return round(s[lo] + (s[hi] - s[lo]) * (k - lo))


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _fmt_cost(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"${value:.4f}"


def _truncate(text: str | None, limit: int) -> str:
    if not text:
        return ""
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"


def build_report(rows: list[dict], samples: int) -> str:
    out: list[str] = []
    out.append("# Benchmarks")
    out.append("")
    out.append(
        f"_Generated {datetime.now(timezone.utc).isoformat(timespec='minutes')} "
        f"by `uv run python -m app.benchmarks report` from {len(rows)} recorded calls. "
        f"Costs are estimates from `app/prices.py` (prices as of {PRICES_AS_OF}). "
        "Do not edit by hand._"
    )
    out.append("")

    if not rows:
        out.append("No calls recorded yet.")
        return "\n".join(out) + "\n"

    # --- summary, grouped by configuration
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        groups[(r["source"], r["provider"], r["model"], r.get("effort") or "default")].append(r)

    out.append("## Summary by configuration")
    out.append("")
    out.append(
        "| Source | Provider | Model | Effort | n | model_ms p50 | model_ms p95 "
        "| in (uncached) | out | reasoning | cache hit | cost/call | cost total |"
    )
    out.append("| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")

    for key in sorted(groups):
        source, provider, model, effort = key
        g = groups[key]
        ms = [r["timing"]["model_ms"] for r in g]
        usage = [r["usage"] for r in g]
        costs = [r["cost_usd"] for r in g if r.get("cost_usd") is not None]
        cache_hits = sum(1 for u in usage if u["cache_read_input_tokens"] > 0)
        out.append(
            f"| {source} | {provider} | {model} | {effort} | {len(g)} "
            f"| {_percentile(ms, 0.5)} | {_percentile(ms, 0.95)} "
            f"| {round(_mean([u['input_tokens'] for u in usage]))} "
            f"| {round(_mean([u['output_tokens'] for u in usage]))} "
            f"| {round(_mean([u['reasoning_tokens'] for u in usage]))} "
            f"| {cache_hits}/{len(g)} "
            f"| {_fmt_cost(_mean(costs) if costs else None)} "
            f"| {_fmt_cost(sum(costs) if costs else None)} |"
        )
    out.append("")
    out.append(
        "`in (uncached)` is input billed at the full rate; cached input is counted "
        "under cache hit. `reasoning` is the part of `out` spent thinking before "
        "the visible reply (OpenAI reports it; Anthropic folds it into `out`)."
    )
    out.append("")

    # --- samples
    if samples > 0:
        out.append(f"## Last {min(samples, len(rows))} calls")
        out.append("")
        for r in rows[-samples:][::-1]:
            req, u, t = r["request"], r["usage"], r["timing"]
            title = req.get("title") or req.get("slug") or "(no problem)"
            label = f"{r['source']}" + (f" · {r['case']}" if r.get("case") else "")
            out.append(
                f"### {title} — {label} · {r['model']} · effort {r.get('effort') or 'default'} "
                f"· {t['model_ms']} ms · {_fmt_cost(r.get('cost_usd'))}"
            )
            out.append("")
            out.append(
                f"{u['input_tokens']} in (uncached) + {u['cache_read_input_tokens']} cached · "
                f"{u['output_tokens']} out ({u['reasoning_tokens']} reasoning) · "
                f"code {req['code_chars']} chars ({req.get('code_language') or 'n/a'}) · "
                f"{req['turns']} turn(s) · {r['ts']}"
            )
            out.append("")
            out.append(f"**User:** {_truncate(req.get('last_message'), 300)}")
            out.append("")
            out.append(f"**Reply:** {_truncate(r.get('reply'), 700)}")
            out.append("")

    return "\n".join(out) + "\n"


def report(samples: int) -> None:
    rows = load()
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(build_report(rows, samples), encoding="utf-8")
    print(f"{len(rows)} calls -> {REPORT_FILE}")


# ---------------------------------------------------------------------------
# Replay runner
# ---------------------------------------------------------------------------


def _load_cases() -> list[dict]:
    return json.loads(CASES_FILE.read_text(encoding="utf-8"))


def _estimate_run_cost(cases: list[dict], model: str, repeat: int) -> float | None:
    """Rough pre-flight estimate: ~4 chars per input token, ~1,200 output tokens
    per call including reasoning. Only for the confirmation prompt."""
    from .prompt import SYSTEM_PROMPT

    price = lookup(model)
    if price is None:
        return None
    total = 0.0
    for case in cases:
        req = case["request"]
        chars = len(SYSTEM_PROMPT)
        chars += len((req.get("problem") or {}).get("statement") or "")
        chars += len((req.get("code") or {}).get("code") or "")
        chars += sum(len(m["content"]) for m in req["messages"])
        total += (chars / 4) * price.input / 1_000_000 + 1200 * price.output / 1_000_000
    return total * repeat


async def run(repeat: int, yes: bool) -> None:
    from .providers import get_provider

    cases = _load_cases()
    provider = get_provider()
    calls = len(cases) * repeat
    estimate = _estimate_run_cost(cases, provider.model, repeat)

    print(
        f"{calls} call(s): {len(cases)} case(s) x {repeat} on {provider.name}/{provider.model} "
        f"effort={settings.llm_effort or 'default'} — rough estimate "
        f"{_fmt_cost(estimate) if estimate is not None else 'unknown (no price entry)'}"
    )
    if not yes:
        print("Dry run. Re-run with --yes to spend it.")
        return
    if settings.benchmarks_file is None:
        print("BENCHMARKS_PATH is empty — results would not be recorded. Aborting.")
        return

    total_cost = 0.0
    for i in range(repeat):
        for case in cases:
            request = ChatRequest.model_validate(case["request"])
            started = perf_counter()
            response = await provider.chat(request)
            ms = round((perf_counter() - started) * 1000)
            response.timing = Timing(model_ms=ms, backend_ms=ms)
            response.cost_usd = estimate_cost(response.model, response.usage)
            record(
                source="bench",
                user_id=None,
                provider=provider.name,
                request=request,
                response=response,
                case=case["name"],
            )
            u = response.usage
            total_cost += response.cost_usd or 0.0
            print(
                f"[{i + 1}/{repeat}] {case['name']:<20} {ms:>6} ms  "
                f"in {u.input_tokens:>5}  out {u.output_tokens:>5}  "
                f"reasoning {u.reasoning_tokens:>5}  {_fmt_cost(response.cost_usd)}"
            )

    print(f"done: {calls} call(s), total {_fmt_cost(total_cost)} -> {settings.benchmarks_file}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.benchmarks")
    sub = parser.add_subparsers(dest="command", required=True)

    p_report = sub.add_parser("report", help="write docs/benchmarks.md from the recorded calls")
    p_report.add_argument("--samples", type=int, default=5, help="how many recent calls to include verbatim")

    p_run = sub.add_parser("run", help="replay benchmarks/cases.json against the configured provider")
    p_run.add_argument("--repeat", type=int, default=1, help="run every case this many times")
    p_run.add_argument("--yes", action="store_true", help="actually spend tokens; without it, only estimate")

    args = parser.parse_args(argv)
    if args.command == "report":
        report(args.samples)
    elif args.command == "run":
        asyncio.run(run(args.repeat, args.yes))


if __name__ == "__main__":
    main(sys.argv[1:])
