# volc-test vs AgentArts — LoComo 评测对比

> **好消息：两份报告有可比性**
> 两份报告均评估**同一组 152 题（conv-26）**、使用相同的 answerer 与 judge 模型（`deepseek-v4-flash`），且都跑在 `openai` 协议下。这是当前最干净的一组横向对比。

---

## 1. 可比性核对

| 维度 | `report_volc.md` | `report_agentarts.md` | 是否一致 |
|---|---|---|---|
| Benchmark | locomo | locomo | ✓ |
| 总题数 | 152 | 152 | ✓ |
| Answerer / Judge | deepseek-v4-flash / deepseek-v4-flash | deepseek-v4-flash / deepseek-v4-flash | ✓ |
| Provider | openai | openai (DeepSeek 兼容端点) | ✓ |
| top_k | 200 | 200（**实际被 AgentArts clamp 到 100**） | ⚠️ |
| 模式 | evaluate_only | evaluate_only | ✓ |
| 类别切分 | single-hop / multi-hop / temporal / open-domain | cat 1–4（顺序不同，类别相同） | ✓ |
| 题目分布 | 70 / 32 / 37 / 13 | 70 / 32 / 37 / 13 | ✓ |

**唯一变量是后端**：`volc-test`（火山引擎某种自研检索栈）vs `AgentArts Memory`（华为云 SDK + 四策略抽取）。
非变量较多，故下文可以放心地做横向比较。

---

## 2. 运行元信息

| 字段 | volc-test | AgentArts |
|---|---|---|
| Project | volc-test | smoke-test |
| Run ID | a772bd17 | bfe373f7 |
| 数据源 | `locomo_results_20260702_131625.json` | `locomo_results_20260702_112100.json` |
| Timestamp | 2026-07-02 13:16:25 | 2026-07-02 11:21:00 |

两次 run 间隔约 2 小时，跑在同一个数据集上，可视为同一时间的两次独立评估。

---

## 3. 总体准确率对比（按 cutoff）

| Cutoff | volc-test | AgentArts | Δ (pp) |
|---|---:|---:|---:|
| top_10  | 51.32 % (78/152)  | **68.4 %** (104/152) | **+17.1** |
| top_20  | **55.26 %** (84/152) | 65.1 % (99/152) | +9.9 |
| top_50  | 53.95 % (82/152)  | **69.1 %** (105/152) ← 峰值 | **+15.2** |
| top_200 | **55.26 %** (84/152) | 65.1 % (99/152) | +9.9 |

**核心结论**：
- **AgentArts 在所有 cutoff 上都领先 volc 约 10–17 pp**（绝对值非噪声，N=152 下 1 pp ≈ 1.5 题）。
- **volc 触顶于 top_20 / top_200，均为 55.26 %**，并没有随着上下文变多而提升。
- **AgentArts 在 top_50 触顶 69.1 %**，但因受 100 cap 影响，top_100 之后没有信号——**AgentArts 的 top_200 真实水平未知**。
- volc 报告指出 top_200 段过长导致空答激增（详见 §6）；AgentArts 没有这个问题，因为根本进不到 top_200。

---

## 4. 按类别对比

### 4.1 类别准确率（取各自 best cutoff）

| 类别 | volc-test @ top_200 | AgentArts @ best | Δ (pp) |
|---|---:|---:|---:|
| **single-hop** (70) | 67.14 % (47/70) | **84.3 %** (59/70, top_50) | **+17.2** |
| **multi-hop** (32) | 59.38 % (19/32) | **78.1 %** (25/32, top_50) | **+18.8** |
| **open-domain** (13) | 100.00 % (13/13) | **100.0 %** (13/13, top_200) | 0（并列） |
| **temporal** (37) | 13.51 % (5/37) | **24.3 %** (9/37, top_10/50) | **+10.8** |

**结构性观察**：
- **single-hop / multi-hop 上 AgentArts 大幅领先（+17–19 pp）** — 这是 AgentArts 的核心优势区，top-1 摘要排序对单跳尤其友好。
- **open-domain 双方都接近 100 %** — N=13 小样本下数据可信度有限，但都表明开放域问题在当前 prompt 和判分下是「白送」题。
- **temporal 双方都塌方，但 AgentArts 还是好 10.8 pp** — LOCOMO 时间题普遍偏难，这是结构性问题，不是哪家后端独有的弱点。

### 4.2 按类别 × Cutoff

**volc-test**：

| 类别 | top_10 | top_20 | top_50 | top_200 |
|---|---:|---:|---:|---:|
| open-domain   | 84.62 % | 69.23 % | 92.31 % | 100.00 % |
| single-hop    | 64.29 % | 65.71 % | 67.14 % | 67.14 % |
| multi-hop     | 59.38 % | 68.75 % | 59.38 % | 59.38 % |
| temporal      |  8.11 % | 18.92 % | 10.81 % | 13.51 % |

**AgentArts**：

| 类别 | top_10 | top_20 | top_50 | top_200 |
|---|---:|---:|---:|---:|
| single-hop (cat 4) | 82.9 % | 78.6 % | **84.3 %** | 78.6 % |
| multi-hop (cat 1)  | 75.0 % | 75.0 % | **78.1 %** | 71.9 % |
| open-domain (cat 3)| 100.0 % | 92.3 % | 92.3 % | 100.0 % |
| temporal (cat 2)   | 24.3 % | 21.6 % | 24.3 % | 21.6 % |

**对比观察**：
- volc 的 open-domain 在 top_20 出现 69.23 % 的回落然后又爬到 100 % — 这种非线性波动说明 volc 的判分不稳定，或生成在不同上下文长度下行为不一致。
- volc 的 multi-hop 在 top_20 出现 68.75 % 异常尖峰 → top_50 跌回 59.38 % — 报告本身也标记为「值得怀疑」的数据点。
- AgentArts 整体曲线更平稳（top_10 / top_50 之间最大差 4 pp），说明其检索 + 判分链路更稳定。

---

## 5. 跨 Cutoff 稳定性对比

volc 报告做了一个「同一道题在 4 个 cutoff 下的对错序列」分析（称为 cross-cutoff 稳定性矩阵）：

| 序列模式 | volc-test 题数 |
|---:|---:|
| C C C C（全对） | 56 |
| W W W W（全错） | 48 |
| 其它翻转模式 | 48 |

→ volc 共 **104/152 = 68 % 在 4 个 cutoff 下结果完全一致**，剩余 48 题在 cutoff 之间摇摆。

AgentArts 报告做了等价的「每个问题最多答对的 cutoff 数」分析：

| 答对 cutoff 数 | AgentArts 题数 |
|---:|---:|
| 4 / 4（任意 cutoff 都对） | **91** |
| 0 / 4（全错） | **39** |
| 1 / 4 | 8 |
| 2 / 4 | 7 |
| 3 / 4 | 7 |

→ AgentArts **91/152 = 60 % 全对、39/152 = 26 % 全错**（即 26% 是稳定错，14% 在中间分布）。

**对比观察**：
- **稳定正确率 AgentArts 91/152 > volc 56/152**，差 35 题。
- **稳定错误率 volc 48 > AgentArts 39**，差 9 题。
- **volc 多出的 32 道错题（约 21%）** 正好来自在不同 cutoff 之间的反复横跳，说明 volc 的判分 / 生成在 cutoff 变化时易抖动。
- AgentArts 反过来：**39 题全错是真正的能力短板**（答案提取或检索缺失），而 22 题「深度敏感」属于次要抖动。

---

## 6. 失败原因对比（仅 top_200）

### volc-test 失败归类（68 道判错）

| 失败类型 | 题数 | 占比 |
|---|---:|---:|
| **模型直接拒答 / 空答** | 34 | **50.0 %** |
| 日期与标准答案相差 >14 天容差 | 15 | 22.1 % |
| 其它原因（缺记忆、半透明判定） | 8 | 11.8 % |
| 答案非空但完全不包含正确答案 | 6 | 8.8 % |
| 内容差异（如 counseling vs adoption agencies） | 5 | 7.4 % |

volc 一个非常严重的现象：**空答随着 cutoff 增大单调递增**（15 → 18 → 24 → 35）。top_200 段越长反而诱导模型拒答。

### AgentArts 失败归类

AgentArts 报告**没有给出统一的失败归类表**，但披露了：
- 39 题「0/4 全错」——主要是检索缺失或答案提取失败
- 2 题搜到 0 条记忆（冷启动 / 抽取未完成 / 语义距离太远）

**对比观察**：
- volc 的头号失分点是 **「空答」**（占失败 50 %），根因在生成端 prompt 与上下文压缩。
- AgentArts 的头号失分点是 **「真检索/真抽取失败」**（39 题稳定全错），根因在后端算法。
- **volc 的空答是一种「浪费型失败」——给更多上下文反而更糟**；**AgentArts 的失败是「投资型失败」——边界清晰，有改进空间**。

---

## 7. 检索性能对比

| 指标 | volc-test | AgentArts |
|---|---:|---:|
| 平均检索时延 | **383.4 ms** | 2,307 ms |
| 最快检索 | 301.2 ms | 415 ms |
| 最慢检索 | 914.2 ms | 4,615 ms |
| 每题平均返回数 | 200（始终满） | 55.6（cap 100） |
| 0 条召回题数 | 未报告 | 2 |
| top-1 平均分数 | ~0.50 | 未单独报告 |

**检索性能对比**：
- **volc 比 AgentArts 快 6 倍**（383 ms vs 2307 ms），且延迟分布极紧凑（max 914 ms）。
- **volc 的 top-1 分数偏低（~0.5）** —— AgentArts 没有给出 top-1 分数，无法直接比较相关性排序质量。
- AgentArts 慢可能与它的「按四策略抽取 → 各出一条 memory」的存储结构有关（总记忆数更多，搜索面更大）。

**结论**：
- 在「快+返回满」这个维度 volc 明显更好。
- 在「相关性质量」（top-1 准确率）这个维度 AgentArts 没有数据，需要再跑一次 benchmark 才能对比。

---

## 8. 后端特性差异

| 维度 | volc-test | AgentArts |
|---|---|---|
| 部署形态 | 自研 / 接入（详情未在报告中披露） | 华为云 SDK |
| 检索上限 | 200（无 cap） | 100（API clamp） |
| 抽取策略 | 报告中未披露 | 4 策略：summary / semantic / episodic / user_preference |
| top-1 主导类型 | 未知 | summary（72 %） |
| 返回结构 | 未披露 | dict 含 metadata（space_id / strategy_type / actor_id） |
| 时间戳语义 | 未知 | SDK batch-level client time（非 message event time） |

**可改进信号**：
- volc 报告自己指出：top_10 已经能拿到 51.32 %，与 top_200 只差 4 pp——**生产场景可以只用 top_20**。
- AgentArts 报告自己指出：top-1 72 % 是 summary，对 temporal 不友好——**应该把 episodic / user_preference 的权重提上去**。

---

## 9. Root Cause 对比（小结）

| 假设的根因 | volc-test | AgentArts |
|---|---|---|
| 检索召回 | 不明显是瓶颈（top-1 0.5、调用满） | 39 题 0/4 全错表明部分题召回失败 |
| 答案生成 | **核心瓶颈**（34/68 = 50 % 空答） | 不是主要瓶颈 |
| 判分稳定性 | **次要瓶颈**（top_20 多跳异常尖峰 + 时间题锚点漂移） | 中等瓶颈（top_10 → top_20 几个 pp 漂移） |
| 时间理解 | **结构性短板**（13.51 %，日期锚到当前会话日） | **结构性短板**（24.3 %，占位偏移） |
| 长上下文处理 | **反向受限**（越大越拒答） | 受 100 cap 保护，没触发 |

---

## 10. 关键差异点（一句话）

1. **绝对正确率**：AgentArts 整体领先 volc 约 10–17 pp。
2. **失败模式**：volc 主要输给「空答」（prompt / 上下文压缩问题），AgentArts 主要输给「真检索/真抽取失败」（后端能力问题）。
3. **速度**：volc 比 AgentArts 快 6 倍。
4. **时间题**：双方都是 13–24 % 区间，属于 LOCOMO 数据集固有问题，但 AgentArts 仍领先 10 pp。
5. **建议下一步**：
   - volc 优先修空答（生成 prompt），收益最大。
   - AgentArts 优先排查 39 题 0/4 全错题，分清是检索缺还是提取错。
   - 同样建议把 AgentArts 的 top_k 上限调到 ≥200 再跑一次，确认 69.1 % 是不是真天花板。

---

*对比基于：`report_volc.md`（volc-test, 152q, deepseek-v4-flash, top_k=200）· `report_agentarts.md`（AgentArts, 152q, deepseek-v4-flash, top_k=200→100 clamp）*
*同数据集 conv-26，同 answerer+judge+provider，可直接横向对比绝对分数*
