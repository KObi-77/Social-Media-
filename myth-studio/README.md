# Myth Studio

A team of AI agents (built on Claude) that writes one funny, twisty, **fact-checked**
video script a day for an "Untold Origins" channel: the real, often darker or stranger
versions of African, Norse, Japanese and Greek myths, original fairy tales, and odd history.

## How it works

```
Topic Picker → Writer (10 hooks + draft) → Comedy Critic ⇄ Writer (up to 3 rounds)
            → Fact-Checker (web search) → Writer fixes → saved script
```

| Agent | Job |
|---|---|
| Topic Picker | Chooses a story from `data/stories.json`, skipping the last 30 used and rotating traditions. |
| Writer | Writes the script in the hook → setup → escalation → twist → loop format, with narration, on-screen gags and visual notes for each scene. |
| Comedy Critic | Scores hook, humor, twist and loop from 1 to 10 and sends rewrite notes until every score is 8+. |
| Fact-Checker | Searches the web to confirm the twist and every claim against real sources. |

Each run saves `output/<date>/<format>-<title>.md` (easy to read and record from) and a
`.json` version for later steps (voice, animation). A script is marked **ready** when
the critic approved it and the fact-check passed. Otherwise it's marked **needs_review**.

## Setup

1. Get a Claude API key at <https://platform.claude.com>.
2. Install and run:

```bash
cd myth-studio
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...

python -m mythstudio                          # one short (60-90s)
python -m mythstudio --format long            # one 8-12 minute YouTube script
python -m mythstudio --count 5 --tradition African
python -m mythstudio --trends "Anansi videos trending this week"
```

Tests run offline, with no key and no cost: `python -m pytest -q`

## Customize

- **Voice, jokes, format, rules:** edit `style_guide.md`. Every agent reads it.
- **Stories:** add entries to `data/stories.json` (`id`, `title`, `tradition`, `source`, `premise`).
- **Model:** set `MYTH_STUDIO_MODEL` (default `claude-opus-5-5`).

## Cost

Each script takes about 8–12 Claude calls, including web searches. Expect roughly
$0.30–$1.00 per short script and somewhat more for long ones. Check the usage page in
the Claude Console after your first runs.

## Roadmap

1. **This step:** scripts.
2. Voice: text-to-speech or your own recording, saved per scene.
3. Visuals: image generation from each scene's `visual` field with a fixed character style sheet, then motion and captions with ffmpeg.
4. Trend Scout: YouTube Data API for top myth/history videos, passed in as `--trends`.
5. Publishing through a scheduler (Buffer, Metricool) and an analytics feedback loop.
