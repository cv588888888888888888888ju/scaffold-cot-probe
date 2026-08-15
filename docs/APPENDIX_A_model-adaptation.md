# 追加 A：per-model 适配层设计（基于 dsv4p Scaffold 研究）

**日期**: 2026-08-15 | **定位**: EXPERIMENT_REPORT 追加章节 | **范围**: 引擎的模型适配层规格

---

## 1. 核心命题

**厚 harness 的退化，本质是模型的适配性下降**——同一套厚 scaffold 硬套所有模型，把模型从训练分布（母语）拉出，强迫适配陌生工具面，能力打折。解法：**引擎按模型做适配（per-model scaffold 模板），每个模型回到自己的训练分布**。

实测：dsv4p 对 scaffold 极敏感（91↔99，±8 分），flash 不敏感（92±1）——**适配敏感性因模型而异，一刀切必然伤害敏感模型**。

## 2. 适配参数化（5 维度，全部实测支撑）

| 维度 | 实测结论 | 引用 |
|---|---|---|
| **framework 原文** | 按表面字段匹配：dsv4p 训练原句 `You are a helpful software engineer assistant.` 改任何形式（词形/词序/大小写）都触发 let_me 人格化（大小写最伤 0→9.67）| test14 |
| **工具面** | ① 工具名 ∈ RL 分布：改名 → 思考塌方 3.6× ② 数量 ≤5：25 工具 → 探索 14 次/验证焦虑/产出延迟，2 工具零探索 | test11 / test15 / test19 |
| **注入/推荐** | 位置是开关：身份前置 → let_me=4.0 人格化；追加在 minimal 原句后 → we 保持 + 思考 2.5×；推荐放 user 消息尾 → 轨迹保持（modeltest 同证）| test12 / test16 / modeltest |
| **effort 默认** | effort=low → 自称 we 翻转为 I（思考浅）；≥high → we 轨迹稳定。dsv4p 默认 high（官方/DSH 默认）| test17 |
| **批量策略** | DSH 式并行执行：模型返回多 tool_calls → 按工具 executionMode 分组 → 有界池并发（max 10）| dsh-agent-loop 源码 |

## 3. 适配模板草案（dsv4p 完整参数）

```
per-model template: dsv4p
├─ framework: "You are a helpful software engineer assistant."（verbatim，禁止改动）
├─ schema 工具（≤3，训练内命名）: bash + str_replace_editor（+ 可选 read）
├─ 工具库: 外部脚本（bash 环境变量 TOOL_* 注入，不占 schema）
│   ├─ 相关工具 2-3 个（verify/check/build 类）
│   └─ 推荐策略: user 消息尾部中性推荐（"可用: verify_html / check_js"）
├─ reasoning_effort: high（默认，禁止 low）
├─ 批量: 开启（并行执行 pool ≤4）
├─ 上下文注入: 全部追加在 persona 后（\n\n 分隔），不进 framework 段
└─ 记忆/档案: 作为追加节，不作为身份
```

## 4. 引擎实现建议

```
引擎 = 模型路由层 + 模板库
调用链: 模型识别 → 查模板 → 组装（framework verbatim + 母语工具集 + 推荐注入）→ 请求
┌─────────────────────────────────────────┐
│ 模板库                                    │
│  dsv4p   → minimal 式（上述草案）          │
│  dsv4-flash → 模板可宽松（适配不敏感）      │
│  Claude 系 → 待测（各自的 RL 训练分布）     │
│  GPT 系   → 待测（Codex 式母语）           │
└─────────────────────────────────────────┘
```

## 5. 模板库建设路径

1. **dsv4p**：已有完整参数（本报告 19 节 + 追加 A）
2. **其他模型**：复用 probe 方法（skill: scaffold-cot-probe）逐一测出母语参数：
   - 找官方 harness 源码 → 扒 exact persona + 工具集（DSH 模式）
   - 形式消融确认字段匹配敏感性
   - 工具改名确认 RL 分布边界
3. **模板注册**：每模型模板 = {framework 原文, schema 工具集, 工具库脚本, 推荐策略, effort, 批量开关}

## 6. 设计原则（全部来自实测）

1. **framework 段 = 训练原句 verbatim**，一个字不改（字段匹配）
2. **schema 工具 ≤3 且训练内命名**，能力扩展走外部工具库
3. **一切注入追加在 persona 后**，前置 = 人格化陷阱
4. **推荐 = user 消息尾部中性清单**，不是 system 指令
5. **effort 锁定 ≥high**，low 会退化为 I 自称浅思考
6. **批量 = harness 层并行执行**（模型发数组即可），不靠提示引导
7. **验证工具必须可信**，陷阱/坏资产只放便利层（若测试需要）
8. **适配敏感性因模型而异**：模板必须 per-model，不做通用最优

---

*追加 A 完。主报告见 EXPERIMENT_REPORT.md（1-19 节）。*
