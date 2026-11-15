"""Structured outputs the agents return. Claude is constrained to these shapes."""

from typing import List, Literal

from pydantic import BaseModel, Field


class TopicPick(BaseModel):
    story_id: str = Field(description="id of the chosen story from the library")
    angle: str = Field(description="The specific funny/surprising angle for this episode")
    why_it_will_work: str


class Scene(BaseModel):
    beat: Literal["hook", "setup", "escalation", "twist", "loop", "act", "outro"]
    narration: str = Field(description="Exact words the narrator says")
    on_screen_text: str = Field(description="Caption or gag text shown on screen; empty if none")
    visual: str = Field(description="What the animation shows, for the art step")


class Claim(BaseModel):
    claim: str = Field(description="A factual claim the script makes about the source")
    source: str = Field(description="Where in the original this comes from")


class Script(BaseModel):
    title: str = Field(description="Video title, under 70 characters")
    hook_options: List[str] = Field(description="10 alternative opening lines")
    chosen_hook: str
    scenes: List[Scene]
    twist_summary: str
    key_claims: List[Claim]
    hashtags: List[str]
    thumbnail_idea: str


class Critique(BaseModel):
    hook_score: int = Field(description="1-10: would this stop a scroll in 3 seconds?")
    humor_score: int = Field(description="1-10: joke density and quality")
    twist_score: int = Field(description="1-10: surprising yet earned")
    loop_score: int = Field(description="1-10: does the ending lead back to the start?")
    style_violations: List[str] = Field(description="Breaks of the style guide's hard rules")
    rewrite_notes: List[str] = Field(description="Specific, actionable fixes")
    approved: bool


class ClaimCheck(BaseModel):
    claim: str
    verdict: Literal["supported", "disputed", "unsupported"]
    evidence: str
    source_url: str = Field(description="Best supporting URL, empty if none")


class FactCheck(BaseModel):
    checks: List[ClaimCheck]
    passed: bool = Field(description="True only if the twist and every key claim are supported")
    required_fixes: List[str]
