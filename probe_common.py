"""probe_common.py - shared plumbing for DSH scaffold A/B CoT probes.

Zero-dependency (urllib only). Talks directly to api.deepseek.com with
OpenAI-compatible chat/completions, capturing reasoning_content verbatim.

Key facts encoded here (verified from source):
- DSH minimal preset persona (agent.cordis.yml, complete:true):
    "You are a helpful software engineer assistant."
- DSH minimal tools: persistent-bash (bash) + str_replace_editor,
  bash description copied verbatim from config/agent-presets/minimal/agent.cordis.yml
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

API_URL = "https://opencode.ai/zen/go/v1/chat/completions"
MODEL = "deepseek-v4-flash"
WORKSPACE = r"${PROBE_ROOT}"

# --------------------------------------------------------------------------
# DSH minimal verbatim assets
# --------------------------------------------------------------------------

MINIMAL_PERSONA = "You are a helpful software engineer assistant."

BASH_DESCRIPTION = (
    "Run commands in a bash shell\n"
    "* When invoking this tool, the contents of the \"command\" parameter does NOT need to be XML-escaped.\n"
    "* You don't have access to the internet via this tool.\n"
    "* You do have access to a mirror of common linux and python packages via apt and pip.\n"
    "* State is persistent across command calls and discussions with the user.\n"
    "* To inspect a particular line range of a file, e.g. lines 10-25, try 'sed -n 10,25p /path/to/the/file'.\n"
    "* Please avoid commands that may produce a very large amount of output.\n"
    "* Please run long lived commands in the background, e.g. 'sleep 10 &' or start a server in the background."
)

TOOL_BASH = {
    "type": "function",
    "function": {
        "name": "bash",
        "description": BASH_DESCRIPTION,
        "parameters": {
            "type": "object",
            "properties": {"command": {"type": "string", "description": "The command to run"}},
            "required": ["command"],
        },
    },
}

TOOL_STR_REPLACE = {
    "type": "function",
    "function": {
        "name": "str_replace_editor",
        "description": (
            "Edit files using string replacement. Use 'view' to read a file (with optional line range), "
            "'str_replace' to replace an exact string, 'create' to create a new file. Paths must be absolute."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["view", "str_replace", "create"]},
                "path": {"type": "string"},
                "old_string": {"type": "string"},
                "new_string": {"type": "string"},
                "view_range": {"type": "array", "items": {"type": "integer"}},
            },
            "required": ["action", "path"],
        },
    },
}

MINIMAL_TOOLS = [TOOL_BASH, TOOL_STR_REPLACE]


def load_key():
    """Read DEEPSEEK_API_KEY from .dsh/.credentials.yaml without echoing it."""
    cred_path = os.path.expanduser(r"~\.dsh\.credentials.yaml")
    with open(cred_path, "r", encoding="utf-8") as f:
        for line in f:
            m = re.match(r"^\s*DEEPSEEK_API_KEY\s*:\s*['\"]?([^'\"]+)", line)
            if m:
                return m.group(1).strip()
    raise RuntimeError("DEEPSEEK_API_KEY not found in " + cred_path)


def _curl_stream(body, timeout=300):
    """POST via curl.exe with stream:true (SSE). Keeps the connection alive during
    long reasoning, avoiding gateway idle-timeouts. Parses deltas and assembles a
    response dict shaped like the non-streaming one."""
    import tempfile
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "wb") as f:
        f.write(json.dumps(body).encode("utf-8"))
    try:
        last_err = None
        for attempt in range(4):
            try:
                r = subprocess.Popen(
                    ["curl.exe", "-sS", "-N", "--max-time", str(min(timeout, 300)),
                     "-X", "POST", API_URL,
                     "-H", "Content-Type: application/json",
                     "-H", "Authorization: Bearer " + load_key(),
                     "--data-binary", "@" + path],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, encoding="utf-8", errors="replace")
                msg = {"role": "assistant", "content": "", "reasoning_content": "", "tool_calls": []}
                usage = {}
                finish = None
                for line in r.stdout:
                    line = line.strip()
                    if not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if payload == "[DONE]":
                        break
                    try:
                        chunk = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    ch = (chunk.get("choices") or [{}])[0]
                    delta = ch.get("delta") or {}
                    if delta.get("reasoning_content"):
                        msg["reasoning_content"] += delta["reasoning_content"]
                    if delta.get("content"):
                        msg["content"] += delta["content"]
                    for tc in delta.get("tool_calls") or []:
                        idx = tc.get("index", 0)
                        while len(msg["tool_calls"]) <= idx:
                            msg["tool_calls"].append({"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
                        fn = tc.get("function") or {}
                        if tc.get("id"):
                            msg["tool_calls"][idx]["id"] = tc["id"]
                        if fn.get("name"):
                            msg["tool_calls"][idx]["function"]["name"] += fn["name"]
                        if fn.get("arguments"):
                            msg["tool_calls"][idx]["function"]["arguments"] += fn["arguments"]
                    if ch.get("finish_reason"):
                        finish = ch["finish_reason"]
                    if chunk.get("usage"):
                        usage = chunk["usage"]
                r.wait(timeout=min(timeout, 300) + 15)
                err_out = r.stderr.read() if r.stderr else ""
                if r.returncode != 0:
                    raise RuntimeError(f"curl failed rc={r.returncode}: {err_out[:300]}")
                # drop empty tool_calls
                msg["tool_calls"] = [tc for tc in msg["tool_calls"] if tc["function"]["name"]]
                return {
                    "choices": [{"message": msg, "finish_reason": finish}],
                    "usage": usage,
                }
            except Exception as e:
                last_err = str(e)[:300]
                if attempt < 3:
                    time.sleep(5 * (attempt + 1))
        raise RuntimeError(f"stream request failed after 4 attempts: {last_err}")
    finally:
        os.unlink(path)


def _curl_json(body, timeout=300):
    """POST JSON via curl.exe (Cloudflare-safe TLS fingerprint), with retries.
    Uses streaming when body has stream:true (keeps long-reasoning connections alive)."""
    if body.get("stream"):
        return _curl_stream(body, timeout)
    import tempfile
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "wb") as f:
        f.write(json.dumps(body).encode("utf-8"))
    try:
        last_err = None
        for attempt in range(4):
            try:
                r = subprocess.run(
                    ["curl.exe", "-sS", "--max-time", str(min(timeout, 90)), "-X", "POST", API_URL,
                     "-H", "Content-Type: application/json",
                     "-H", "Authorization: Bearer " + load_key(),
                     "--data-binary", "@" + path],
                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                    timeout=min(timeout, 90) + 15)
                if r.returncode != 0:
                    raise RuntimeError(f"curl failed rc={r.returncode}: {r.stderr[:300]}")
                out = r.stdout.strip()
                if not out:
                    raise RuntimeError("empty response")
                return json.loads(out)
            except Exception as e:
                last_err = str(e)[:300]
                if attempt < 3:
                    time.sleep(5 * (attempt + 1))
        raise RuntimeError(f"request failed after 4 attempts: {last_err}")
    finally:
        os.unlink(path)


def call_once(system, user, tools=None, reasoning_effort="max", thinking=True, timeout=300, temperature=None, stream=True):
    """One chat/completions call; returns parsed JSON. Streaming by default."""
    body = {
        "model": MODEL,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "reasoning_effort": reasoning_effort,
        "stream": stream,
    }
    if thinking:
        body["thinking"] = {"type": "enabled"}
    if temperature is not None:
        body["temperature"] = temperature
    if tools:
        body["tools"] = tools
    return _curl_json(body, timeout)


# --------------------------------------------------------------------------
# minimal tool EXECUTION (real, local) for multi-round trajectories
# --------------------------------------------------------------------------

def exec_tool(tool_name, args, workdir=WORKSPACE):
    """Execute a tool call locally. Returns (ok, text)."""
    try:
        if tool_name == "bash":
            cmd = args.get("command", "")
            # DSH minimal runs real bash; execute via git-bash so bash syntax
            # (ls -la, sed, heredocs) actually works instead of pwsh errors.
            env = dict(os.environ)
            env["PATH"] = r"C:\Python312;C:\Program Files\Git\usr\bin;" + env.get("PATH", "")
            # tool variables: expose external toolkit as bash env vars (available
            # in every bash call without discovery)
            _tl = os.path.join(workdir, "tools_lib")
            if os.path.isdir(_tl):
                for _fn in sorted(os.listdir(_tl)):
                    if _fn.endswith(".sh"):
                        env["TOOL_" + _fn[:-3].upper()] = os.path.join(_tl, _fn)
            r = subprocess.run(
                [r"C:\Program Files\Git\bin\bash.exe", "-lc", cmd],
                cwd=workdir, capture_output=True, text=True, timeout=120,
                encoding="utf-8", errors="replace", env=env,
            )
            out = (r.stdout or "") + (("\n[stderr] " + r.stderr) if r.stderr else "")
            return r.returncode == 0, out[:16000] or "(no output)"
        if tool_name == "str_replace_editor":
            action = args.get("action")
            path = args.get("path", "")
            if action == "view":
                rng = args.get("view_range") or []
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
                if rng and len(rng) >= 2:
                    lines = lines[rng[0] - 1 : rng[1]]
                return True, "".join(lines)[:16000]
            if action == "str_replace":
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                old = args.get("old_string", "")
                if old not in content:
                    return False, f"old_string not found in {path}"
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content.replace(old, args.get("new_string", ""), 1))
                return True, f"Replaced in {path}"
            if action == "create":
                with open(path, "w", encoding="utf-8") as f:
                    f.write(args.get("new_string", ""))
                return True, f"Created {path}"
            return False, f"unsupported action {action}"
        if tool_name == "read_file":
            path = args.get("path", "")
            if not os.path.isabs(path):
                path = os.path.join(workdir, path)
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return True, f.read()[:16000]
        if tool_name == "write_file":
            path = args.get("path", "")
            if not os.path.isabs(path):
                path = os.path.join(workdir, path)
            with open(path, "w", encoding="utf-8") as f:
                f.write(args.get("content", ""))
            return True, f"Wrote {path}"
        if tool_name == "run_python":
            code = args.get("code", "")
            tmp = os.path.join(workdir, "_probe_run.py")
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(code)
            r = subprocess.run(["C:\\Python312\\python.exe", tmp],
                               cwd=workdir, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=120)
            out = (r.stdout or "") + (("\n[stderr] " + r.stderr) if r.stderr else "")
            return r.returncode == 0, out[:8000] or "(no output)"
        if tool_name == "list_dir":
            p = args.get("path", workdir)
            if not os.path.isabs(p):
                p = os.path.join(workdir, p)
            entries = os.listdir(p)
            return True, "\n".join(sorted(entries))[:16000]
        if tool_name == "search_files":
            pat = args.get("pattern", "")
            hits = []
            for root, dirs, files in os.walk(args.get("path", WORKSPACE)):
                dirs[:] = [d for d in dirs if d not in (".git", "__pycache__")]
                for fn in files:
                    if fn.endswith(".py"):
                        fp = os.path.join(root, fn)
                        try:
                            for i, line in enumerate(open(fp, encoding="utf-8"), 1):
                                if pat in line:
                                    hits.append(f"{os.path.relpath(fp, WORKSPACE)}:{i}: {line.rstrip()}")
                        except Exception:
                            pass
            return True, "\n".join(hits[:60]) or "(no hits)"
        if tool_name == "run_node_check":
            # extract <script> from an HTML file and run node --check
            path = args.get("path", "")
            if not os.path.exists(path):
                return False, f"file not found: {path}"
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                html = f.read()
            m = re.search(r"<script[^>]*>(.*?)</script>", html, re.S)
            if not m:
                return False, "no <script> block found in file"
            tmp = os.path.join(os.path.dirname(path), "_extracted_check.js")
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(m.group(1))
            r = subprocess.run(["node", "--check", tmp], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=60)
            out = (r.stdout or "") + (("\n[stderr] " + r.stderr) if r.stderr else "")
            return r.returncode == 0, (out[:3000] or "syntax OK")
        if tool_name == "html_validate":
            # validate HTML structure with python html.parser
            import html.parser as _hp
            path = args.get("path", "")
            if not os.path.isabs(path):
                path = os.path.join(workdir, path)
            if not os.path.exists(path):
                return False, f"file not found: {path}"
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                html_text = f.read()
            errors = []

            class P(_hp.HTMLParser):
                def error(self, message):
                    errors.append(message)
            p = P()
            try:
                p.feed(html_text)
                p.close()
            except Exception as e:
                errors.append(str(e))
            for tag in ("canvas", "script", "div", "button"):
                if f"<{tag}" not in html_text:
                    errors.append(f"missing <{tag}>")
            return (not errors), ("valid" if not errors else "issues: " + "; ".join(errors[:8]))
        return False, f"tool '{tool_name}' not available in this probe"
    except subprocess.TimeoutExpired:
        return False, "[exec timeout]"
    except Exception as e:
        return False, f"[exec error] {e}"


def run_agent_loop(system, user, tools, max_rounds=4, reasoning_effort="max", workdir=WORKSPACE, tools_after=None, swap_after_round=1):
    """Multi-round loop: LLM -> execute tool calls locally -> feed back. Returns transcript.

    tools_after: if set, rounds > swap_after_round use this catalog instead
    (anchored-standard style: minimal first round, full catalog afterwards).
    Records per-round api_wall_ms, tool_wall_ms and token usage.
    """
    import time as _t
    transcript = []
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    for rnd in range(1, max_rounds + 1):
        active_tools = tools if (tools_after is None or rnd <= swap_after_round) else tools_after
        body = {
            "model": MODEL,
            "messages": messages,
            "tools": active_tools,
            "reasoning_effort": reasoning_effort,
            "thinking": {"type": "enabled"},
            "stream": True,
        }
        t0 = _t.time()
        data = _curl_json(body, 300)
        api_wall_ms = int((_t.time() - t0) * 1000)
        if "choices" not in data:
            raise RuntimeError("API error: " + json.dumps(data, ensure_ascii=False)[:500])
        msg = data["choices"][0]["message"]
        reasoning = msg.get("reasoning_content", "")
        content = msg.get("content") or ""
        calls = msg.get("tool_calls") or []
        transcript.append({
            "round": rnd,
            "reasoning": reasoning,
            "content": content,
            "tool_calls": [c["function"]["name"] + " :: " + json.dumps(json.loads(c["function"]["arguments"] or "{}"), ensure_ascii=False)[:300] for c in calls],
            "usage": data.get("usage", {}),
            "api_wall_ms": api_wall_ms,
            "tool_wall_ms": 0,
        })
        if not calls:
            break
        tool_ms = 0
        # DSH-style batched execution: run tool_calls concurrently in a bounded
        # pool (maxParallelToolCalls=10 in DSH; we use 4 to stay light).
        from concurrent.futures import ThreadPoolExecutor
        t_exec = _t.time()
        results = {}
        with ThreadPoolExecutor(max_workers=min(4, len(calls))) as pool:
            futs = {}
            for idx, c in enumerate(calls):
                fn = c["function"]["name"]
                try:
                    args = json.loads(c["function"]["arguments"] or "{}")
                except json.JSONDecodeError:
                    args = {}
                futs[pool.submit(exec_tool, fn, args, workdir)] = idx
            for fut in futs:
                idx = futs[fut]
                try:
                    results[idx] = fut.result()
                except Exception as e:
                    results[idx] = (False, f"[exec error] {e}")
        tool_ms += int((_t.time() - t_exec) * 1000)
        for idx, c in enumerate(calls):
            ok, out = results.get(idx, (False, "[missing result]"))
            transcript[-1]["tool_results"] = transcript[-1].get("tool_results", [])
            transcript[-1]["tool_results"].append({"name": c["function"]["name"], "ok": ok, "output": out[:1200]})
            messages.append({"role": "assistant", "content": content, "reasoning_content": reasoning, "tool_calls": [c]})
            messages.append({"role": "tool", "tool_call_id": c["id"], "content": out})
        transcript[-1]["tool_wall_ms"] = tool_ms
    return transcript


# --------------------------------------------------------------------------
# style statistics (mirrors modeltest's we / let's / let me counters)
# --------------------------------------------------------------------------

STYLE_PATTERNS = {
    "we": r"\bwe\b",
    "let's": r"\blet'?s\b",
    "let me": r"\blet me\b",
    "I'll": r"\bI'?ll\b",
    "The user wants": r"The user wants",
    "Let me": r"\bLet me\b",
    "Let's": r"\bLet'?s\b",
}


def style_stats(text):
    if not text:
        return {k: 0 for k in STYLE_PATTERNS}
    low = text
    return {k: len(re.findall(v, low, re.IGNORECASE)) for k, v in STYLE_PATTERNS.items()}
