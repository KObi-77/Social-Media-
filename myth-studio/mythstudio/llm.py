"""Thin wrapper around the Anthropic SDK used by every agent."""

import os
from typing import Type, TypeVar

import anthropic
from pydantic import BaseModel

MODEL = os.environ.get("MYTH_STUDIO_MODEL", "claude-opus-5-5")
FALLBACK_BETA = "server-side-fallback-2026-07-01"
WEB_SEARCH = {"type": "web_search_20260209", "name": "web_search", "max_uses": 8}

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    pass


class LLM:
    """Two calls: `structured` (JSON in a fixed shape) and `research` (web search, text)."""

    def __init__(self, client=None, model: str = MODEL):
        self.client = client or anthropic.Anthropic()
        self.model = model

    def _common(self, system: str, effort: str) -> dict:
        return dict(
            model=self.model,
            system=system,
            output_config={"effort": effort},
            # If a safety classifier declines, the API retries on a fallback model.
            betas=[FALLBACK_BETA],
            fallbacks="default",
        )

    @staticmethod
    def _check(resp) -> None:
        if resp.stop_reason == "refusal":
            details = getattr(resp, "stop_details", None)
            raise LLMError(f"Model declined: {getattr(details, 'explanation', '') or 'no details'}")
        if resp.stop_reason == "max_tokens":
            raise LLMError("Response was cut off (max_tokens).")

    def structured(self, system: str, prompt: str, schema: Type[T], effort: str = "high") -> T:
        resp = self.client.beta.messages.parse(
            max_tokens=16000,
            messages=[{"role": "user", "content": prompt}],
            output_format=schema,
            **self._common(system, effort),
        )
        self._check(resp)
        if resp.parsed_output is None:
            raise LLMError("No structured output returned.")
        return resp.parsed_output

    def research(self, system: str, prompt: str, effort: str = "medium") -> str:
        messages = [{"role": "user", "content": prompt}]
        texts = []
        for _ in range(5):
            resp = self.client.beta.messages.create(
                max_tokens=16000, messages=messages, tools=[WEB_SEARCH], **self._common(system, effort)
            )
            texts += [b.text for b in resp.content if b.type == "text"]
            if resp.stop_reason != "pause_turn":
                break
            # A long web-search turn paused; send it back so the server continues it.
            messages = messages + [{"role": "assistant", "content": resp.content}]
        else:
            raise LLMError("Research did not finish after 5 resumes.")
        self._check(resp)
        return "\n".join(texts)
