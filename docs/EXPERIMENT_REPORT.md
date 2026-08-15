# DeepSeek V4 Pro Scaffold CoT Probe — 完整实验报告

**日期**: 2026-08-15 | **研究对象**: deepseek-v4-pro（直连 opencode.ai/zen/go/v1）| **方法**: reasoning_content 全文抓取 + 风格统计 + 真实工具执行

---

## 0. 源码事实（扒 @deepseek-ai/dsh@0.1.0-rc.6）

`config/agent-presets/minimal/agent.cordis.yml`（2403 字节，全部内容）：
- **persona**: `You are a helpful software engineer assistant.`（唯一一句）
  - `complete: true` → 禁止追加任何提示词
  - `includeRuntimeContext: false` → 不注入运行时上下文
- **工具**（2 个）: `persistent-bash`（8 行描述，300s 超时）+ `str_replace_editor`（maxOutputChars 16000）
- 无上下文压缩、无 AGENTS.md、无 skill-catalog

DSH 实际配置（settings.yaml）：baseURL=`https://opencode.ai/zen/go/v1`，默认模型 deepseek-v4-flash，reasoningEffort=high。Hermes 与 DSH 共用同一端点+key。

**协议硬约束发现**: thinking 模式下 `reasoning_content` 必须原样回传，否则 API 报 `invalid_request_error`（"The reasoning_content in the thinking mode must be passed back"）。

---

## 1. persona 长度 → CoT 风格（test3，flash，2 工具固定，单轮）

| persona | 字符 | reasoning | `we` | `let me` |
|---|---|---|---|---|
| p_short（minimal 原句） | 46 | 107 | 1 | **0** |
| p_mid（4 行） | 268 | 51 | 1 | 0 |
| p_long（~30 行） | 1138 | 110 | 0 | **1** |

→ 长 persona 激活 `let me`；短 persona 保持 `we`。

---

## 2. 工具数量梯度（test2，flash，minimal persona 固定，单轮）

| 工具数 | reasoning | content | `we` | `let me` | `let's` | 行为 |
|---|---|---|---|---|---|---|
| 0 | **377**（最长） | 1110（文字方案） | 5 | 0 | 2 | 被迫纯文本推理，絮叨纠结工具 |
| 2（minimal） | 75-107 | 0 | 1 | 0 | 1 | 直接调工具 |
| 10 | 108 | 0 | 1 | 0 | 1 | 直接行动 |
| 25 | 94 | 0 | 1 | 0 | 1 | 直接行动（倾向并行多工具） |

→ **工具存在与否是最大分野**（0 vs 有工具），工具数量 2→25 对首轮影响小；flash 下 0 工具时 `we=5` 最高（思考最多），有工具后一律 `we=1, let me=0`（minimal 短 persona 锚定的 we 轨迹）。

---

## 3. A/B scaffold 完整轨迹（test1，pro，4 轮真实工具执行）

任务：诊断+修复 stats_lib 测试失败。

| 配置 | r1 reasoning | 风格 | 轨迹特征 |
|---|---|---|---|
| A_minimal（46ch+2工具） | 90-103 | we=1-2, let_me=0 | 全程只用 bash，小步探索→读代码 |
| B_full（1134ch+11工具+注入） | 89-97 | we=0, let_me=1 | r1 就并行双工具（bash+list_dir） |

→ 多工具 scaffold 下模型倾向并行工具调用；minimal 单工具顺序执行。

---

## 4. 关键词消融（test7 n=3 / test8 n=1，pro，minimal 工具固定）

test7（n=3，游戏任务首轮）:

| 关键词 | 平均思考量 | 平均 `we` | 平均 `let me` |
|---|---|---|---|
| helpful | 3,861 | 7.33 | 0.00 |
| **senior** | **7,811（2.0×）** | **14.67（2.0×）** | 0.33 |
| precise | 5,773 | 8.33 | 2.00（一次 6） |

test8（n=1 原文抓取）:

| 关键词 | 思考量 | `we` | `let me` | `let's` |
|---|---|---|---|---|
| helpful | 1,560 | 7 | 0 | 4 |
| senior | **13,282（8.5×）** | 14 | 0 | 11 |
| precise | 7,338 | 16 | 0 | 3 |

→ **单词激活角色模式，分布级偏移非开关**。senior 触发"想周全"（思考 2-8.5×），helpful 触发"直接帮"，precise 触发"谨慎核验"（偶发 let me）。

---

## 5. pro 生成贪吃蛇产物对比（test5，8 轮）

| 维度 | A_minimal（46ch+2工具） | B_full（1134ch+11工具） |
|---|---|---|
| 产物 | game.html **408 行/12KB** | game.html **308 行/9.9KB** |
| 功能检查 | 6/6 过 | 6/6 过 |
| 单轮最长 reasoning | 1,097 | **45,223** |
| 风格 | we=7, **let_me=0** | **let_me=21, I'll=29** |
| 工作方式 | bash+编辑器小步迭代+node 验证+清理 | write_file 一次成稿+验证 |

test6（关键词产物，各 6 轮）: A_helpful（aria=1, overlay=11）/ B_senior（**aria=4, role=1, CSS变量=7, box-shadow=6**）→ senior 想得更久 → 引导+审美标记全面更多。

用户主观评测: **A 逻辑/引导更好（键盘缓冲、aria 无障碍、overlay 引导），B 审美更好（CSS 变量、渐变、阴影）**。

---

## 6. 只改工具（test9b，pro，persona 锁死 1 句，n=3）

| 工具数 | 思考量 | `we` | `let me` |
|---|---|---|---|
| 2（minimal） | 1,126 | 5.67 | **0.0** |
| 11（full） | 2,950（2.6×） | 6.33 | 0.67 |

→ 工具增多：思考投入 2.6×，`let me` 从 0 冒出（1/3 采样），`we` 仍主导。

---

## 7. 锚定 vs 全开（test10，pro，5 轮轨迹）

| 配置 | `we`/`let me` 总计 | 实际行为 |
|---|---|---|
| 锚定（r1 两工具→r2 起 11） | 8 / **0** | **r4 写完 game.html**，直接产出 |
| 全开（r1 起 11 工具） | 7 / 0 | **5 轮全在探测验证工具**（chromium/playwright/puppeteer/jsdom），没动手写 |

→ **首轮后加工具不改变思维方式**（we 保持，与 modeltest 355 块仅 1 次 let me 同构）；真正差异在行为：**多工具目录引发"验证焦虑"，延迟动手**。

---

## 8. 工具改名（test11，pro，n=3，描述不变只换名）

| 工具名 | 思考量 | `we` | `let's` |
|---|---|---|---|
| `bash`/`str_replace_editor`（RL 分布内） | 4,573 | 11.0 | 5.0 |
| `run_command`/`file_editor`（改名） | **1,277（3.6×↓）** | 7.7 | 2.7 |

→ **工具名是 RL 分布的一部分**（"exact RL prompt and schemas"实锤）。改名后调用仍正常，但思考投入断崖下跌。

---

## 9. `let me` 出现条件汇总（跨全部批次）

| 场景 | `let me` 强度 |
|---|---|
| 长 persona + 11 工具（叠加） | 21-29 次（45K 思考） |
| 长 persona 单独（1138ch） | 1 次 |
| 工具多单独（11 工具） | 0.67 |
| precise 关键词 | 2.0（一次 6） |
| 短 persona + 任何工具数 | 全 0 |
| 锚定 / 改名 / 0 工具 | 全 0 |

**机制**: `we` 家族（we+let's）= 任务共同体模式 = RL 训练默认轨迹（无身份信号时自动进入）；`let me` 家族（let me+I'll）= 自我执行者模式 = 身份强化（"你是一个 X"）/ 工具选择压力 / 谨慎要求 三者触发，叠加爆炸。

---

## 10. 追加式优化（test12，pro，n=3，minimal 工具固定）

| 配置 | persona 字符 | 思考量 | `we` | `let me` | `let's` |
|---|---|---|---|---|---|
| base（1 句对照） | 46 | 1,130 | 4.33 | **0.0** | 3.0 |
| **ident_pre**（身份前置） | 139 | **8,688（7.7×）** | 11.0 | **4.0** | 7.33 |
| **ident_post**（身份后置） | 140 | 2,777（2.5×） | 8.0 | **0.0** | 4.67 |
| **toolsum_post**（工具概要后置） | 171 | **5,772（5.1×）** | 7.33 | 0.67 | 5.67 |
| both_post（身份+工具概要后置） | 264 | 4,764（4.2×） | 4.33 | 1.33 | 2.67 |

**核心发现——位置是开关**：
- 同一句身份描述，**前置 → let_me=4.0**（深度思考但自我人格化，分布外偏移）
- **后置 → let_me=0.0 + we 从 4.33 升到 8.0**（思考加深 2.5× 且 we 轨迹保持）
- 工具概要后置最甜：**思考量 5.1×，let_me≈0**，we 保持
- 身份+工具概要叠加追加反而稀释（let_me 回升 1.33，we 掉回 4.33）

**机制**：前置 = 系统提示词开头的"你是谁"定义位 → 身份信号被当作首要自我定义 → 人格化；后置 = minimal 原句先锚定"helpful 共同体" → 追加内容只被当作能力补充说明 → we 轨迹保持 + 深度提升。

**优化配方**：`"You are a helpful software engineer assistant." + \n\n + 身份/工具概要`（作为补充说明，绝不做身份声明）。

---

## 12. 工具概要抑制探索 + 字段匹配实锤（test13/test14，pro）

### test13：11 工具 ± 工具概要（6 轮轨迹）

| 配置 | 探索命令 | 首写轮次 | 产出 | 验证方式 |
|---|---|---|---|---|
| 11 工具无概要 | **14** | 4 | ✓ | 找 Edge headless（.edge-profile --dump-dom） |
| 11 工具+概要后置 | **5（-64%）** | **3** | ✓ | run_python 解析+语法检查 |

→ 一句话工具概要 = 多工具场景必配：模型知道工具能力边界，不再盲目探测环境。

### test14：minimal persona 形式消融（语义不变，n=3）

| 变体 | 思考量 | `we` | `let me` |
|---|---|---|---|
| **orig_exact**（训练原句） | 4,947 | 10.0 | **0.0** |
| engineer→engineering | 10,827 | 9.0 | **2.67** |
| 换词序 | 3,325 | 8.3 | **1.67** |
| **改大小写**（Helpful Software Engineer Assistant） | 7,796 | 4.3 | **9.67** |
| 拆成两句 | 1,431 | 6.0 | 0.67 |
| 完全改写 | 6,846 | 8.0 | 2.67 |

→ **表面字段匹配实锤**：原文 let_me 严格 0，任何形式变化都让 let_me 冒出（大小写最伤 9.67）。极简模式高分 = 与 RL 训练数据逐字节一致的字符串匹配，不是语义理解。framework 段必须保留训练原句 verbatim，任何"优化"都是破坏分布。

---

## 14. 应用场景版工具数量梯度（test15，pro，6 轮完整 agent 循环）

| 工具数 | 产出 | 首写轮次 | 探索命令 | 总 `we` | `let me` | 实际用到的工具 |
|---|---|---|---|---|---|---|
| **2（minimal）** | ✓ | **4** | **0** | 15 | 0 | bash + str_replace_editor（2/2） |
| 11 | ✓ | 4 | 4 | 14 | 0 | bash + list_dir + write_file（3/11） |
| 25 | ✓ | **5** | **14** | **43（2.9×）** | 0 | bash + write_file（**2/25**） |

→ 修正单轮快照结论，应用场景下：
- **工具目录越大 → 探索焦虑越重**（探索命令 0→4→14），t25 在 r3/r4 疯狂找浏览器（playwright/chrome/msedge 全探测一遍），却仍用 node --check 验证
- **产出越晚**（r4→r5）；**思考越重**（we 15→43，t25 单轮 r5 达 20,332 字符的巨长思考）
- **工具利用率极低**：t11 只用 3/11，t25 只用 2/25——绝大多数工具是噪音
- **let_me 全轨迹保持 0**：minimal 短 persona 锚定下，工具数量不直接引发 let_me（修正 test9b 单轮的 0.67 弱信号），we 轨迹稳固
- **实战最优 = 2 工具**：零探索、直接产出、思考克制

---

## 15. 封装工具 + 解释 + 推荐（test16，pro，8 相关工具，6 轮）

将外部验证器封装为专用 tool（run_node_check 提取 script 跑 node --check、html_validate 用 python html.parser 校验），4 变体：无帮助 / 解释 / 推荐 / 全有。

> ⚠️ 第一轮结果被工具 bug 污染（html_validate 变量名覆盖模块、run_python 未实现、相对路径写错目录）——模型思维链里明确说"tool bug, maybe"并被迫绕道造轮子。修复后重跑，以下为干净数据。

| 配置 | 产出 | 首写 | 探索 | errs | `we` | `let me` | 用到的工具 |
|---|---|---|---|---|---|---|---|
| A 无帮助 | ✓ | - | 0 | **7** | 35 | **0** | 4 种 |
| B 解释 | ✓ | 4 | 0 | 2 | 8 | **15** | 6 种 |
| C 推荐 | ✓ | 3 | 0 | 3 | 1 | **12** | 6 种 |
| **D 解释+推荐** | ✓ | **2** | 0 | **0** | 3 | 11 | **6 种（全）** |

**思维质量评估（读思维链原文）**：
- A：we 共同体但缺乏引导——r1 用 bash 瞎试（ls -la/sed/heredoc 在 pwsh 报错），被工作区残留文件困惑（"文件是不是 hidden setup 创建的？"）
- D：思维最清醒——r2 用 write_file 一次成稿 → r4 用 str_replace_editor 精准修复（**主动发现 ctx.roundRect 兼容性问题并加 fallback**）→ run_node_check+html_validate 并行验证 → r6 干净收尾
- **封装工具消灭验证焦虑**：零探索命令（vs test15 的 25 工具版 14 次探索找浏览器）

**⚠️ 环境归因修正（git-bash 重跑 test16b）**：A 的 errs=7 中 ~3 个是**我们的执行器问题**——bash 工具用 pwsh 模拟，模型用真 bash 语法（`ls -la`/heredoc）全部报错；改用 git-bash 执行器后 **A: errs 7→4、语法错误 0**（剩余 4 个为 POSIX /tmp 路径 vs Windows open() 不一致，同为环境问题）。**D: errs 0→1**（D 这次用了 bash grep/sed，真 bash 下正常）。修正后核心结论不变：D 工具运用 6/6、errs 最低、有主动兼容性处理；A 仍只用 3/8 工具、无主动改进。

**关键修正——let_me 不必然是坏指纹**：
- 中性工具清单（"Available tools: X (功能)"，test12）→ we 保持
- **指令式描述（"Use when you need..."）+ 推荐工作流（"Use bash only when..."）→ 触发 let_me（11-15）**——触发因子是"第二人称指令"，不是追加位置
- 但此时的 let_me 是**"有指导的执行者"**：errs=0、工具运用最全、深度验证——与焦虑型 let_me（test5 B_full 45K 自我叙述）质量天差地别

**应用结论：封装工具 + 中性解释 + 推荐工作流 = 最优组合**。工具越多越要封装（消灭探索），解释越要中性陈述（避免人格化焦虑），推荐给执行路径（消灭瞎试）。

---

## 17. 自称（we vs I）× 工具数 × 参数（test17，pro）

### Part A：工具数不影响自称（minimal persona，effort=max，6 轮 n=2）

| 工具数 | we | I | ratio |
|---|---|---|---|
| 2 | 30/23 | 0/0 | **1.0 / 1.0** |
| 11 | 16/21 | 0/0 | **1.0 / 1.0** |
| 25 | 26/25 | 0/0 | **1.0 / 1.0** |

### Part B：effort 是自称开关 🔥

| 参数 | ratio | reasoning 量 |
|---|---|---|
| **effort=low** | **0.0 / 0.0**（we=0, I=1/4）| 201 / 1137 字符 |
| effort=max | 0.94 / 1.0 | 1355 / 3602 字符 |
| temperature 0.0/1.0 | 1.0（无效单元格：thinking 下 temp 官方确认不生效）| — |
| thinking off | 1.0（不采用）| — |

**结论**：`we` 自称与深度思考绑定——effort 高时进入共同体规划模式（we，长思考），effort 低时退化为第一人称快速决策（I，短思考）。**we 是深思的外壳不是原因**：想用 we 轨迹，关键是 reasoning_effort≥high（DSH/官方默认即 high）。

---

## 18. 拆解指令 × scaffold 矩阵（test19，pro，high，并行 4 worker，6 轮 n=2）

用户消息加"先完整拆解需求（子需求/技术决策/验证步骤），拆解完再工作"。

| 格 | Scaffold | 产出 | 墙钟 | we | ratio | token | 评估 |
|---|---|---|---|---|---|---|---|
| 1b | standard 基线 | **0/2** | 100s | 43-51 | 1.0 | 11.8K | **生产禁用**：长 persona+11 工具+high = 验证焦虑，6 轮交付率 0 |
| 1a | standard+拆解 | 1/2 | 170s | 109-117 | 0.98 | 20.6K | 拆解是救命稻草（0/2→1/2，成功次 errs=0）但方差大，能救不稳 |
| 2b | minimal 基线 | 2/2 | 105s | 31-39 | 1.0 | 15.4K | 又快又稳，思考少但够用 |
| 2a | minimal+拆解 | 2/2 | 163s | **111-124（3×）** | 0.96 | 19.8K | 拆解让 minimal 深思（r1 22K 拆解思考），代价 +60s，质量/时间清晰交易 |
| 3b | minimal+工具库 | 1/1 | **88s** | 44 | 1.0 | **4.9K** | **性价比之王**：工具库自己消灭探索焦虑，无需拆解 |
| 3a | 工具库+拆解 | 2/2 | 130s | 73-106 | 0.95 | 16.2K | 拆解+工具库 = 质量成本平衡点（比 2a 省 15% token）|
| 4b | 锚定基线 | 2/2 | 123s | 34-49 | 0.92 | 19.3K | 锚定稳定，比 minimal 贵 18%（切换+前缀缓存失效成本）|
| 4a | 锚定+拆解 | 2/2 | **203s** | **129-138** | 0.98 | **24.7K** | 思考最深产出最稳但最贵（时间 2.3×/token 2.7× vs 3b），复杂高价值任务专用 |

**五条生产结论**：
1. 纯 standard 6 轮交付率 0——生产禁用；拆解指令是唯一能拉回产出的手段（1/2）
2. 拆解指令 = +60% 时间 + 1.3-1.5× token，换来 standard 复活 + minimal 思考 3×
3. minimal 系（2/3/4）产出全部稳定（11/11）；工具库最省（88s/4.9K）
4. high effort 下自称稳定 we（ratio 0.89-1.0），呼应 test17
5. **并行 4 worker 完全可行**：15/16 成功、无限流拒绝（1 个卡住是 API 慢）、~16min vs 串行 60-80min = 4× 加速零质量损失

**生产选择总表**：默认/快 → 3b（minimal+工具库）；质量优先 → 4a（锚定+拆解）；已有 standard → 1a（加拆解）；绝不 → 1b。

---

## 19. 机制模型（因果图）

```
工具名 ∈ RL 分布  ──►  思考深度（改名 → 3.6× 思考塌方）
工具数量          ──►  思考投入 + 验证焦虑（2.6× 思考量，但延迟动手）
首轮工具目录      ──►  轨迹锚定（加工具不改变思维方式，但影响动手时机）
persona 关键词    ──►  思考预算（senior 2-8.5× 于 helpful）
persona 长度/身份 ──►  人称轨迹（we 共同体 vs let me 自我）
```

**实操结论**: 又快又稳 = 首轮极简（训练内工具名 + 短 persona）+ 后续按需加工具；改名 = 打成新手模式；想要深度思考用 senior 类词（但注意同时会 we 保持、let me 不增）。

---

## 11. 文件索引

```
${PROBE_ROOT}\
├── A_game/game.html  B_game/game.html  C_game/ D_game/ E_anchored/ F_fullstart/  ← 产物
├── scripts/
│   ├── probe_common.py（minimal verbatim 资产 + 请求/执行/统计公共层）
│   ├── test1_minimal_vs_full.py  test2_tool_count.py  test3_persona_len.py
│   ├── test4_pro_check.py  test5_html_game.py  test6_persona_word.py
│   ├── test7_word_repeat.py  test8_show_raw.py  test9b_tools_only.py
│   ├── test10_anchored.py  test11_rename.py  test12_append.py
│   └── results/*.json（全部原始数据 + reasoning 原文）
```

对照基线：`xiaobright/modeltest`（11 份 DSH/OpenCode 真实轨迹：minimal we=272/231, let me=0/0 vs standard let me=208；anchored-standard 355 块仅 1 次 let me）→ 本实验全部结论与其同构。
