"""Offline tests: a fake model stands in for Claude, so no API key or cost."""

import datetime as dt
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from mythstudio import pipeline
from mythstudio.llm import LLM, LLMError
from mythstudio.schemas import Claim, ClaimCheck, Critique, FactCheck, Scene, Script, TopicPick

ROOT = Path(__file__).resolve().parent.parent


def make_script(title="Thor Wore A Wedding Dress | It Worked"):
    return Script(
        title=title, hook_options=["h"] * 10, chosen_hook="The strongest god once wore a wedding dress.",
        scenes=[Scene(beat="hook", narration="The strongest god once wore a wedding dress.",
                      on_screen_text="", visual="Thor in veil")],
        twist_summary="The hammer is placed in the bride's lap.",
        key_claims=[Claim(claim="Thor dresses as Freyja", source="Thrymskvida")],
        hashtags=["myth", "#norse"], thumbnail_idea="Thor in a veil",
    )


class FakeLLM:
    """Critic rejects once, then approves. Fact-check fails once, then passes."""

    def __init__(self):
        self.calls, self.critic_calls, self.fact_calls = [], 0, 0

    def structured(self, system, prompt, schema, effort="high"):
        self.calls.append(schema.__name__)
        if schema is TopicPick:
            return TopicPick(story_id="thor-wedding-dress", angle="deadpan", why_it_will_work="absurd")
        if schema is Script:
            return make_script()
        if schema is Critique:
            self.critic_calls += 1
            ok = self.critic_calls > 1
            return Critique(hook_score=9, humor_score=9 if ok else 5, twist_score=9, loop_score=9,
                            style_violations=[], rewrite_notes=[] if ok else ["more jokes"], approved=ok)
        if schema is FactCheck:
            self.fact_calls += 1
            ok = self.fact_calls > 1
            return FactCheck(checks=[ClaimCheck(claim="Thor dresses as Freyja", verdict="supported",
                                                evidence="Thrymskvida st. 15-19", source_url="")],
                             passed=ok, required_fixes=[] if ok else ["fix claim"])
        raise AssertionError(schema)

    def research(self, system, prompt, effort="medium"):
        self.calls.append("research")
        return "notes"


@pytest.fixture
def workdir(tmp_path):
    shutil.copy(ROOT / "style_guide.md", tmp_path)
    (tmp_path / "data").mkdir()
    shutil.copy(ROOT / "data" / "stories.json", tmp_path / "data")
    return tmp_path


def test_full_pipeline(workdir):
    llm = FakeLLM()
    r = pipeline.run(llm, "short", root=workdir, date=dt.date(2026, 11, 15))
    assert r.status == "ready"
    assert llm.calls == ["TopicPick", "Script", "Critique", "Script", "Critique",
                         "research", "FactCheck", "Script", "research", "FactCheck"]
    md = r.path.read_text()
    assert r.path.parent.name == "2026-11-15" and "Thor in a wedding dress" in md and "#norse" in md
    assert "##norse" not in md
    assert json.loads(r.path.with_suffix(".json").read_text())["status"] == "ready"
    history = json.loads((workdir / "data" / "history.json").read_text())
    assert history[-1]["story_id"] == "thor-wedding-dress"


def test_unapproved_script_needs_review(workdir):
    llm = FakeLLM()
    llm.critic_calls = -100  # critic never approves
    r = pipeline.run(llm, "short", max_rounds=2, root=workdir)
    assert r.status == "needs_review" and len(r.critiques) == 2


def test_stories_library_is_valid():
    stories = json.loads((ROOT / "data" / "stories.json").read_text())
    ids = [s["id"] for s in stories]
    assert len(ids) == len(set(ids))
    assert all({"id", "title", "tradition", "source", "premise"} <= s.keys() for s in stories)


def test_schemas_convert_for_structured_outputs():
    from anthropic.resources.beta.messages.messages import to_json_output_format
    for schema in (TopicPick, Script, Critique, FactCheck):
        fmt = to_json_output_format(schema)
        assert fmt["type"] == "json_schema"


def _resp(stop, blocks):
    return SimpleNamespace(stop_reason=stop, stop_details=None, content=blocks, parsed_output="ok")


def test_llm_sends_fallbacks_and_resumes_pause_turn():
    sent = []
    replies = iter([_resp("pause_turn", [SimpleNamespace(type="text", text="part 1")]),
                    _resp("end_turn", [SimpleNamespace(type="text", text="part 2")])])
    messages = SimpleNamespace(create=lambda **kw: sent.append(kw) or next(replies),
                               parse=lambda **kw: sent.append(kw) or _resp("end_turn", []))
    llm = LLM(client=SimpleNamespace(beta=SimpleNamespace(messages=messages)))
    assert llm.research("sys", "q") == "part 1\npart 2"
    assert len(sent) == 2 and sent[1]["messages"][-1]["role"] == "assistant"
    assert sent[0]["fallbacks"] == "default" and sent[0]["model"] == "claude-opus-5-5"
    assert llm.structured("sys", "q", TopicPick) == "ok"
    with pytest.raises(LLMError):
        LLM._check(_resp("refusal", []))
