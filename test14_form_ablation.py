"""test14_form_ablation.py - FORM ablation on the minimal persona.

Semantics held constant ("helpful software engineer assistant"), surface form
varies: word form, word order, capitalization, sentence splitting, paraphrase.

If behavior tracks SEMANTICS, all variants behave like the original.
If behavior tracks SURFACE FORM (field/string matching to RL training data),
variants diverge sharply from the exact training string.
n=3 per cell, minimal 2 tools, round-1 sampling.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import probe_common  # noqa: E402

probe_common.MODEL = "deepseek-v4-pro"

from probe_common import MINIMAL_TOOLS, call_once, style_stats  # noqa: E402

GAME_TASK = (
    "Create a complete single-file HTML5 game at game.html in the current directory. "
    "Make it a snake game: canvas-based, arrow-key controls, score display, "
    "game-over with restart. It must be playable by opening the file in a browser. "
    "Use the tools to write and verify the file."
)

VARIANTS = [
    ("orig_exact", "You are a helpful software engineer assistant."),
    ("v_ing_form", "You are a helpful software engineering assistant."),
    ("v_word_order", "You are a software engineer assistant that is helpful."),
    ("v_caps", "You are a Helpful Software Engineer Assistant."),
    ("v_split", "You are helpful. You are a software engineer assistant."),
    ("v_paraphrase", "You are an assistant for software engineering who is always helpful."),
]

N = 3


def main():
    results_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
    os.makedirs(results_dir, exist_ok=True)
    out = {}
    for key, persona in VARIANTS:
        rows = []
        print(f">>> {key}: {persona!r}")
        for i in range(N):
            r = call_once(persona, GAME_TASK, MINIMAL_TOOLS)
            m = r["choices"][0]["message"]
            reason = m.get("reasoning_content", "")
            st = style_stats(reason)
            calls = [c["function"]["name"] for c in (m.get("tool_calls") or [])]
            rows.append({"chars": len(reason), "we": st["we"], "let_me": st["let me"],
                         "let_s": st["let's"], "n_calls": len(calls), "calls": calls})
            print(f"  [#{i}] chars={len(reason)} we={st['we']} let_me={st['let me']} let's={st['let\'s']} calls={len(calls)} {calls}")
        avg = {k: round(sum(x[k] for x in rows) / N, 2) for k in ("chars", "we", "let_me", "let_s", "n_calls")}
        out[key] = {"persona": persona, "samples": rows, "avg": avg}
        print(f"  avg: {avg}")
    with open(os.path.join(results_dir, "test14_form_ablation.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("\nDONE -> results/test14_form_ablation.json")


if __name__ == "__main__":
    main()
