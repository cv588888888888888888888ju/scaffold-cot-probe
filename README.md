# scaffold-cot-probe

对 [xiaobright/modeltest](https://github.com/xiaobright/modeltest) 中 DeepSeek V4 Pro scaffold 实验的独立复核。
本仓库脚本测量 LLM agent 的 **scaffold**（persona 文本、工具目录、工具命名、注入位置、推理档位）如何改变其
思维链轨迹（`we` 共同体 vs `let me` 自我风格）、产物质量与墙钟/token 成本。

## 背景

DeepSeek Harness 等官方 harness 自带 "minimal" 预设，向模型发送 *exact RL prompt and schemas*
（一句 persona + 两个训练对齐工具）。模型对 scaffold 高度敏感：同一模型在原生 minimal scaffold 下 99 分，
在更厚的通用 harness 下仅 91-93。本仓库独立复现并量化该效应，并测试外部工具库、推荐位置、工具命名等优化。

## 核心实验发现（dsv4p，2026-08）

- **persona 按表面形式匹配**：训练原句（"You are a helpful software engineer assistant."）的任何改动
  （词形/词序/大小写）都会使思维链从 `we` 翻转为 `let me`
- **工具名属于 RL 分布**：把 `bash` 改名为 `run_command` 使推理深度下降约 3.6×
- **工具目录规模有害**：25 工具 → 探索焦虑、产出延迟、实际只用 2/25；2 工具 → 零探索、直接产出
- **注入位置是开关**：身份前置 → 自我人格化；追加在 minimal persona 之后 → `we` 保持且思考更深
- **推理档位低于 high 使自称翻转**：`we` → `I`
- **外部工具库 + user 消息推荐是甜点区**：快、稳、容错好、对便利工具陷阱免疫

## 脚本

| 文件 | 用途 |
|---|---|
| `probe_common.py` | 公共层：API 调用（流式+重试）、DSH 式并行工具执行、风格统计（we/let me/let's）|
| `test1_minimal_vs_full.py` | A/B：minimal 对齐 vs 全量 harness scaffold |
| `test2_tool_count.py` | 工具目录规模扫描 0/2/10/25 |
| `test5_html_game.py` | 两种 scaffold 下产出真实游戏 |
| `test10_anchored.py` | anchored-standard：首轮 minimal、后续全工具 |
| `test14_form_ablation.py` | minimal persona 的表面形式消融 |
| `test17_selfref_params.py` | 自称 vs 工具数与采样参数 |
| `test19_parallel.py` | 并行多 agent 矩阵运行 |
| `make_assets.py` | 生成工作区资产（音频/sprite/工具库）|
| `md2pdf_report.py` | Markdown → 中文 PDF 报告 |

## 用法

```bash
# 配置：设置 PROBE_ROOT（默认 $TEMP/dsh_cot_probe）与 API key
# （读取 ~/.dsh/.credentials.yaml 的 DEEPSEEK_API_KEY，或自定义加载器）
python probe_common.py   # 冒烟
python test14_form_ablation.py   # 运行任意测试
```

所有脚本通过 `probe_common.py` 中配置的端点（API_URL）调用 chat-completions，
`stream:true`（SSE 保持长连接）、4 次重试、DSH 式批量工具执行。

## License

MIT
