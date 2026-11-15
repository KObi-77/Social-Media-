"""Daily pipeline: pick -> write -> critic loop -> fact-check -> save."""

import datetime as dt
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from . import agents
from .llm import LLM
from .schemas import Critique, FactCheck, Script

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Result:
    story: dict
    script: Script
    critiques: List[Critique] = field(default_factory=list)
    fact_check: Optional[FactCheck] = None
    status: str = "ready"  # ready | needs_review
    path: Optional[Path] = None


def _load_json(path: Path, default):
    return json.loads(path.read_text()) if path.exists() else default


def run(llm: LLM, fmt: str = "short", tradition: Optional[str] = None, trend_hints: str = "",
        max_rounds: int = 3, root: Path = ROOT, date: Optional[dt.date] = None) -> Result:
    date = date or dt.date.today()
    style = (root / "style_guide.md").read_text()
    stories = _load_json(root / "data" / "stories.json", [])
    history_path = root / "data" / "history.json"
    history = _load_json(history_path, [])

    pick = agents.pick_topic(llm, style, stories, history[-30:], trend_hints, tradition)
    story = next(s for s in stories if s["id"] == pick.story_id)
    print(f"Topic: {story['title']} ({story['tradition']}) — {pick.angle}")

    script = agents.write_script(llm, style, story, pick.angle, fmt)
    result = Result(story=story, script=script)
    for round_no in range(1, max_rounds + 1):
        review = agents.critique(llm, style, script, fmt)
        result.critiques.append(review)
        print(f"Critic round {round_no}: hook {review.hook_score} humor {review.humor_score} "
              f"twist {review.twist_score} loop {review.loop_score} approved={review.approved}")
        if review.approved:
            break
        script = agents.write_script(llm, style, story, pick.angle, fmt,
                                     review.rewrite_notes + review.style_violations, script)
    result.script = script

    check = agents.fact_check(llm, style, story, script)
    if not check.passed and check.required_fixes:
        print("Fact-check failed; revising once.")
        script = agents.write_script(llm, style, story, pick.angle, fmt, check.required_fixes, script)
        check = agents.fact_check(llm, style, story, script)
    result.script, result.fact_check = script, check
    approved = bool(result.critiques) and result.critiques[-1].approved
    result.status = "ready" if (check.passed and approved) else "needs_review"

    result.path = save(result, fmt, root / "output" / date.isoformat())
    history.append({"date": date.isoformat(), "story_id": story["id"], "tradition": story["tradition"],
                    "format": fmt, "title": script.title, "status": result.status})
    history_path.write_text(json.dumps(history, indent=1))
    return result


def to_markdown(r: Result, fmt: str) -> str:
    s = r.script
    lines = [f"# {s.title}", "",
             f"**Status:** {r.status} · **Format:** {fmt} · **Story:** {r.story['title']} "
             f"({r.story['tradition']}) · **Source:** {r.story['source']}", "",
             "## Script", "", "| # | Beat | Narration | On screen | Visual |", "|---|---|---|---|---|"]
    for i, sc in enumerate(s.scenes, 1):
        cells = [sc.narration, sc.on_screen_text, sc.visual]
        cells = [c.replace("|", "/").replace("\n", " ") for c in cells]
        lines.append(f"| {i} | {sc.beat} | {cells[0]} | {cells[1]} | {cells[2]} |")
    words = sum(len(sc.narration.split()) for sc in s.scenes)
    lines += ["", f"Spoken words: {words} (about {round(words / 2.6)} seconds)", "",
              f"**Twist:** {s.twist_summary}", "", f"**Thumbnail:** {s.thumbnail_idea}", "",
              "**Hashtags:** " + " ".join(h if h.startswith("#") else f"#{h}" for h in s.hashtags), "",
              "## Other hook options", ""] + [f"- {h}" for h in s.hook_options]
    if r.critiques:
        c = r.critiques[-1]
        lines += ["", "## Comedy critic (final round)", "",
                  f"Hook {c.hook_score} · Humor {c.humor_score} · Twist {c.twist_score} · Loop {c.loop_score} · "
                  f"Approved: {c.approved}"] + [f"- {n}" for n in c.rewrite_notes + c.style_violations]
    if r.fact_check:
        lines += ["", "## Fact-check", "", f"Passed: {r.fact_check.passed}", ""]
        lines += [f"- **{ch.verdict}**: {ch.claim} — {ch.evidence} {ch.source_url}".rstrip()
                  for ch in r.fact_check.checks]
        lines += [f"- Fix needed: {f}" for f in r.fact_check.required_fixes]
    return "\n".join(lines) + "\n"


def save(r: Result, fmt: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", r.script.title.lower()).strip("-")[:60] or r.story["id"]
    md = out_dir / f"{fmt}-{slug}.md"
    md.write_text(to_markdown(r, fmt))
    md.with_suffix(".json").write_text(json.dumps({
        "story": r.story, "status": r.status, "script": r.script.model_dump(),
        "critiques": [c.model_dump() for c in r.critiques],
        "fact_check": r.fact_check.model_dump() if r.fact_check else None,
    }, indent=1))
    return md
