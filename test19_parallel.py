"""test19_parallel.py - run the decompose matrix with PARALLEL agents
(ThreadPoolExecutor, max_workers=4), simulating production multi-agent load.
Compares against serial baselines (test18 1a_r0) for behavior/timing/errors.

16 tasks (8 cells x 2 reps). Each cell writes its result incrementally.
"""
import json
import os
import re
import shutil
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import probe_common  # noqa: E402

probe_common.MODEL = "deepseek-v4-pro"

from probe_common import (  # noqa: E402
    MINIMAL_PERSONA, MINIMAL_TOOLS, TOOL_BASH, TOOL_STR_REPLACE,
    run_agent_loop, WORKSPACE,
)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL_LIB = os.path.join(BASE, "tools_lib")
GAME_TASK = (
    "Create a complete single-file HTML5 game at game.html in the current directory. "
    "Make it a snake game: canvas-based, arrow-key controls, score display, "
    "game-over with restart. It must be playable by opening the file in a browser. "
    "Use the tools to write and verify the file."
)
DECOMPOSE = (
    " Before you start working, fully decompose the requirements: list all "
    "sub-requirements, technical decisions, and verification steps. "
    "Only start working after the decomposition is complete, and follow it."
)
STANDARD_PERSONA = (
    "You are a senior software engineering agent operating in a general-purpose assistant harness. "
    "You have access to a rich toolset for shell execution, file operations, code search, "
    "web retrieval and process management. "
    "Guidelines: think step by step before acting; plan the smallest change that fixes the root cause; "
    "prefer reading code before editing; run verification after any change; never claim success without evidence. "
    "You are working in " + BASE + "."
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

WE_RE = re.compile(r"\bwe\b|\bour\b|\bus\b|\blet'?s\b", re.I)
I_RE = re.compile(r"\bI\b|\bI'|\bmy\b|\bmine\b|\blet me\b")
ERR_RE = re.compile(r"\[stderr\]|command not found|not recognized|No such file|Traceback|Error", re.I)

CELLS = [
    ("1a_std_dec", STANDARD_PERSONA, FULL_TOOLS, True, False, False),
    ("1b_std_base", STANDARD_PERSONA, FULL_TOOLS, False, False, False),
    ("2a_min_dec", MINIMAL_PERSONA, MINIMAL_TOOLS, True, False, False),
    ("2b_min_base", MINIMAL_PERSONA, MINIMAL_TOOLS, False, False, False),
    ("3a_lib_dec", MINIMAL_PERSONA, MINIMAL_TOOLS, True, True, False),
    ("3b_lib_base", MINIMAL_PERSONA, MINIMAL_TOOLS, False, True, False),
    ("4a_anch_dec", MINIMAL_PERSONA, MINIMAL_TOOLS, True, False, True),
    ("4b_anch_base", MINIMAL_PERSONA, MINIMAL_TOOLS, False, False, True),
]

_lock = threading.Lock()
_results = {}


def run_one(label, persona, tools, user, workdir, tools_after):
    t_start = time.time()
    err = None
    try:
        traj = run_agent_loop(persona, user, tools, max_rounds=6, workdir=workdir,
                              reasoning_effort="high", tools_after=tools_after, swap_after_round=1)
    except Exception as e:
        traj = []
        err = str(e)[:300]
    wall = time.time() - t_start
    tot_we = tot_i = tot_err = 0
    api_ms = tool_ms = 0
    prompt_tok = comp_tok = 0
    first_write = None
    rounds = []
    for t in traj:
        we, i = selfref(t["reasoning"])
        tot_we += we; tot_i += i
        api_ms += t.get("api_wall_ms", 0); tool_ms += t.get("tool_wall_ms", 0)
        u = t.get("usage", {})
        prompt_tok += u.get("prompt_tokens", 0); comp_tok += u.get("completion_tokens", 0)
        for r in t.get("tool_results", []):
            if ERR_RE.search(r.get("output", "")):
                tot_err += 1
        calls_str = " ".join(t["tool_calls"])
        if first_write is None and "game.html" in calls_str and "write" in calls_str.lower():
            first_write = t["round"]
        rounds.append({"round": t["round"], "reasoning_chars": len(t.get("reasoning", "")),
                       "api_ms": t.get("api_wall_ms", 0), "tool_ms": t.get("tool_wall_ms", 0),
                       "tool_calls": t["tool_calls"]})
    produced = os.path.exists(os.path.join(workdir, "game.html"))
    total = tot_we + tot_i
    res = {
        "label": label, "produced": produced, "first_write_round": first_write,
        "rounds_used": len(traj), "we": tot_we, "i": tot_i,
        "ratio": round(tot_we / total, 2) if total else None,
        "errs": tot_err, "api_wall_s": round(api_ms / 1000, 1),
        "tool_wall_s": round(tool_ms / 1000, 1), "total_wall_s": round(wall, 1),
        "prompt_tokens": prompt_tok, "completion_tokens": comp_tok,
        "error": err, "rounds": rounds,
    }
    return res


def selfref(text):
    we = len(WE_RE.findall(text or ""))
    i = len(I_RE.findall(text or ""))
    return we, i


def main():
    results_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
    os.makedirs(results_dir, exist_ok=True)
    tasks = []
    for label, persona, tools, dec, lib, anch in CELLS:
        for rep in range(2):
            key = f"{label}_r{rep}"
            user = GAME_TASK + (DECOMPOSE if dec else "")
            workdir = os.path.join(BASE, f"par_{label}", f"rep{rep}")
            if os.path.exists(workdir):
                shutil.rmtree(workdir)
            os.makedirs(workdir, exist_ok=True)
            if lib:
                shutil.copytree(TOOL_LIB, os.path.join(workdir, "tools_lib"))
            tasks.append((key, persona, tools, user, workdir, FULL_TOOLS if anch else None))

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(run_one, *t): t[0] for t in tasks}
        for fut in as_completed(futs):
            key = futs[fut]
            try:
                res = fut.result()
            except Exception as e:
                res = {"label": key, "error": str(e)[:300]}
            with _lock:
                _results[key] = res
                with open(os.path.join(results_dir, "test19_parallel.json"), "w", encoding="utf-8") as f:
                    json.dump(_results, f, ensure_ascii=False, indent=1)
            print(f"[{key}] done: produced={res.get('produced')} ratio={res.get('ratio')} "
                  f"wall={res.get('total_wall_s')}s errs={res.get('errs')} err={res.get('error')}")
    total = time.time() - t0
    print(f"\nPARALLEL (4 workers) total wall: {round(total, 1)}s for {len(tasks)} tasks")
    print("DONE -> results/test19_parallel.json")


if __name__ == "__main__":
    main()
