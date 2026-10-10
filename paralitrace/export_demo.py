"""Pack the current forecast into a static snapshot for the hosted demo (e.g. Vercel).

    py -m paralitrace.export_demo

Copies output/latest.json and output/backtest.json into frontend/public/demo/ and records the
assistant's answers (with their Strands tool calls) to the three example questions, so the hosted
page can show them without a server or an API key. Re-run after changing the forecast on screen.
"""
from __future__ import annotations

import json
import os
import shutil

from .config import OUTPUT_DIR

ROOT = os.path.join(os.path.dirname(__file__), "..")
DEMO_DIR = os.path.join(ROOT, "frontend", "public", "demo")

# Keep identical to EXAMPLES in frontend/src/components/AskPane.tsx (a test checks this).
EXAMPLES = [
    "Which cities get the worst smoke tomorrow, and why?",
    "Write a school advisory for Ludhiana in Punjabi.",
    "Where should Punjab send 200 machines tomorrow?",
]


def export(record_answers: bool = True, out_dir: str = DEMO_DIR) -> list[str]:
    os.makedirs(out_dir, exist_ok=True)
    written = []
    for name in ("latest.json", "backtest.json"):
        src = os.path.join(OUTPUT_DIR, name)
        if os.path.exists(src):
            shutil.copyfile(src, os.path.join(out_dir, name))
            written.append(name)
    if "latest.json" not in written:
        raise SystemExit("No forecast to export. Run the pipeline first.")

    if record_answers:
        from .agent import NoModelConfigured, ask_with_trace
        answers = []
        for q in EXAMPLES:
            try:
                print(f"  recording: {q}")
                a, tools = ask_with_trace(q)
                answers.append({"question": q, "answer": a, "tools": tools})
            except NoModelConfigured as e:
                print(f"  skipped answers: {e}")
                break
            except Exception as e:  # one failed question shouldn't block the rest
                print(f"  could not record '{q}': {e}")
        if answers:
            with open(os.path.join(out_dir, "answers.json"), "w", encoding="utf-8") as f:
                json.dump(answers, f, ensure_ascii=False)
            written.append("answers.json")
    return written


def main():
    files = export()
    print("Snapshot written to frontend/public/demo: " + ", ".join(files))


if __name__ == "__main__":
    main()
