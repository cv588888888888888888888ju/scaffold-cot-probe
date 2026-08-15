"""test2_tool_count.py - tool-catalog-size sweep (0 / 2 / 10 / 25 tools).

Fixed persona = DSH minimal verbatim ("You are a helpful software engineer
assistant."). Only the tool catalog size changes. Question: does the CoT
style/length shift with the number of visible tools?
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from probe_common import (  # noqa: E402
    MINIMAL_PERSONA, MINIMAL_TOOLS, TOOL_BASH, TOOL_STR_REPLACE,
    call_once, style_stats,
)

USER_TASK = (
    "Work in the current directory. The test suite has a failure. "
    "Diagnose the root cause, fix the bug, and verify the tests pass. Use the available tools."
)

TEN_TOOLS = MINIMAL_TOOLS + [
    {"type": "function", "function": {"name": "read_file", "description": "Read a file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "write_file", "description": "Write a file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "list_dir", "description": "List directory entries.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "search_files", "description": "Grep contents.", "parameters": {"type": "object", "properties": {"pattern": {"type": "string"}}, "required": ["pattern"]}}},
    {"type": "function", "function": {"name": "run_python", "description": "Run python snippet.", "parameters": {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]}}},
    {"type": "function", "function": {"name": "git_status", "description": "Git status.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "git_diff", "description": "Git diff.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "run_tests", "description": "Run the test suite.", "parameters": {"type": "object", "properties": {"suite": {"type": "string"}}, "required": ["suite"]}}},
]

TWENTYFIVE_TOOLS = list(TEN_TOOLS) + [
    {"type": "function", "function": {"name": "web_search", "description": "Web search.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "web_extract", "description": "Fetch URL.", "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}},
    {"type": "function", "function": {"name": "http_get", "description": "HTTP GET.", "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}},
    {"type": "function", "function": {"name": "http_post", "description": "HTTP POST.", "parameters": {"type": "object", "properties": {"url": {"type": "string"}, "json": {"type": "object"}}, "required": ["url"]}}},
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
]

CONFIGS = [
    ("t00", "0 tools", None),
    ("t02", "2 tools (minimal)", MINIMAL_TOOLS),
    ("t10", "10 tools", TEN_TOOLS),
    ("t25", "25 tools", TWENTYFIVE_TOOLS),
]


def main():
    os.makedirs("results", exist_ok=True)
    out = {}
    for key, label, tools in CONFIGS:
        print(f"\n{'='*70}\n>>> {key} ({label})")
        try:
            r = call_once(MINIMAL_PERSONA, USER_TASK, tools)
        except Exception as e:
            print(f"  FAILED: {e}")
            continue
        m = r["choices"][0]["message"]
        reason = m.get("reasoning_content", "")
        content = m.get("content") or ""
        calls = m.get("tool_calls") or []
        st = style_stats(reason)
        print(f"  reasoning: {len(reason)} chars | content: {len(content)} chars | calls: {len(calls)}")
        print(f"  style: {st}")
        out[key] = {
            "label": label, "tools": len(tools) if tools else 0,
            "reasoning_chars": len(reason), "content_chars": len(content),
            "tool_calls": [c["function"]["name"] for c in calls],
            "style": st, "reasoning_text": reason, "content_text": content,
        }
    with open("results/test2_tool_count.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("\nDONE -> results/test2_tool_count.json")


if __name__ == "__main__":
    main()
