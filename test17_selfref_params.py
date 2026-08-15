"""test17_selfref_params.py - self-reference (we vs I) across tool count and
sampling params, minimal persona fixed, deepseek-v4-pro.

Part A (application mode, 6 rounds, n=2): tools 2 / 11 / 25 -> self-ref ratio
  plus quality (errs, produced, first-write). Tests "we self-reference grows
  quality" community claim.
Part B (single round, n=2): params sweep -> reasoning_effort low/max,
  temperature 0.0/1.0, thinking off. Tests whether sampling params shift
  self-reference.
"""
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import probe_common  # noqa: E402

probe_common.MODEL = "deepseek-v4-pro"

from probe_common import (  # noqa: E402
    MINIMAL_PERSONA, MINIMAL_TOOLS, TOOL_BASH, TOOL_STR_REPLACE,
    call_once, run_agent_loop, style_stats, WORKSPACE,
)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME_TASK = (
    "Create a complete single-file HTML5 game at game.html in the current directory. "
    "Make it a snake game: canvas-based, arrow-key controls, score display, "
    "game-over with restart. It must be playable by opening the file in a browser. "
    "Use the tools to write and verify the file."
)

WE_RE = re.compile(r"\bwe\b|\bour\b|\bus\b|\blet'?s\b", re.I)
I_RE = re.compile(r"\bI\b|\bI'|\bmy\b|\bmine\b|\blet me\b")
ERR_RE = re.compile(r"\[stderr\]|command not found|not recognized|No such file|Traceback|Error", re.I)


def selfref(text):
    we = len(WE_RE.findall(text or ""))
    i = len(I_RE.findall(text or ""))
    total = we + i
    return {"we": we, "i": i, "ratio": round(we / total, 2) if total else None}


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
T11 = [TOOL_BASH, TOOL_STR_REPLACE] + EXTRA_TOOLS
T25 = list(T11) + [
    {"type": "function", "function": {"name": "docker_exec", "description": "Exec in container.", "parameters": {"type": "object", "properties": {"container": {"type": "string"}, "command": {"type": "string"}}, "required": ["container", "command"]}}},
    {"type": "function", "function": {"name": "db_query", "description": "Run SQL query.", "parameters": {"type": "object", "properties": {"sql": {"type": "string"}}, "required": ["sql"]}}},
    {"type": "function", "function": {"name": "task_decompose", "description": "Split task into subtasks.", "parameters": {"type": "object", "properties": {"goal": {"type": "string"}}, "required": ["goal"]}}},
    {"type": "function", "function": {"name": "delegate_subagent", "description": "Spawn subagent.", "parameters": {"type": "object", "properties": {"goal": {"type": "string"}}, "required": ["goal"]}}},
    {"type": "function", "function": {"name": "todo_write", "description": "Write todo list.", "parameters": {"type": "object", "properties": {"items": {"type": "array", "items": {"type": "string"}}}, "required": ["items"]}}},
    {"type": "function", "function": {"name": "ask_user", "description": "Ask the user a question.", "parameters": {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]}}},
    {"type": "function", "function": {"name": "memory_save", "description": "Save to memory.", "parameters": {"type": "object", "properties": {"content": {"type": "string"}}, "required": ["content"]}}},
    {"type": "function", "function": {"name": "calendar_check", "description": "Check calendar.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "email_send", "description": "Send email.", "parameters": {"type": "object", "properties": {"to": {"type": "string"}, "subject": {"type": "string"}}, "required": ["to"]}}},
    {"type": "function", "function": {"name": "notify_push", "description": "Push notification.", "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}}},
    {"type": "function", "function": {"name": "tts_speak", "description": "Text to speech.", "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}}},
    {"type": "function", "function": {"name": "http_get", "description": "HTTP GET.", "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}},
    {"type": "function", "function": {"name": "http_post", "description": "HTTP POST.", "parameters": {"type": "object", "properties": {"url": {"type": "string"}, "json": {"type": "object"}}, "required": ["url"]}}},
]


def part_a():
    print("=== PART A: self-ref vs tool count (6 rounds, n=2) ===")
    out = {}
    for label, tools, sub in [("t2", MINIMAL_TOOLS, "R_t2"), ("t11", T11, "S_t11"), ("t25", T25, "T_t25")]:
        runs = []
        for rep in range(2):
            workdir = os.path.join(BASE, sub, f"rep{rep}")
            if os.path.exists(workdir):
                shutil.rmtree(workdir)
            os.makedirs(workdir, exist_ok=True)
            traj = run_agent_loop(MINIMAL_PERSONA, GAME_TASK, tools, max_rounds=6, workdir=workdir)
            agg_we = agg_i = errs = 0
            first_write = None
            for t in traj:
                sr = selfref(t["reasoning"])
                agg_we += sr["we"]; agg_i += sr["i"]
                for r in t.get("tool_results", []):
                    if ERR_RE.search(r.get("output", "")):
                        errs += 1
                if first_write is None and "game.html" in " ".join(t["tool_calls"]) and "write" in " ".join(t["tool_calls"]).lower():
                    first_write = t["round"]
            produced = os.path.exists(os.path.join(workdir, "game.html"))
            total = agg_we + agg_i
            ratio = round(agg_we / total, 2) if total else None
            runs.append({"rep": rep, "we": agg_we, "i": agg_i, "ratio": ratio,
                         "errs": errs, "produced": produced, "first_write": first_write,
                         "rounds": len(traj)})
            print(f"  [{label} rep{rep}] we={agg_we} i={agg_i} ratio={ratio} errs={errs} produced={produced} fw={first_write}")
        out[label] = runs
    return out


def part_b():
    print("\n=== PART B: self-ref vs params (single round, n=2) ===")
    cells = [
        ("effort_low", dict(reasoning_effort="low")),
        ("effort_max", dict(reasoning_effort="max")),
        ("temp_0.0", dict(temperature=0.0)),
        ("temp_1.0", dict(temperature=1.0)),
        ("think_off", dict(thinking=False)),
    ]
    out = {}
    for label, kw in cells:
        rows = []
        for rep in range(2):
            r = call_once(MINIMAL_PERSONA, GAME_TASK, MINIMAL_TOOLS, **kw)
            m = r["choices"][0]["message"]
            reason = m.get("reasoning_content", "") or ""
            content = m.get("content") or ""
            sr = selfref(reason + " " + content)
            rows.append({"rep": rep, "we": sr["we"], "i": sr["i"], "ratio": sr["ratio"],
                         "reasoning_chars": len(reason), "content_chars": len(content)})
            print(f"  [{label} rep{rep}] we={sr['we']} i={sr['i']} ratio={sr['ratio']} reasoning={len(reason)}ch content={len(content)}ch")
        out[label] = rows
    return out


def main():
    results_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
    os.makedirs(results_dir, exist_ok=True)
    res = {"partA_tools": part_a(), "partB_params": part_b()}
    with open(os.path.join(results_dir, "test17_selfref_params.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print("\nDONE -> results/test17_selfref_params.json")


if __name__ == "__main__":
    main()
