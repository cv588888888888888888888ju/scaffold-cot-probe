"""test1_minimal_vs_full.py - A/B: DSH minimal-aligned scaffold vs full harness scaffold.

Both runs answer the SAME task with the SAME model (deepseek-v4-pro,
reasoning_effort=max, thinking enabled). Only the scaffold differs:
- A: DSH minimal verbatim (1-line persona, complete:true, 2 tools, no injection)
- B: typical third-party harness (long persona, 10 tools, AGENTS.md/skill injection)
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from probe_common import (  # noqa: E402
    MINIMAL_PERSONA, MINIMAL_TOOLS, TOOL_BASH, TOOL_STR_REPLACE,
    call_once, run_agent_loop, style_stats, WORKSPACE,
)

USER_TASK = (
    "Work in the current directory. The test suite has a failure. "
    "Diagnose the root cause, fix the bug, and verify the tests pass. Use the available tools."
)

# --------------------------------------------------------------------------
# Scaffold B: "full harness" style - long persona + 10 tools + injected context
# --------------------------------------------------------------------------

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

You are working in {cwd}. The repository layout and project conventions are described
in AGENTS.md (summary injected below). Skills are available; consult the catalog when a
specialized workflow applies, but do not call a skill for trivial operations.""".format(cwd=WORKSPACE)

AGENTS_MD_INJECTION = (
    "[AGENTS.md summary] stats_lib is a pure-python library; tests live in tests/ and run via "
    "`python -m unittest discover -s tests -v`. No external deps. Keep API backwards compatible."
)
SKILL_CATALOG_INJECTION = (
    "[skill catalog] Available skills: python-debugging, unit-testing, git-workflow, "
    "code-review, dependency-check. Read the relevant skill before complex operations."
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

FULL_USER = AGENTS_MD_INJECTION + "\n" + SKILL_CATALOG_INJECTION + "\n\n" + USER_TASK


def main():
    os.makedirs("results", exist_ok=True)
    configs = {
        "A_minimal": {"system": MINIMAL_PERSONA, "user": USER_TASK, "tools": MINIMAL_TOOLS},
        "B_full": {"system": FULL_PERSONA, "user": FULL_USER, "tools": FULL_TOOLS},
    }
    summary = {}
    for name, cfg in configs.items():
        print(f"\n{'='*70}\n>>> {name}: persona={len(cfg['system'])} chars, tools={len(cfg['tools'])}")
        # first-round reasoning (verbatim capture)
        r1 = call_once(cfg["system"], cfg["user"], cfg["tools"])
        m1 = r1["choices"][0]["message"]
        reason1 = m1.get("reasoning_content", "")
        print(f"  round1 reasoning chars: {len(reason1)}")
        print(f"  round1 style: {style_stats(reason1)}")
        print(f"  round1 content chars: {len(m1.get('content') or '')}")
        # full trajectory (up to 4 rounds, real local tool execution)
        traj = run_agent_loop(cfg["system"], cfg["user"], cfg["tools"], max_rounds=4)
        rounds_info = []
        for t in traj:
            rounds_info.append({
                "round": t["round"],
                "reasoning_chars": len(t["reasoning"]),
                "style": style_stats(t["reasoning"]),
                "tool_calls": t["tool_calls"],
                "content_chars": len(t["content"]),
            })
        for t in traj:
            print(f"  r{t['round']}: reasoning={len(t['reasoning'])}ch calls={t['tool_calls']}")
        summary[name] = {
            "persona_chars": len(cfg["system"]),
            "tool_count": len(cfg["tools"]),
            "round1_reasoning_chars": len(reason1),
            "round1_style": style_stats(reason1),
            "trajectory": rounds_info,
            "round1_reasoning_text": reason1,
        }
        with open(f"results/{name}.json", "w", encoding="utf-8") as f:
            json.dump(summary[name], f, ensure_ascii=False, indent=1)
    print("\n" + "=" * 70)
    print("DONE. Results in scripts/results/")


if __name__ == "__main__":
    main()
