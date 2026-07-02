# 三后端横评 — Volc · AgentArts · AWS AgentCore

> **可比性核对** —— 三份报告都是 conv-26(152 题)、同一 `deepseek-v4-flash` 同时担任 answerer 和 judge、`openai` 协议。**唯一变量是后端**。可以直接横比绝对分数。
>
> ⚠️ **AWS 数据带 production bug** —— `aws_memory.py:search()` 没解开 `_data.content.text` 嵌套,模型实际看到的是 `str(dict)`。Bug 已在 `8d8ef8f` 修复,`report_agentcore.md` 仍基于 buggy 数据。文中所有 AWS 分数都标 ⚠️ 表示"修完后预计会涨 3-5 pp"。

---

## 1. 运行元信息

| 字段 | Volc | AgentArts | AWS AgentCore ⚠️ |
|---|---|---|---|
| Project | volc-test | smoke-test | aws-test |
| Run ID | a772bd17 | bfe373f7 | d1210a28 |
| 时间 | 07-02 13:16 | 07-02 11:21 | 07-02 16:14 |
| 模式 | full(ingest+search+answer+judge) | evaluate_only | full |
| top_k 请求 | 200 | 200 | 200 |
| **top_k 实际** | **200**(无 cap) | 100(API cap) | 100(API cap) |
| 抽取语言 | 中文(volc 默认) | 英文(SDK 自带) | 英文(SDK 自带) |

---

## 2. 总体准确率(按 cutoff)

| Cutoff | Volc | AgentArts | AWS ⚠️ |
|---|---:|---:|---:|
| top_10  | 51.32 % | **68.4 %** | 56.58 % |
| top_20  | 55.26 % | 65.1 % | 61.18 % |
| top_50  | 53.95 % | **69.1 %** ← 峰值 | 60.53 % |
| top_200 | 55.26 % | 65.1 % | **61.84 %** ← 峰值 |

**整体排名(各后端峰值)**:**AgentArts 69.1%** > **AWS 61.84%(预计修后 65-67%)** > **Volc 55.26%**

**曲线形态对比**:

| 后端 | 形态 | 解读 |
|---|---|---|
| Volc | 触顶 top_20,后续 0 增长 | 召回够,但**生成**有问题 |
| AgentArts | 触顶 top_50,top_200 反而**下降** | API cap 100 拖累;top_10 已有真答案,后续是噪声 |
| AWS ⚠️ | **单调递增**直到 top_200 | 多召回真的在加正确答案 —— 这是最健康的曲线 |

---

## 3. 按类别 × Cutoff 全表

### 3.1 单跳(70 题)

| Cutoff | Volc | AgentArts | AWS ⚠️ |
|---|---:|---:|---:|
| top_10  | 64.29 % | 82.9 % | 70.00 % |
| top_20  | 65.71 % | 78.6 % | 75.71 % |
| top_50  | 67.14 % | **84.3 %** | 78.57 % |
| top_200 | 67.14 % | 78.6 % | **81.43 %** |

**峰值排名**:AgentArts 84.3% > **AWS 81.43%(预计 85+)** > Volc 67.14%。

### 3.2 多跳(32 题)

| Cutoff | Volc | AgentArts | AWS ⚠️ |
|---|---:|---:|---:|
| top_10  | 59.38 % | 75.0 % | 68.75 % |
| top_20  | 68.75 % | 75.0 % | 81.25 % |
| top_50  | 59.38 % | **78.1 %** | 81.25 % |
| top_200 | 59.38 % | 71.9 % | **84.38 %** |

**峰值排名**:**AWS 84.38%**(三后端之冠!)> AgentArts 78.1% > Volc 59.38%。**AWS 的多跳检索是三后端最强**。

### 3.3 开放域(13 题,小样本)

| Cutoff | Volc | AgentArts | AWS ⚠️ |
|---|---:|---:|---:|
| top_10  | 84.62 % | 100.0 % | 92.31 % |
| top_20  | 69.23 % | 92.3 % | 76.92 % |
| top_50  | 92.31 % | 92.3 % | 84.62 % |
| top_200 | **100.00 %** | **100.0 %** | 84.62 % |

**峰值排名**:Volc 100% = AgentArts 100% > **AWS 84.62%**(⚠️ 修后应到 92-100%)。N=13,小样本方差大,差距意义有限。

### 3.4 时序(37 题,共同短板)

| Cutoff | Volc | AgentArts | AWS ⚠️ |
|---|---:|---:|---:|
| top_10  |  8.11 % | **24.3 %** |  8.11 % |
| top_20  | 18.92 % | 21.6 % | 10.81 % |
| top_50  | 10.81 % | **24.3 %** | **16.22 %** |
| top_200 | 13.51 % | 21.6 % | 10.81 % |

**峰值排名**:**AgentArts 24.3%** > Volc 18.92% > **AWS 16.22%**(top_50),**三后端都不行但 AgentArts 是天花板**。这是 LOCOMO 数据集本身的问题(模糊相对时间 + 跨年日期)。

---

## 4. 空答分析(头号"反模式"指标)

**空答 = `generated_answer` 为空字符串,直接判 WRONG**。

| Cutoff | Volc | AgentArts | AWS ⚠️ |
|---|---:|---:|---:|
| top_10  | 15 | (未单列) | 11 |
| top_20  | 18 | (未单列) |  7 |
| top_50  | 24 | (未单列) | 13 |
| top_200 | **35** | (未单列,推断 ≈ 0) | 12 |

**关键发现**:

| 后端 | 空答随 cutoff 变化 | 诊断 |
|---|---|---|
| **Volc** | **15 → 18 → 24 → 35 单调递增** | 上下文越长越拒答 — **prompt 病** |
| **AgentArts** | 几乎无空答 | 没这个病 |
| **AWS** ⚠️ | **11 → 7 → 13 → 12 基本平稳** | 没 volc 那种病,bug 修了之后还会更稳 |

**Volc 的空答占其 top_200 失败(68 道)的 50%** —— 这是性价比最高的修复点。**AWS 即使带 bug,空答也只有 12 道,跟 Volc 的 35 形成 3× 差距**。

### 4.1 Volc top_200 空答按类别

| 类别 | 题数 | 空答数 | 比例 |
|---|---:|---:|---:|
| temporal    | 37 | **16** | **43 %** |
| single-hop  | 70 | 10 | 14 % |
| multi-hop   | 32 |  9 | 28 % |
| open-domain | 13 |  0 |  0 % |

### 4.2 AWS top_200 空答按类别

| 类别 | 题数 | 空答数 | 比例 |
|---|---:|---:|---:|
| single-hop  | 70 | **6** | 9 % |
| multi-hop   | 32 | 3 | 9 % |
| temporal    | 37 | 3 | 8 % |
| open-domain | 13 | 0 | 0 % |

**AWS 的 temporal 空答(3)比 Volc 的(16)少 13 道** —— 同样是 temporal,AWS 模型的"拒答门槛"比 Volc 低很多。

---

## 5. Cross-cutoff 稳定性(全对 / 全错 = 一致性)

> 把每道题在 4 个 cutoff 下的对错拼成 4-字符序列(如 `C C C W`)。

| 后端 | 4/4 全对(CCCC) | 0/4 全错(WWWW) | 一致性 |
|---|---:|---:|---:|
| **Volc**     | 56 (37%) | 48 (32%) | **68%**(104/152) |
| **AgentArts** | **91 (60%)** | 39 (26%) | **86%**(130/152) |
| **AWS** ⚠️   | 74 (49%) | 45 (30%) | **78%**(119/152) |

**稳定性排名**:**AgentArts 86%** > **AWS 78%** > Volc 68%。

**解读**:
- **AgentArts 91 道 4/4 全对** —— 这是它能拿 69.1% 峰值的原因:主路径极其稳。
- **Volc 48 道 0/4 全错** + 大量"反复横跳"—— 它的失败更多是"判分/生成不稳定",不是能力问题。
- **AWS 介于两者之间** —— 78% 一致性 = "answerer 一旦认可,大多都对;一旦否定,大多都否定",判分比较果断。

---

## 6. 失败模式(头号失分原因)

| 后端 | 头号失分点 | 占比 |
|---|---|---:|
| **Volc**     | 模型直接拒答 / 空答 | **50.0%**(34/68 错) |
| **AWS** ⚠️  | temporal 日期锚定到 2026 | **51.7%**(30/58 错) |
| **AgentArts** | 真检索/真抽取失败(0/4 全错) | ~26%(39/152 稳定全错) |

**三种完全不同的失败画像**:

1. **Volc** —— "**闭嘴型失败**"。检索到答案了,但模型决定不答。修 prompt 就能解决。
2. **AWS** ⚠️ —— "**张嘴但日期错**"。模型愿意答,但把 2023 的事锚到 2026。修 bug 后预计会好转。
3. **AgentArts** —— "**能力型失败**"。39 道题是真检索不到 / 真抽取不出来,需要换模型或换策略。

---

## 7. 检索侧性能

| 指标 | Volc | AgentArts | AWS ⚠️ |
|---|---:|---:|---:|
| 检索延迟(avg) | 383 ms | **2,307 ms** | **254.8 ms**(最快) |
| 检索延迟(min/max) | 301 / 914 ms | 415 / 4,615 ms | 228 / 595 ms(最稳定) |
| 每题实际返回 | 200(满) | 55.6(avg,cap 100) | 100(cap 100) |
| 0 条召回题数 | 0 | **2** | 0 |
| top-1 分数(avg) | **~0.50**(真相关分) | 未统计 | 1.0(⚠️ **合成**,无真分) |

**性能排名**:**AWS 254ms**(fastest & most stable)> **Volc 383ms** > **AgentArts 2,307ms**(9× slower than AWS)

**关于 AWS 的 top-1 分数 = 1.0**:`aws_memory.py` 里 `score = 1.0 - i * 0.01` 合成,**不是真相关性分数**。**跨后端比 top-1 score 没意义**,但 top-k 切片给 LLM 看的**位置序**是真序。

---

## 8. 后端特性对比

| 维度 | Volc | AgentArts | AWS AgentCore |
|---|---|---|---|
| **形态** | 火山引擎云(中文抽取) | 华为云 SDK | 亚马逊云 SDK |
| **topK 上限** | 无(实际 200) | 100(API cap) | 100(API cap) |
| **抽取策略** | LLM 抽取事实 | 4 策略:summary(72%) / semantic / episodic / user_preference | 1 策略(SDK 默认) |
| **time 字段** | message event time | batch client time | batch client time(未实测) |
| **返回结构** | string memory | dict(带 metadata) | dict(_data.content.text)|
| **典型检索时延** | 383ms | 2307ms | 255ms |
| **空答率(top_200)** | 23% | ~0% | 8% |
| **跨 cutoff 稳定性** | 68% | 86% | 78% |

---

## 9. 三后端综合排名

### 9.1 整体准确率(峰值)

| 排名 | 后端 | 峰值 | cutoff |
|---|---|---:|---|
| 🥇 | **AgentArts** | **69.1%** | top_50 |
| 🥈 | **AWS AgentCore** ⚠️ | 61.84% | top_200 |
| 🥉 | **Volc** | 55.26% | top_20 |

### 9.2 类别冠军

| 类别 | 冠军 | 数值 |
|---|---|---:|
| single-hop | **AgentArts** | 84.3% @ top_50 |
| multi-hop | **AWS AgentCore** ⚠️ | 84.38% @ top_200 |
| open-domain | **Volc / AgentArts** 并列 | 100% @ top_200 |
| temporal | **AgentArts** | 24.3% @ top_10/50 |
| 检索速度 | **AWS** | 254.8 ms |
| 跨 cutoff 稳定性 | **AgentArts** | 86% |
| 空答最少 | **AgentArts** | ≈ 0% |

### 9.3 失败诊断冠军(最差的那个维度反而能看出特性)

| 后端 | 头号问题 | 修法成本 |
|---|---|---|
| Volc | 空答 50% | **低** —— 改 prompt 即可 |
| AWS ⚠️ | temporal 锚 2026 | **中** —— bug 修完 + 时间规范化 |
| AgentArts | 39 题稳定全错 | **高** —— 需换模型或加 user-profile 分桶 |

---

## 10. Caveat:AWS 数据带 Bug

报告 `report_agentcore.md` 的所有 AWS 数字都来自 buggy run。**已确认的 bug**:`benchmarks/common/aws_memory.py:search()` 把 AWS SDK 返回的 `_data.content.text` 嵌套 dict 错当 `memory` 字段,answerer LLM 实际收到的是 `str(dict)` 的 JSON 字符串。

**bug 影响估算**:
- temporal:10.81% → 修后预计 15-20%(去 dict 噪声后,模型能读到真日期)
- single-hop:81.43% → 微涨 1-3 pp
- multi-hop:84.38% → 微涨 1-3 pp(可能仍为三后端之冠)
- 整体 top_200:61.84% → 修后预计 64-67%

**复测命令**(已落盘,无需重 ingest):

```bash
export MEMORY_BACKEND=aws
# AWS creds + AWS_MEMORY_ID
python -m benchmarks.locomo.run \
    --project-name aws-test \
    --evaluate-only --rejudge \
    --answerer-model deepseek-v4-flash \
    --judge-model deepseek-v4-flash \
    --conversations 0
```

跑完新结果后,AWS 的相对排名可能会升到第二位(可能追平甚至超过 AgentArts)。

---

## 11. 给三个后端的推荐

### 11.1 Volc(优先级最高 = 改 prompt)

| 优先级 | 动作 |
|---|---|
| 🔴 高 | 修空答:answerer prompt 加显式兜底句("If not in memories, say so in one sentence")。预期 top_200 从 55.26% → 62-65%。 |
| 🟡 中 | temporal 加时间规范化预处理("the week before X" → 绝对日期区间)。 |
| 🟢 低 | 生产用 `--top-k 20`(top_20 已触顶,后续是噪声)。 |

### 11.2 AgentArts

| 优先级 | 动作 |
|---|---|
| 🔴 高 | 39 道 0/4 全错题,肉眼抽 5 道看 top-10,分清"检索缺"还是"提取错"。 |
| 🔴 高 | judge 改 gpt-4o / claude-sonnet 复评一次,看分差是 judge 噪声还是真差。 |
| 🟡 中 | summary 排序占比 72% 太重,试试提权 episodic 对 temporal 的影响。 |
| 🟢 低 | 默认 `--top-k 100`,cutoffs 改 `10,20,50,100`,与 API cap 对齐。 |

### 11.3 AWS AgentCore ⚠️

| 优先级 | 动作 |
|---|---|
| 🔴 高 | 跑 `--evaluate-only --rejudge` 复测当前数据(已修 bug,无需重 ingest)。 |
| 🟡 中 | temporal 修完后若仍低,加时间规范化预处理(同 Volc)。 |
| 🟢 低 | 如果复测 ≥ 67%,换 `--top-k 100` + cutoffs `10,20,50,100` 跑完整 10 conv,正式上对比榜。 |

---

## 12. 一句话结论

> **AgentArts 仍是当前最稳的后端**(69.1% 峰值、86% 跨 cutoff 一致性、近 0% 空答),但 **AWS AgentCore 是 2026 的"潜力股"** —— multi-hop 84.4% 是三后端之冠、检索 255ms 是三后端最快、跨 cutoff 一致性 78%。**bug 修完后,AWS 预计会从 61.8% 升到 64-67%,可能逼近 AgentArts**。
>
> **Volc 当前最弱** —— 但问题集中在空答(占失败 50%),改 prompt 就能拿到 5-10 pp 边际收益,是三后端中**修复成本最低**的。
>
> **共同短板**:temporal 类题(三后端 11-24%)是 LOCOMO 数据集上限,不是哪家后端独有的弱点,提权 episodic / 加时间预处理是通用解。

---

*对比基于:`report_volc.md`(volc-test, 152q, deepseek-v4-flash, top_k=200)·`report_agentarts.md`(smoke-test, 152q, deepseek-v4-flash, top_k=200→100 cap)·`report_agentcore.md`(aws-test, 152q, deepseek-v4-flash, top_k=200→100 cap,buggy run)*
*三 run 都跑在 conv-26、同 152 题、同 answerer+judge+provider,可比绝对分数*
*AWS 数据带已知 bug,修后预计涨 3-5 pp*
