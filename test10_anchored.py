"""test10_anchored.py - anchored-standard replication: round 1 exposes ONLY the
2 minimal tools; from round 2 the FULL 11-tool catalog is swapped in.

Question: does the minimal-anchored we-style trajectory survive the catalog
expansion, or does it flip to let-me style (as plain full-from-start does)?
Also runs the control: full tools from round 1.
"""
import json
import os
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


def main():
    results_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
    os.makedirs(results_dir, exist_ok=True)
    configs = [
        ("anchored_2to11", MINIMAL_TOOLS, FULL_TOOLS,
         os.path.join(BASE, "E_anchored")),
        ("full_from_start", FULL_TOOLS, None,
         os.path.join(BASE, "F_fullstart")),
    ]
    out = {}
    for name, tools_r1, tools_after, workdir in configs:
        os.makedirs(workdir, exist_ok=True)
        print(f"\n{'='*70}\n>>> {name} (r1 tools={len(tools_r1)}, after={len(tools_after) if tools_after else 'same'})")
        traj = run_agent_loop(MINIMAL_PERSONA, GAME_TASK, tools_r1,
                              max_rounds=5, workdir=workdir,
                              tools_after=tools_after, swap_after_round=1)
        rounds = []
        for t in traj:
            st = style_stats(t["reasoning"])
            rounds.append({"round": t["round"], "reasoning_chars": len(t["reasoning"]),
                           "we": st["we"], "let_me": st["let me"], "let_s": st["let's"],
                           "tool_calls": t["tool_calls"]})
            print(f"  r{t['round']}: reasoning={len(t['reasoning'])}ch we={st['we']} let_me={st['let me']} let's={st['let\'s']} calls={t['tool_calls']}")
        tot_we = sum(r["we"] for r in rounds)
        tot_lm = sum(r["let_me"] for r in rounds)
        print(f"  TOTAL: we={tot_we} let_me={tot_lm}")
        out[name] = {"rounds": rounds, "totals": {"we": tot_we, "let_me": tot_lm}}
        with open(os.path.join(results_dir, f"{name}.json"), "w", encoding="utf-8") as f:
            json.dump(out[name], f, ensure_ascii=False, indent=1)
    print("\nDONE -> results/anchored_*.json")


if __name__ == "__main__":
    main()
