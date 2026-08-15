# scaffold-cot-probe

Independent replication of the DeepSeek V4 Pro scaffold experiments from
[xiaobright/modeltest](https://github.com/xiaobright/modeltest). These scripts
measure how an LLM agent's **scaffold** (persona text, tool catalog, tool names,
injection position, reasoning effort) changes its chain-of-thought trajectory
(`we`-collective vs `let me`-self style), output quality, and wall-clock/token
cost.

## Background

Official harnesses like DeepSeek Harness ship a "minimal" preset that sends the
model's *exact RL prompt and schemas* (one-line persona + two training-aligned
tools). Models are highly sensitive to scaffold: the same model scores 99 with
its native minimal scaffold and 91-93 under thicker generic harnesses. These
scripts independently reproduce and quantify that effect, and test
optimizations such as external toolkits, recommendation placement, and tool
naming.

## Key empirical findings (dsv4p, 2026-08)

- **Persona is matched by surface form**: any change to the training string
  (`"You are a helpful software engineer assistant."`) - word form, word order,
  capitalization - flips CoT style from `we` to `let me`.
- **Tool names are part of the RL distribution**: renaming `bash` to
  `run_command` cuts reasoning depth ~3.6x.
- **Tool catalog size hurts**: 25 tools -> exploration anxiety, delayed output,
  ~2/25 actually used; 2 tools -> zero exploration, direct production.
- **Injection position is a switch**: identity prepended -> self-personification;
  appended after the minimal persona -> `we` preserved + deeper thinking.
- **Reasoning effort < high flips self-reference** from `we` to `I`.
- **External toolkit + user-message recommendation** is the sweet spot: fast,
  stable, fault-tolerant, immune to convenience-tool traps.

## Scripts

| File | Purpose |
|---|---|
| `probe_common.py` | shared plumbing: API calls (streaming + retries), DSH-style parallel tool execution, style stats (`we`/`let me`/`let's`) |
| `test1_minimal_vs_full.py` | A/B: minimal-aligned vs full-harness scaffold |
| `test2_tool_count.py` | tool catalog size sweep 0/2/10/25 |
| `test5_html_game.py` | produce a real game under two scaffolds |
| `test10_anchored.py` | anchored-standard: minimal first round, full tools after |
| `test14_form_ablation.py` | surface-form ablation of the minimal persona |
| `test17_selfref_params.py` | self-reference vs tool count and sampling params |
| `test19_parallel.py` | parallel multi-agent matrix runs |
| `make_assets.py` | generate workspace assets (audio/sprites/tool library) |
| `md2pdf_report.py` | markdown -> Chinese PDF report |

## Usage

```bash
# configure: set PROBE_ROOT (defaults to $TEMP/dsh_cot_probe) and an API key
# read from ~/.dsh/.credentials.yaml (DEEPSEEK_API_KEY) or your own loader
python probe_common.py   # smoke
python test14_form_ablation.py   # any test file
```

All scripts call the chat-completions endpoint configured in `probe_common.py`
(API_URL) with `stream:true` (SSE, keeps long-reasoning connections alive),
4-attempt retries, and DSH-style batched tool execution.

## License

MIT
