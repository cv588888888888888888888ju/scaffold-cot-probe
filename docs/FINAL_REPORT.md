# minimal + toolkit 方案定稿报告

**日期**: 2026-08-15 | **研究对象**: deepseek-v4-pro | **状态**: 最终方案，不再迭代

---

## 1. 为什么这么做（动机链）

### 1.1 起点：厚 harness 退化模型能力
- modeltest 实测：dsv4p 在 DSH minimal = 99/96，在 standard/OpenCode/WorkBuddy = 91-93
- 官方源码实锤：minimal 发送 "exact RL prompt and schemas"（快照测试名）
- 本实验证实：standard（长 persona + 11 工具）复杂任务**交付率 0**（test19 0/2 + test20 0/2，4 格全败）

### 1.2 机制：厚 harness 退化 = 适配性下降
- dsv4p 对 scaffold 极敏感（±8 分），flash 不敏感（±1）——适配敏感性因模型而异
- 厚壳 = 把模型从训练分布拉出 → 人格化偏移（let_me 大量涌现）、工具选择焦虑、探索浪费
- **关键指纹**：we（共同体深思）= RL 训练默认轨迹；let_me（自我人格化）= 分布外偏移

### 1.3 结论：模型要跑"母语 harness"
- 但纯 minimal 只有 2 个工具，复杂任务能力不足（工具面窄）
- **解法 = minimal + toolkit**：薄 schema（母语）+ 外部工具库（补能力）
- 工具知识放**文件系统**（模型按需发现/调用），不放 schema（避免分布外干扰）

---

## 2. 最终方案（参数定稿）

```
┌─ Schema 工具（2 个，训练内命名，verbatim）────┐
│  bash + str_replace_editor                    │
├─ persona ─────────────────────────────────────┤
│  "You are a helpful software engineer assistant."（1 句，禁改动）│
├─ 外部工具库（TOOL_* 环境变量注入，bash 调用）──┤
│  只封装复杂/专有/有副作用操作：                 │
│  fetch_page / browser / search_api /          │
│  net_check / 构建链 / html2text              │
├─ 推荐（user 消息尾部，中性陈述一句）────────────┤
│  "可用: fetch_page / search_api ..."          │
├─ reasoning_effort = high（锁定）───────────────┤
└─ 上下文注入全部追加在 persona 后（\n\n 分隔）────┘
```

---

## 3. 踩过的坑（方案层面，非测试层面）

| # | 坑 | 现象 | 数据 |
|---|---|---|---|
| 1 | **工具库塞简单验证脚本** | 模型无视（bash 自己一行能做，工具无封装价值）| test22/23：verify_html rel=0，fetch_page 等 complex 5-8 次 |
| 2 | **推荐放 system prompt / schema description** | 触发 let_me 人格化（"Use when you need..."指令式）| test16：let_me 0→15 |
| 3 | **身份描述前置** | 人格化偏移（"你是谁"定义位）| test12：前置 let_me=4.0 vs 后置 0 |
| 4 | **工具改名/自定义 schema 名** | 思考塌方（RL 分布外）| test11：bash→run_command 思考量 3.6×↓ |
| 5 | **工具数量膨胀且无路由** | 探索焦虑、产出延迟、工具利用率 2/25 | test15：25 工具探索 14 次、首写晚 1 轮 |
| 6 | **拆解指令无差别加** | 过度思考（自我审查+规划非必要步骤），引向便利工具陷阱 | test20：4a we=407 但踩 optimize 陷阱（靠验证排雷）|

> **核心启示：不要乱加思维引导。** 任何思维引导（拆解指令/CoT 提示/思考步骤要求）都是对 RL 默认轨迹的干预——minimal 的 we 深思轨迹是训练默认，加引导 = 把模型推出默认轨迹。只有任务确实需要（复杂/多步骤/易漏）才值得加，且要承担时间与 token 成本（1.3-1.6×）。**引导是药，不是饭。**
| 7 | **effort 低于 high** | 自称翻转 we→I，浅思考 | test17：effort=low ratio 1.0→0.0 |
| 8 | **全 standard 厚壳** | 稳定交付率 0（不是偶发）| test19 0/2 + test20 0/2 |
| 9 | **无推荐** | 模型自己干，工具库形同虚设 | test23：无推荐 complex_uses 0-1 vs 有推荐 5-8 |
| 10 | **验证类工具不可信/坏资产** | 模型无法验证 → 信任崩塌或盲信 | test16 第一轮（工具 bug 污染）；原则：验证工具必须可信 |

---

## 4. 已验证的能力边界

- **容错设计**：minimal+toolkit 在 25 轮复杂任务交付 12/12 模块，坏资产全量兜底（Promise.allSettled/fallback 合成），不依赖知道"哪个坏"
- **查证能力**：伪站错误声明 3/4 判对，模型能跟链接跳转、站内交叉验证、公网核实
- **陷阱免疫**：无便利工具依赖 → 天然不踩；用便利工具后靠验证排雷
- **思维质量**：we 纯正（ratio 0.96-0.99），有效思考密度高（决策直落最优，无需 10K 拆解）

---

## 5. 生产部署建议

1. schema 恒为 bash+editor（训练内），新能力一律走工具库
2. 工具库只收"封装价值"工具：复杂链路、专有知识、副作用操作
3. 推荐按任务路由 2-3 个相关工具，user 消息尾中性注入
4. effort 锁定 high；工具库脚本可信可审计
5. 每个模型配独立模板（per-model 适配，见《追加 A：模型适配层设计》）

---

*定稿。测试数据全量见 EXPERIMENT_REPORT.md（1-19 节）与各 results/*.json。*
