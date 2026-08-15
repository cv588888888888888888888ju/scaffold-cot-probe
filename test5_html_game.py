"""test5_html_game.py - pro builds an HTML5 game under two scaffolds.

A: DSH minimal-aligned (1-line persona, 2 tools: bash + str_replace_editor)
B: full harness (long persona, 11 tools)

Each agent gets its own workdir (A_game/ B_game/) and up to 8 rounds to
create a playable single-file HTML5 game. We compare: did it finish? file
size, round count, reasoning style, tool-call pattern.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import probe_common  # noqa: E402

probe_common.MODEL = "deepseek-v4-pro"

from probe_common import (  # noqa: E402
    MINIMAL_PERSONA, MINIMAL_TOOLS, TOOL_BASH, TOOL_STR_REPLACE,
    run_agent_loop, style_stats, WORKSPACE,
)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME_TASK = (
    "Create a complete single-file HTML5 game at game.html in the current directory. "
    "Make it a snake game: canvas-based, arrow-key controls, score display, "
    "game-over with restart. It must be playable by opening the file in a browser. "
    "Use the tools to write and verify the file."
)

FULL_PERSONA = """You are a senior software engineering agent operating in a general-purpose
assistant harness. You have access to a rich toolset for shell execution, file
operations, code search, web retrieval and process management.

Guidelines:
- Think step by step before acting; plan the smallest change that fixes the root cause.
- Prefer reading code before editing it. Use targeted searches instead of grepping whole trees.
- Run the test suite after any change to confirm the fix; never claim success without evidence.
- When a command fails, read the error carefully and adjust, do not retry blindly.
- Keep edits minimal and idiomatic; preserve existing style and imports.
- If you need information not available locally, you may use web tools, but prefer local evidence first.
- Always report what you changed, why, and the verification result.

You are working in {cwd}.""".format(cwd=BASE)

EXTRA_TOOLS = [
    {"type": "function", "function": {"name": "read_file", "description": "Read a file (absolute path).", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "write_file", "description": "Write a file (absolute path).", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "list_dir", "description": "List a directory.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "search_files", "description": "Search file contents by pattern.", "parameters": {"type": "object", "properties": {"pattern": {"type": "string"}, "path": {"type": "string"}}, "required": ["pattern"]}}},
    {"type": "function", "function": {"name": "patch", "description": "Apply a unified diff to a file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "diff": {"type": "string"}}, "required": ["path", "diff"]}}},
    {"type": "function", "function": {"name": "run_python", "description": "Run a python snippet in the workspace.", "parameters": {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]}}},
    {"type": "function", "function": {"name": "git_status", "description": "Show git status.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "web_search", "description": "Search the web.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "web_extract", "description": "Extract a web page.", "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}},
]
FULL_TOOLS = [TOOL_BASH, TOOL_STR_REPLACE] + EXTRA_TOOLS

HTML_SNIPPETS = {
    "canvas": re.compile(r"<canvas", re.I),
    "script": re.compile(r"<script", re.I),
    "keydown": re.compile(r"keydown|addEventListener", re.I),
    "score": re.compile(r"score", re.I),
    "gameover": re.compile(r"game\s*over|gameover", re.I),
    "restart": re.compile(r"restart|again|space", re.I),
}


def grade_html(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    return {
        "bytes": len(text.encode("utf-8")),
        "checks": {k: bool(p.search(text)) for k, p in HTML_SNIPPETS.items()},
    }


def main():
    results_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
    os.makedirs(results_dir, exist_ok=True)
    configs = [
        ("A_minimal_game", {"system": MINIMAL_PERSONA, "user": GAME_TASK,
                            "tools": MINIMAL_TOOLS, "workdir": os.path.join(BASE, "A_game")}),
        ("B_full_game", {"system": FULL_PERSONA, "user": GAME_TASK,
                         "tools": FULL_TOOLS, "workdir": os.path.join(BASE, "B_game")}),
    ]
    out = {}
    for name, cfg in configs:
        os.makedirs(cfg["workdir"], exist_ok=True)
        print(f"\n{'='*70}\n>>> {name} (deepseek-v4-pro, rounds<=8, workdir={cfg['workdir']})")
        traj = run_agent_loop(cfg["system"], cfg["user"], cfg["tools"],
                              max_rounds=8, workdir=cfg["workdir"])
        rounds = []
        for t in traj:
            rounds.append({
                "round": t["round"],
                "reasoning_chars": len(t["reasoning"]),
                "style": style_stats(t["reasoning"]),
                "tool_calls": t["tool_calls"],
                "content_chars": len(t["content"]),
            })
            print(f"  r{t['round']}: reasoning={len(t['reasoning'])}ch style={style_stats(t['reasoning'])} calls={t['tool_calls']}")
        game = grade_html(os.path.join(cfg["workdir"], "game.html"))
        print(f"  game.html: {game}")
        out[name] = {
            "rounds_used": len(traj),
            "finished_with_reply": traj[-1]["content"] != "",
            "trajectory": rounds,
            "game": game,
        }
        with open(os.path.join(results_dir, f"{name}.json"), "w", encoding="utf-8") as f:
            json.dump(out[name], f, ensure_ascii=False, indent=1)
    print("\nDONE -> results/")


if __name__ == "__main__":
    main()
