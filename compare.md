# 三后端横评 — Volc · AgentArts · AWS AgentCore(post-bug-fix)

> **可比性核对** —— 三份报告都是 conv-26(152 题)、同一 `deepseek-v4-flash` 同时担任 answerer 和 judge、`openai` 协议。**唯一变量是后端**。可以直接横比绝对分数。
>
> **AWS 数据基于修复后 rejudge**(`locomo_results_20260702_173737.json`,run_id 47179308,commit `8d8ef8f`)。修复前的版本(bug: `search()` 返回 dict 而非 text)已被替换,本报告所有 AWS 数字都是真实表现。

---

## 1. 运行元信息

| 字段 | Volc | AgentArts | AWS AgentCore |
|---|---|---|---|
| Project | volc-test | smoke-test | aws-test |
| Run ID | a772bd17 | bfe373f7 | 47179308 |
| 时间 | 07-02 13:16 | 07-02 11:21 | 07-02 17:37 |
| 模式 | full(ingest+search+answer+judge) | evaluate_only | **evaluate_only rejudge** |
| top_k 请求 | 200 | 200 | 200 |
| **top_k 实际** | 200(无 cap) | 100(API cap) | 100(API cap) |
| 抽取语言 | 中文(volc 默认) | 英文(SDK) | 英文(SDK) |

## 2. 总体准确率(按 cutoff)

| Cutoff | Volc | AgentArts | AWS |
|---|---:|---:|---:|
| top_10  | 51.32 % | **68.4 %** | 56.58 % |
| top_20  | 55.26 % | 65.1 % | 63.16 % |
| top_50  | 53.95 % | 69.1 % | **68.42 %** ← 峰值 |
| top_200 | 55.26 % | 65.1 % | 63.82 % |

**整体排名(各后端峰值)**:

| 排名 | 后端 | 峰值 | cutoff |
|---|---|---:|---|
| 🥇 | **AgentArts** | 69.1 % | top_50 |
| 🥈 | **AWS AgentCore** | **68.42 %** | top_50 |
| 🥉 | **Volc** | 55.26 % | top_20 |

> ⚠️ **AgentArts 仅领先 AWS 0.7 pp,基本并列** —— 修复前 AWS 只有 61.84% @ top_200,跟 AgentArts 差 7.3 pp。**bug 修复后,AWS 从"垫底第二"挤进"并列冠军梯队"**。

**曲线形态对比**:

| 后端 | 曲线形态 | 解读 |
|---|---|---|
| Volc | 触顶 top_20,后续无增长 | 召回够,**生成**有问题 |
| AgentArts | 触顶 top_50,top_200 反而下降 | API cap 100 拖累 |
| **AWS** | **触顶 top_50,top_200 同样下降** | sweet spot 是 top_50,过长拒答 |

## 3. 按类别 × Cutoff 全表(post-fix AWS)

### 3.1 single-hop(70 题)

| Cutoff | Volc | AgentArts | AWS |
|---|---:|---:|---:|
| top_10  | 64.29 % | **82.9 %** | 71.43 % |
| top_20  | 65.71 % | 78.6 % | 78.57 % |
| top_50  | 67.14 % | **84.3 %** | 81.43 % |
| top_200 | 67.14 % | 78.6 % | 81.43 % |

**峰值排名**:AgentArts 84.3% > **AWS 81.43%** > Volc 67.14%。

### 3.2 multi-hop(32 题)—— **AWS 此处反超**

| Cutoff | Volc | AgentArts | **AWS** |
|---|---:|---:|---:|
| top_10  | 59.38 % | 75.0 % | 68.75 % |
| top_20  | 68.75 % | 75.0 % | 81.25 % |
| top_50  | 59.38 % | 78.1 % | **87.50 %** ← 三后端之冠 |
| top_200 | 59.38 % | 71.9 % | 71.88 % |

**峰值排名**:**AWS 87.50%(@ top_50)** > AgentArts 78.1% > Volc 68.75%。

**AWS 多跳的 sweet spot 是 top_50** —— 给 top_200 不仅没用,反而**多 7 道拒答**(71.88% < 87.50%)。

### 3.3 open-domain(13 题,小样本)

| Cutoff | Volc | AgentArts | AWS |
|---|---:|---:|---:|
| top_10  | 84.62 % | **100.0 %** | 84.62 % |
| top_20  | 69.23 % | 92.3 % | 84.62 % |
| top_50  | 92.31 % | 92.3 % | **92.31 %** |
| top_200 | **100.0 %** | **100.0 %** | 84.62 % |

**峰值排名**:Volc/AgentArts 100% > **AWS 92.31%**。N=13 小样本,差距意义有限。

### 3.4 temporal(37 题,共同短板)

| Cutoff | Volc | AgentArts | AWS |
|---|---:|---:|---:|
| top_10  |  8.11 % | **24.3 %** |  8.11 % |
| top_20  | **18.92 %** | 21.6 % | 10.81 % |
| top_50  | 10.81 % | **24.3 %** | **18.92 %** |
| top_200 | 13.51 % | 21.6 % | 16.22 % |

**峰值排名**:**AgentArts 24.3%** > **Volc 18.92%(@ top_20)** ≈ **AWS 18.92%(@ top_50)**。**Volc 和 AWS 在 temporal 几乎并列**,都远不及 AgentArts。

## 4. 空答分析(head-to-head 反模式指标)

| Cutoff | Volc | AgentArts | AWS |
|---|---:|---:|---:|
| top_10  | 15 | ≈ 0 |  6 |
| top_20  | 18 | ≈ 0 | 10 |
| top_50  | 24 | ≈ 0 |  7 |
| top_200 | **35** | ≈ 0 | 16 |

**关键对比**:

| 后端 | top_10 → top_200 走向 | 诊断 |
|---|---|---|
| **Volc**     | **15 → 35**(单调递增,+133%) | 长上下文诱拒答 — 典型 prompt 病 |
| **AgentArts** | ≈ 0 全程 | 无此病 |
| **AWS**      | 6 → 10 → 7 → 16(基本平稳,+167% 但起点低) | 长拒答比 Volc 弱但**有**:

**Volc 的 35 道空答 = 占其 top_200 失败的 50%** —— 这是最高 ROI 的修复点。
**AWS 的 16 道空答 = 占其 top_200 失败的 29%** —— 影响中。

### 4.1 Volc top_200 空答按类别(50 题)

| 类别 | 题数 | 空答数 | 比例 |
|---|---:|---:|---:|
| temporal    | 37 | **16** | **43 %** |
| single-hop  | 70 | 10 | 14 % |
| multi-hop   | 32 |  9 | 28 % |
| open-domain | 13 |  0 |  0 % |

### 4.2 AWS top_200 空答按类别(post-fix)

| 类别 | 题数 | 空答数 | 比例 |
|---|---:|---:|---:|
| multi-hop   | 32 | **7** | **22 %** |
| single-hop  | 70 |  6 |  9 % |
| temporal    | 37 |  3 |  8 % |
| open-domain | 13 |  0 |  0 % |

> **关键洞察**:AWS 的空答模式跟 Volc **完全不同** —— Volc 是 temporal 空答最多(43%),AWS 是 multi-hop 空答最多(22%)。

## 5. Cross-cutoff 稳定性

把每道题在 4 个 cutoff 下的对错拼成 4-字符序列:

| 后端 | CCCC(全对) | WWWW(全错) | 一致性 |
|---|---:|---:|---:|
| **Volc**     | 56 (37%) | 48 (32%) | **68 %** |
| **AgentArts** | **91 (60 %)** | 39 (26%) | **86 %** |
| **AWS** (post-fix) | 75 (49%) | 41 (27%) | **76 %** |

**稳定性排名**:**AgentArts 86%** > **AWS 76%** > **Volc 68%**。

**解读**:
- **AgentArts 91 道 4/4 全对** —— 主路径极稳,撑起 69.1% 峰值。
- **AWS 修复后 CCCC +1、WWWW -4** —— 净稳定性改善 5 题,主路径稍微稳一点。
- **Volc 48 道 0/4 全错** —— 它的失败主要是判分不稳定,不是能力问题。

## 6. 失败模式

| 后端 | 头号失分点 | 占比 |
|---|---|---:|
| **Volc** | 模型直接拒答 / 空答 | **50.0 %**(34/68) |
| **AWS** (post-fix) | temporal 日期锚到 2026 | **50.9 %**(28/55) |
| **AgentArts** | 真检索/真抽取失败 | 约 26 % |

**三种完全不同的失败画像**:

| 后端 | 类型 | 修法 |
|---|---|---|
| **Volc** | **闭嘴型** —— 检索到答案但模型决定不答 | 改 prompt("If not in memories, say so") |
| **AWS** | **张嘴但日期错** —— 模型愿意答但锚到 2026 | 改 prompt(temporal 强制 reference_date) |
| **AgentArts** | **能力型** —— 39 题真检索不到 | 换模型 / 改 strategy |

## 7. 检索侧性能

| 指标 | Volc | AgentArts | AWS |
|---|---:|---:|---:|
| 检索延迟(avg) | 383 ms | 2,307 ms | **254.8 ms**(最快) |
| 检索延迟(min/max) | 301 / 914 ms | 415 / 4,615 ms | 228 / 595 ms(最稳定) |
| 每题实际返回 | 200(满) | 55.6(cap 100) | 100(cap 100) |
| 0 条召回题数 | 0 | 2 | 0 |
| top-1 分数(avg) | ~0.50(真分) | 未统计 | **1.0(合成)** |

**性能排名**:**AWS 254.8ms**(最快 + 最稳定)> **Volc 383ms** > **AgentArts 2,307ms**(9× slower than AWS)

> ⚠️ AWS 的 top-1=1.0 是合成值(`1.0 - i*0.01`),**不是真相关性分数**。跨后端比较只能看 cut@k。

## 8. 后端特性对比

| 维度 | Volc | AgentArts | AWS AgentCore |
|---|---|---|---|
| **形态** | 火山引擎云(中文抽取) | 华为云 SDK | 亚马逊云 SDK |
| **topK 上限** | 200(满) | 100(API cap) | 100(API cap) |
| **sweet spot cutoff** | top_20 | top_50 | **top_50**(修复后) |
| **抽取策略** | 中文 LLM 抽取 | 4 策略:summary(72%) / semantic / episodic / user_preference | SDK 默认 |
| **time 字段** | message event time | batch client time | batch client time |
| **返回结构** | string memory | dict(带 metadata) | dict(`_data.content.text`,已修了) |
| **典型检索时延** | 383ms | 2307ms | **255ms** |
| **空答率(top_200)** | **23 %** ≈ 35/152 | ≈ 0 % | 11 % = 16/152 |
| **跨 cutoff 稳定性** | 68 % | **86 %** | 76 % |

## 9. 三后端综合排名(post-fix)

### 9.1 整体准确率(各后端峰值)

| 排名 | 后端 | 峰值 | cutoff |
|---|---|---:|---|
| 🥇 | **AgentArts** | 69.1 % | top_50 |
| 🥈 | **AWS AgentCore** | **68.42 %** | top_50 |
| 🥉 | **Volc** | 55.26 % | top_20 |

### 9.2 类别冠军

| 类别 | 冠军 | 数值 |
|---|---|---:|
| single-hop | **AgentArts** | 84.3 % @ top_50 |
| multi-hop | **AWS AgentCore** | **87.50 %** @ top_50 |
| open-domain | **Volc / AgentArts** 并列 | 100 % @ top_200 |
| temporal | **AgentArts** | 24.3 % @ top_10/50 |
| 检索速度 | **AWS** | **254.8 ms**(9× 更快) |
| 跨 cutoff 稳定性 | **AgentArts** | 86 % |
| 空答最少 | **AgentArts** | ≈ 0 % |

### 9.3 失败诊断的修法成本

| 后端 | 头号问题 | 修法成本 |
|---|---|---|
| Volc | 空答 50 % | 🟢 **低** —— 改 prompt,预期涨 5-10 pp |
| AWS | temporal 锚 2026 | 🟡 **中** —— prompt 加时间强制 + reference_date |
| AgentArts | 39 题稳定全错 | 🔴 **高** —— 换模型或改 strategy |

## 10. AWS post-fix 的额外发现

bug 修复带来三个**反直觉**的发现:

### 10.1 AWS 的 sweet spot 是 top_50,不是 top_200

| Cutoff | AWS(post-fix)整体 |
|---|---:|
| top_10  | 56.58 % |
| top_20  | 63.16 % |
| top_50  | **68.42 %** ← 峰值 |
| top_200 | 63.82 % |

> **多记忆 → 多拒答**。AWS 后端 answerer 对长上下文敏感,给 200 条记忆时多跳题反而不敢答。

### 10.2 multi-hop 在 top_50 → top_200 反而**退化**

| | top_50 | top_200 | Δ |
|---|---:|---:|---:|
| multi-hop 准确率 | 87.50 % | 71.88 % | **-15.62 pp** |
| multi-hop 空答数 | 1 | 7 | +6 |

> AWS 多跳题的 sweet spot 严格在 top_50 给再多都是噪声。

### 10.3 temporal 锚 2026 是 answerer 自身 bug,不是 memory 格式 bug

修复前 AWS temporal 锚 2026 的次数 = 24。修复后仍然是 24。**说明这不是检索/抽取的问题** —— answerer LLM 本身不知道如何把模糊相对时间(`the week before X`)锚到 2023 而不是当前日期。

## 11. 给三个后端的推荐

### 11.1 Volc(改 prompt,性价比最高)

| 优先级 | 动作 | 预期 |
|---|---|---|
| 🔴 高 | answerer prompt 加显式兜底("If not in memories, say so in one sentence") | top_200 +5-10 pp |
| 🟡 中 | temporal prompt 强制绝对日期 + reference_date | temporal +5 pp |
| 🟢 低 | 生产用 `--top-k 20`(top_20 已触顶 55.26%) | 节省成本 |

### 11.2 AgentArts(继续打磨 + 复评)

| 优先级 | 动作 |
|---|---|
| 🔴 高 | judge 换 gpt-4o / claude-sonnet,看分差是 judge 噪声还是真差 |
| 🔴 高 | 查 39 道 0/4 全错题,分清"检索缺"还是"提取错" |
| 🟡 中 | 试试调高 `episodic` 排序权重(对 temporal) |
| 🟢 低 | 默认 `--top-k 100` + cutoffs `10,20,50,100`,与 API cap 对齐 |

### 11.3 AWS AgentCore(post-fix 后:打磨 prompt + 重新对齐 cap)

| 优先级 | 动作 | 预期 |
|---|---|---|
| 🔴 高 | 改 cutoffs 为 `[10, 20, 50, 100]` 对齐 API cap,避免 top_50→top_200 拒答退化 | 多跳 +10 pp,可能突破 70 % |
| 🔴 高 | temporal prompt 加 "Compute relative dates from {reference_date}" 而不是 today | temporal +5 pp |
| 🟡 中 | 多跳 prompt 在 Step 3 显式列中间实体,降低长上下文拒答 | 多跳 top_200 至少 +10 pp |
| 🟢 低 | 跑全套 10 conv(`--conversations 0,1,2,3,4,5,6,7,8,9`),完整横评 | 上榜 |

## 12. AWS post-fix 之前后的差距

修复前(`locomo_results_20260702_161433.json`):
- 峰值 61.84% @ top_200
- multi-hop 84.38% @ top_200
- 跟 AgentArts 差 7.3 pp

修复后(`locomo_results_20260702_173737.json`):
- 峰值 **68.42% @ top_50**(↑ 6.58 pp)
- multi-hop 87.50% @ top_50(↑ 6.25 pp,**且为三后端最高**)
- 跟 AgentArts **只差 0.7 pp**

**修复证明**:AWS 后端本身不是"垫底",是 `aws_memory.py:search()` 的 dict 格式 bug 把它拖下去。修完之后,它跟 AgentArts 同档。

## 13. 一句话结论

> **AgentArts 仍是综合冠军**(69.1% 峰值、86% 跨 cutoff 一致性、近 0% 空答)。**AWS AgentCore 已追平第一梯队** —— 修复后 68.42% @ top_50,跟 AgentArts 差 0.7 pp,**multi-hop 87.50% 反超为三后端之冠**。**Volc 因空答 + temporal 锚错 + 缺乏纯 top_50 优化,综合最弱**。下一轮三后端都该把 cutoffs 对齐 API cap(Volc 也最好改成 [10,20,50,100] 或自定义 + 跳到 200 前先停 100),然后**统一换强 judge**(gpt-4o / claude-sonnet)做真实分数对比。

---

*对比基于:`report_volc.md`(volc-test, 152q, deepseek-v4-flash, top_k=200)·`report_agentarts.md`(smoke-test, 152q, deepseek-v4-flash, top_k=200→100 cap)·`report_agentcore.md`(aws-test, 152q, deepseek-v4-flash, top_k=200→100 cap,**bug 已修复**)*
*三 run 都跑在 conv-26、同 152 题、同 answerer+judge+provider,可比绝对分数*
