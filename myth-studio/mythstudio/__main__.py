"""Usage: python -m mythstudio [--format short|long] [--count N] [--tradition Norse] [--trends "..."]"""

import argparse
import sys

from . import pipeline
from .llm import LLM, LLMError


def main() -> int:
    p = argparse.ArgumentParser(description="Generate fact-checked, funny myth video scripts.")
    p.add_argument("--format", choices=["short", "long"], default="short")
    p.add_argument("--count", type=int, default=1, help="How many scripts to make")
    p.add_argument("--tradition", help="Limit to a tradition, e.g. African, Norse, Japanese, Greek, Grimm")
    p.add_argument("--trends", default="", help="Trend notes to steer topic choice")
    p.add_argument("--rounds", type=int, default=3, help="Max critic rewrite rounds")
    a = p.parse_args()

    llm = LLM()
    failures = 0
    for i in range(a.count):
        try:
            r = pipeline.run(llm, a.format, a.tradition, a.trends, a.rounds)
            print(f"[{r.status}] {r.path}")
        except LLMError as e:
            failures += 1
            print(f"Script {i + 1} failed: {e}", file=sys.stderr)
    return 1 if failures == a.count else 0


if __name__ == "__main__":
    sys.exit(main())
