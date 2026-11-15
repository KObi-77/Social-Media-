"""The four agents. Each is one focused Claude call with its own role."""

import json
from typing import List, Optional

from .llm import LLM
from .schemas import Critique, FactCheck, Script, TopicPick

FORMATS = {
    "short": "SHORT format: 60-90 seconds, 150-220 spoken words, vertical 9:16. "
    "Beats in order: hook, setup, escalation (several scenes), twist, loop.",
    "long": "LONG format: 8-12 minutes, 1200-1800 spoken words, 16:9. "
    "Use beats hook, setup, act (several), twist, outro.",
}


def _base(style_guide: str, role: str) -> str:
    return f"{role}\n\nThe channel style guide below is binding.\n\n<style_guide>\n{style_guide}\n</style_guide>"


def pick_topic(llm: LLM, style_guide: str, stories: List[dict], recent: List[dict],
               trend_hints: str = "", tradition: Optional[str] = None) -> TopicPick:
    used = {r["story_id"] for r in recent}
    pool = [s for s in stories if s["id"] not in used] or stories
    if tradition:
        pool = [s for s in pool if tradition.lower() in s["tradition"].lower()] or pool
    recent_traditions = [r.get("tradition", "") for r in recent[-5:]]
    prompt = (
        "Pick the ONE story from this library most likely to go viral today, and the angle to tell it.\n"
        f"Avoid repeating these recent traditions back-to-back: {recent_traditions}\n"
        f"Trend signals (may be empty): {trend_hints or 'none'}\n\n"
        f"<library>\n{json.dumps(pool, indent=1)}\n</library>"
    )
    pick = llm.structured(_base(style_guide, "You are the channel's programming director."), prompt, TopicPick, "medium")
    if pick.story_id not in {s["id"] for s in pool}:
        pick.story_id = pool[0]["id"]  # model named something outside the pool; stay safe
    return pick


def write_script(llm: LLM, style_guide: str, story: dict, angle: str, fmt: str,
                 feedback: Optional[List[str]] = None, previous: Optional[Script] = None) -> Script:
    role = ("You are the head writer of a hit animated YouTube/TikTok channel. "
            "You write funny, deadpan retellings of original myths with a true twist.")
    prompt = (
        f"{FORMATS[fmt]}\n\nStory: {json.dumps(story)}\nAngle: {angle}\n\n"
        "Write 10 hook options, choose the strongest as chosen_hook (it must also be the first scene's narration). "
        "List every factual claim the script relies on, with the part of the original source it comes from."
    )
    if previous and feedback:
        prompt += (f"\n\nREVISE this draft. Keep what works, fix every note.\n<draft>\n"
                   f"{previous.model_dump_json(indent=1)}\n</draft>\n<notes>\n- " + "\n- ".join(feedback) + "\n</notes>")
    return llm.structured(_base(style_guide, role), prompt, Script, "high")


def critique(llm: LLM, style_guide: str, script: Script, fmt: str) -> Critique:
    role = ("You are a ruthless comedy editor and short-form retention expert. You have seen a million "
            "myth videos. You approve only scripts that would beat the channel's best video.")
    prompt = (
        f"{FORMATS[fmt]}\n\nScore this script. Approve only if every score is 8 or higher and there are no "
        "style violations. Rewrite notes must be concrete (quote the line, give the better version).\n\n"
        f"<script>\n{script.model_dump_json(indent=1)}\n</script>"
    )
    return llm.structured(_base(style_guide, role), prompt, Critique, "high")


def fact_check(llm: LLM, style_guide: str, story: dict, script: Script) -> FactCheck:
    role = "You are a meticulous fact-checker for a mythology and history channel."
    claims = "\n".join(f"- {c.claim} (cited: {c.source})" for c in script.key_claims)
    notes = llm.research(
        _base(style_guide, role),
        f"Story: {story['title']} — primary source: {story['source']}\n"
        f"Twist: {script.twist_summary}\nClaims to verify:\n{claims}\n\n"
        "Search the web for each claim. Prefer primary-source translations and scholarly sites. "
        "For each claim say supported/disputed/unsupported, with evidence and the best URL.",
    )
    return llm.structured(
        _base(style_guide, role),
        f"Turn these research notes into a verdict. passed=true only if the twist and every claim are supported "
        f"(a claim told as 'in one version' may be disputed).\n\n<notes>\n{notes}\n</notes>\n\nClaims:\n{claims}",
        FactCheck,
        "medium",
    )
