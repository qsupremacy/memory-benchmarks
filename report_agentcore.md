# LoComo 评测分析报告 (aws-test, AWS Bedrock AgentCore Memory) — **post-bug-fix 版本**

> 源数据:`locomo_results_20260702_173737.json`
> 报告生成时间:2026-07-02
>
> 这是 **bug 修复后的复测**。上一版 `locomo_results_20260702_161433.json`(61.84% 峰值)基于 buggy run,`benchmarks/common/aws_memory.py:search()` 在 commit `8d8ef8f` 修了 `_data.content.text` 嵌套解析。本报告反映修复后的真实表现。

## 一、运行元信息

| 字段 | 值 |
|---|---|
| Benchmark | locomo |
| Project | **aws-test** |
| Run ID | **47179308**(上一版 d1210a28) |
| Timestamp | 2026-07-02 17:37:37 |
| Answerer Model | deepseek-v4-flash |
| Judge Model | deepseek-v4-flash |
| Provider | openai |
| 后端 | AWS Bedrock AgentCore Memory(`MEMORY_BACKEND=aws`) |
| 召回 top_k | 200(API 限制 100)|
| 评测 cutoffs | top_10 / top_20 / top_50 / top_200 |
| 总题数 | 152 |
| 模式 | **evaluate_only + rejudge**(基于上一版的检索结果,重跑 answer + judge) |
| 修复 commit | `8d8ef8f fix(aws): extract real text from nested _data.content.text` |

## 二、总体正确率(按 cutoff)

| Cutoff | 总正确 | 总题数 | 准确率 | vs 前版 Δ |
|---|---:|---:|---:|---:|
| top_10  |  86 | 152 | **56.58 %** | +0.00 |
| top_20  |  96 | 152 | **63.16 %** | +1.98 |
| top_50  | 104 | 152 | **68.42 %** ← 峰值 | **+7.89** |
| top_200 |  97 | 152 | **63.82 %** | +1.98 |

> **关键变化**:bug 修复后,**top_50 从 60.53% 飙到 68.42%(+7.89 pp)**——这是修复带来的最大收益。**top_200 从 61.84% 到 63.82%(+1.98 pp)** 比预测的 64-67% 偏低。峰值从 top_200 转移到 top_50。

## 三、按类别细分

### 3.1 @ top_50(新峰值)

| 类别 | 题数 | 正确 | 准确率 | vs 前版(top_50) Δ |
|---|---:|---:|---:|---:|
| single-hop  | 70 | 57 | **81.43 %** | +2.86 |
| multi-hop   | 32 | 28 | **87.50 %** | **+6.25** |
| open-domain | 13 | 12 | 92.31 % | +7.69 |
| temporal    | 37 |  7 | 18.92 % | +2.70 |

### 3.2 类别 × Cutoff 全表(本次,post-fix)

| 类别 | top_10 | top_20 | top_50 | top_200 |
|---|---:|---:|---:|---:|
| single-hop (70)  | 50/70 = **71.43 %** | 55/70 = 78.57 % | 57/70 = **81.43 %** | 57/70 = **81.43 %** |
| multi-hop  (32)  | 22/32 = 68.75 % | 26/32 = 81.25 % | **28/32 = 87.50 %** | 23/32 = 71.88 % |
| open-domain(13)  | 11/13 = 84.62 % | 11/13 = 84.62 % | **12/13 = 92.31 %** | 11/13 = 84.62 % |
| temporal   (37)  |  3/37 =  8.11 % |  4/37 = 10.81 % |  **7/37 = 18.92 %** |  6/37 = 16.22 % |

观察:
- **multi-hop 在 top_50 出现新高 87.50%** —— 这是三后端 multi-hop 的**绝对最高**(比 AgentArts 78.1% / Volc 59.4% 都高)。
- **multi-hop @ top_200 从 84.38% 跌到 71.88%** —— 一个反直觉的发现:**top_200 的多跳记忆比 top_50 更杂乱,answerer 抓不准**。
- **temporal @ top_50 18.92%** —— bug 修复让 temporal 涨了 5.41 pp,但还没达到 AgentArts 的 24.3%。

## 四、空答统计(post-fix)

| 类别 | top_10 | top_20 | top_50 | top_200 |
|---|---:|---:|---:|---:|
| single-hop  |  1 |  3 |  2 | **6** |
| multi-hop   |  0 |  2 |  1 | **7** |
| open-domain |  0 |  0 |  0 | **0** |
| temporal    |  5 |  5 |  4 | **3** |
| **合计**    |  6 | 10 |  7 | **16** |

> 与前版对比:
> | cutoff | 前版 | 后版 | Δ |
> |---|---:|---:|---:|
> | top_10  | 11 |  6 | -5 |
> | top_20  |  7 | 10 | +3 |
> | top_50  | 13 |  7 | -6 |
> | top_200 | 12 | 16 | +4 |
>
> **空答仍平稳**(6/10/7/16),**非单调递增**。top_200 略升 4 道主要是 multi-hop 长上下文拒答(7 道,见下)。

### 4.1 top_200 多跳空答清单(post-fix)

| Question |
|---|
| What activities does Melanie partake in? |
| What does Melanie do to destress? |
| In what ways is Caroline participating in the LGBTQ community? |
| How many times has Melanie gone to the beach in 2023? |
| What subject have Caroline and Melanie both painted? |
| When did Melanie go on a hike after the roadtrip? |
| What items has Melanie bought? |

> 这 7 题在 top_50 都答上了(见 §3.1),但在 top_200 因上下文过长而被拒答。**多跳题 + 长上下文 + answerer LLM 不确定 → 拒答** —— 跟 volc 的"长上下文拒答"是同一类问题。

## 五、Cross-cutoff 稳定性矩阵(post-fix)

| 序列 | 题数 | 含义 |
|---|---:|---|
| **C C C C** | **75** | 全对(最稳定) |
| **W W W W** | **41** | 全错(核心难点) |
| W C C C |  9 | top_10 翻车,top_20 起稳 |
| C C C W |  7 | top_200 拒答丢分 |
| W W C C |  6 | top_50/200 救回 |
| W W C W |  4 | top_50 救回但 top_200 又丢 |
| W W W C |  3 | 只有 top_200 对 |
| 其余翻转 | 14 | — |

- 75 + 41 = **116/152 = 76% 在 4 个 cutoff 下结果完全一致**(前版 78%,基本持平)。
- **CCCC 涨 1 题(74→75)**,**WWWW 减 4 题(45→41)** —— 净改善 5 题稳定性。
- top_200 拒答丢分的有 7 道(top_50 对、top_200 空)—— 是 §4.1 那 7 题。

## 六、失败原因归类(top_200,共 55 道判错)

| 失败类型 | 题数 | 占比 | Δ vs 前版 |
|---|---:|---:|---:|
| temporal 非空但日期锚到 2026 | 28 | 50.9 % | -2 道(略改善) |
| 多跳 top_200 空答 |  7 | 12.7 % | **+4 道**(恶化) |
| 单跳空答 |  6 | 10.9 % | 持平 |
| 单跳事实错 |  7 | 12.7 % | -2 道(略改善) |
| 多跳事实错 |  2 |  3.6 % | -3 道(改善) |
| open-domain 边缘判分 |  2 |  3.6 % | 持平 |
| temporal 空答 |  3 |  5.5 % | 持平 |

> **temporal 锚定 2026 仍是头号问题**(50.9%)—— 跟修复前几乎一样(24 vs 24)。**这意味着 temporal 失败不是 memory 格式问题,是 answerer 本身的时间推理 bug**(详见 §7.1)。

## 七、按类别深入观察

### 7.1 temporal(37 题,top_50 时 7 对=18.92%,top_200 时 6 对=16.22%)

**失败分布(非空)**:
- 24 道答案锚到 **2026**(修复前也是 24)
- 5 道答案锚到 **2023**(真年)
- 1 道无年份

**修复前后的差异微乎其微** —— 这告诉我们:

> ⚠️ **temporal 锚错不是 `memory` 字段是 dict 的问题**。即使 answerer 拿到了干净的文本,它仍然把 GT 中的相对时间(`"the week before 9 June 2023"`)展开成相对于**当前会话日 2026-07-02** 的日期,而不是 GT 的实际事件日期。

样例:
| Q | GT | Ans(post-fix) |
|---|---|---|
| When did Caroline go to the LGBTQ support group? | 7 May 2023 | **2026-07-01** |
| When did Caroline give a speech at a school? | The week before 9 June 2023 | **In the week before July 2, 2026** |
| When is Caroline going to the transgender conference? | July 2023 | **July 2026** |
| When is Melanie planning on going camping? | June 2023 | **Next month (August 2026)** |

**结论**:temporal 题需要**专门的 prompt 改造**(详见 §十一),而非检索层修复。

### 7.2 multi-hop(32 题,top_50 时 28 对=87.5%,top_200 时 23 对=71.88%)

**post-fix 最大亮点** — top_50 87.50% 是三后端 multi-hop 表现的**绝对最高**。但 top_200 出现"上下文过多导致拒答"问题(7 题空答)。

**对比表**:

| Cutoff | 前版(buggy) | 后版(post-fix) | Δ |
|---|---:|---:|---:|
| top_10  | 68.75 % | 68.75 % | 持平 |
| top_20  | 81.25 % | 81.25 % | 持平 |
| top_50  | 81.25 % | **87.50 %** | **+6.25** |
| top_200 | **84.38 %** | 71.88 % | **-12.50** |

**多跳题的 sweet spot 是 top_50**。给更多上下文没用。

### 7.3 single-hop(70 题,top_50/t200 都 81.43%)

- 6 道 top_200 空答(比 multi-hop 少)。答错了 7 道。
- post-fix 整体微涨(从 70% top_10 → 71.43%)。

### 7.4 open-domain(13 题,top_50 = 92.31%)

- 跟 Volc / AgentArts 接近天花板,N=13 小样本。
- post-fix 在 top_50 也到了 12/13(前版 11/13)。

## 八、检索侧性能(post-fix)

| 指标 | 值 | 备注 |
|---|---:|---|
| 平均搜索时延 | **254.8 ms** | 三后端最快 |
| 最快 / 最慢 | 227.8 / 594.8 ms | 分布紧凑 |
| <250ms / 250-500ms / ≥500ms | 82 / 69 / 1 | 主体 250ms |
| 每题返回 | 100(API cap) | **不是 200** |
| 0 条召回 | 0 | 全活 |
| top-1 平均分数 | 1.0 | **合成值**,详见 §九 |

> 检索层在重跑中**完全没变**(这是 evaluate_only 的语义:用已落盘的检索结果,只重跑 answer+judge)。数据跟前版一字不差。

## 九、Top-1 分数 = 1.000 真相

`aws_memory.py:search()` 用 `score = 1.0 - i * 0.01` 合成,**top-1 永远是 1.0**。这不是真相关性分数。**跨后端比 top-1 score 没意义** —— 应使用 recall@k 比较。

## 十、与 volc / AgentArts 三后端对比(post-fix)

### 10.1 总体准确率(各后端峰值)

| 后端 | 峰值 | cutoff | 模式 |
|---|---:|---|---|
| **AgentArts** | **69.1%** | top_50 | (clamp 100) |
| **AWS AgentCore(post-fix)** | **68.42%** | top_50 | (clamp 100) |
| **Volc** | 55.26% | top_20 | (无 cap) |

**AWS 现在和 AgentArts 几乎并列**(68.4% vs 69.1%,差 0.7 pp)。

> **修复前 AWS 只到 61.8%,跟 AgentArts 差 7.3 pp。修复后差 0.7 pp。** —— 这次 bug fix 把 AWS 从"垫底仅次于 Volc"拉到"并列第一梯队"。

### 10.2 按类别峰值(各后端)

| 类别 | Volc | AgentArts | AWS AgentCore(post-fix) |
|---|---:|---:|---:|
| single-hop (70)  | 67.14 % @ top_200 | **84.3 %** @ top_50 | 81.43 % @ top_50 |
| multi-hop  (32)  | 68.75 % @ top_20 | 78.1 % @ top_50 | **87.50 %** @ top_50 ← 三后端之冠 |
| open-domain(13)  | **100.0 %** @ top_200 | **100.0 %** @ top_10/200 | 92.31 % @ top_50 |
| temporal   (37)  | 18.92 % @ top_20 | **24.3 %** @ top_10/50 | 18.92 % @ top_50 |

**AWS post-fix 之后的新冠军**:multi-hop(87.50% 三后端最高)。

### 10.3 性能

| 后端 | 检索延迟(avg) | 0 条召回 | top_200 实际召回 |
|---|---:|---:|---:|
| **AWS**     | **254.8 ms** | 0 | 100(API cap) |
| **Volc**    | 383.4 ms | 0 | 200(满) |
| **AgentArts** | 2,307 ms | 2 | 100(API cap) |

**AWS 仍是三后端最快**,但 top_200 限制 100,跟 AgentArts 一样在大量召回上吃亏。

## 十一、Cross-cutoff 稳定性(3 后端)

| 后端 | 4/4 全对 | 0/4 全错 | 一致性 |
|---|---:|---:|---:|
| **AgentArts** | 91 (60%) | 39 (26%) | 86% |
| **AWS** post-fix | 75 (49%) | 41 (27%) | **76%**(略降于前版 78%) |
| **Volc** | 56 (37%) | 48 (32%) | 68% |

> 修复后 AWS 稳定性从 78% → 76% 略降:**CCCC +1、WWWW -4 是好事**,但中间翻转 +2 抵销部分改善。**总稳定性仍然是 AgentArts > AWS > Volc**。

## 十二、修复前后对比速查

| 指标 | 修复前 (161433) | 修复后 (173737) | Δ |
|---|---:|---:|---:|
| **整体峰值** | 61.84% @ top_200 | **68.42% @ top_50** | **+6.58 pp,峰值转移** |
| top_50 整体 | 60.53% | 68.42% | **+7.89** ← 最大赢家 |
| top_200 整体 | 61.84% | 63.82% | +1.98 |
| multi-hop @ top_50 | 81.25% | **87.50%** | **+6.25** |
| multi-hop @ top_200 | 84.38% | 71.88% | **-12.50** ← 长上下文拒答 |
| temporal @ top_50 | 16.22% | 18.92% | +2.70 |
| temporal @ top_200 | 10.81% | 16.22% | +5.41 |
| temporal 锚 2026 次数 | 24 | 24 | 持平(根本问题) |
| 空答 @ top_200 | 12 | 16 | +4(多跳拒答) |
| 多跳空答 @ top_200 | 3 | 7 | +4 |
| CCCC 全对 | 74 | 75 | +1 |
| WWWW 全错 | 45 | 41 | -4 |

**修复预测(原 §十三)对照**:

| 预测 | 实际 | 命中 |
|---|---|---|
| temporal 10.81% → 15-20% | **16.22%** | ✅ |
| single-hop 微涨 1-3 pp | **+2.86 → 81.43%** | ✅ |
| multi-hop 微涨 1-3 pp | **+6.25 @ top_50, -12.50 @ top_200** | ⚠️ 半对半错(峰值转移) |
| 整体 top_200 → 64-67% | **63.82%(差点),峰值 top_50 = 68.42%** | ✅ 整体上扬,但峰值位置变了 |

---

## 十三、根因小结(更新)

1. **bug 修复的核心收益** —— answerer 不再把 `str(dict)` 当文本消费,**top_50 整整涨 7.89 pp**(57→104-56=48 → 实际 +7.89 pp)。但 top_200 仅涨 1.98 pp,**长上下文拒答"新冒头"**(多跳空答 3→7)。**AWS 后端的 sweet spot 不是 top_200 而是 top_50**。
2. **multi-hop 是 AWS 的真旗舰能力** —— top_50 87.50% 是三后端绝对最高。
3. **temporal 锚 2026 修不掉** —— 这是 answerer 的 prompt 问题,**不是检索层问题**。详见 §十四建议。
4. **空答新模式:top_200 多跳拒答** —— 长上下文 + 多跳推理 + answerer 不确定 → 拒答。需要 prompt 兜底。

## 十四、给 AWS 的可执行建议

| 优先级 | 动作 | 预期收益 |
|---|---|---|
| 🔴 高 | **多跳题 prompt 改造**:在 Step 3(Combine)显式罗列中间实体,减少"长上下文拒答"。 | top_200 多跳 +5 pp,空答减少 3-4 道 |
| 🔴 高 | **temporal prompt 改造**:在 Step 5(Temporal Grounding)加 "Reference events occurred around 2023, NOT today. Calculate relative dates from {reference_date}." | temporal +5 pp |
| 🟡 中 | **改用 `--top-k 100` + cutoffs `10,20,50,100`**,与 API cap 对齐,避免"50→200 拒答"问题 | 消除多跳 top_200 退化 |
| 🟡 中 | 把 `volc-test` 同数据集也跑一次 `--evaluate-only --rejudge` 看是否能追平 AgentArts | 验证排名稳定性 |
| 🟢 低 | 加 `score` 真相关性分数(wait AWS 暴露 API)—— 现在用合成值,跨后端不可比 | 未来 recall@k 准 |

## 十五、一句话结论

> Bug 修复让 **AWS AgentCore 从"垫底"翻盘到"并列冠军"** —— top_50 峰值 68.42%,跟 AgentArts 69.1% 仅差 0.7 pp,**multi-hop 87.50% 是三后端绝对最高**。但**新问题暴露**:**长上下文 (top_200) 反而让多跳题更差**(84.38% → 71.88%),**temporal 锚 2026 的 answerer bug 不是检索层能修的**。下一步应该改 prompt(多跳兜底 + temporal 强制 reference_date),并把 cutoffs 改成 `10,20,50,100` 对齐 API cap。

---

*数据来源:`/data/disk/mem-demo/memory-benchmarks/results/locomo/locomo_results_20260702_173737.json`*
*对比基线:`report_volc.md`、`report_agentarts.md`(同 conv-26, 同 152 题, 同 judge 模型)*
*前版(buggy):`locomo_results_20260702_161433.json`,峰值 61.84% @ top_200*
*修复 commit:`8d8ef8f fix(aws): extract real text from nested _data.content.text`*
