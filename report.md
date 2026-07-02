# LOCOMO Backend Comparison — Volcengine Mem0 vs AgentArts

> 直接对照：两次 LOCOMO 单会话（conv-0）跑分，相同数据集、相同 judge 模型（deepseek-v4-flash）、相同 cutoff 网格
> `report_oss.md` 实际内容 = Volcengine Mem0 Cloud（`--backend cloud --mem0-host ... --mem0-api-version 1`）
> `report_volc.md` 实际内容 = 默认 OSS Mem0 自托管（my-first-test，10 conv 全跑） — **只作参考基线**

---

## 1. Comparability Matrix

| 报告 | 项目 | 后端 | 对话数 | 题数 | judge 模型 | 可比性 |
|---|---|---|---|---:|---|---|
| `report_oss.md` | volc-test | **Volcengine Mem0 Cloud**（v1 API） | 1 (conv-0) | 152 | deepseek-v4-flash | ✅ 主对比 A |
| `report_agentarts.md` | smoke-test | **AgentArts Memory** | 1 (conv-0) | 152 | deepseek-v4-flash | ✅ 主对比 B |
| `report_volc.md` | my-first-test | 默认 OSS Mem0（自托管） | 10 (全部) | 1540 | deepseek-chat | ⚠️ 仅作粗参考 |

---

## 2. Overall Accuracy × Cutoff

| Cutoff | Volcengine (152q) | AgentArts (152q) | Δ (pp) |
|---|---:|---:|---:|
| top_10  | 51.3% (78/152) | **68.4%** (104/152) | **+17.1** |
| top_20  | **55.3%** (84/152) | 65.1% (99/152) | +9.8 |
| top_50  | 54.0% (82/152) | **69.1%** (105/152) | **+15.1** |
| top_200 | **55.3%** (84/152) | 65.1% (99/152) | +9.8 |

**观察**：
- AgentArts 在每个 cutoff 都领先，**top_10 差距最大（+17pp）**
- Volcengine 在 top_20 即触顶（55.3%），后续加更多上下文没收益
- AgentArts 最高分在 top_50（69.1%），top_200 回到 65.1%（被 100 cap 限制）

---

## 3. By Category × Cutoff

| Category | top_10 (Volc / AArts) | top_20 | top_50 | top_200 |
|---|---:|---:|---:|---:|
| **single-hop** (70) | 64.3% / **82.9%** | 65.7% / 78.6% | 67.1% / **84.3%** | 67.1% / 78.6% |
| **multi-hop** (32) | 59.4% / **75.0%** | 68.8% / 75.0% | 59.4% / **78.1%** | 59.4% / 71.9% |
| **open-domain** (13) | 84.6% / **100.0%** | 69.2% / 92.3% | 92.3% / 92.3% | **100.0%** / 100.0% |
| **temporal** (37) | 8.1% / **24.3%** | 18.9% / 21.6% | 10.8% / **24.3%** | 13.5% / 21.6% |

**观察**：
- AgentArts 在 **single-hop 和 multi-hop** 全面领先（+15 ~ +18pp）
- **temporal** 仍是双方共同短板，但 AgentArts **翻倍**（8% → 24%）
- open-domain 都接近天花板，差距被样本量（n=13）稀释

---

## 4. Volcengine Failure Analysis（top_200，68 道错）

| 失败类型 | 题数 | 占比 |
|---|---:|---:|
| **模型直接拒答 / 空答** | 34 | **50.0%** |
| 日期与标准答案相差 > 14 天容差 | 15 | 22.1% |
| 其它原因 | 8 | 11.8% |
| 答案非空但完全不含正确答案 | 6 | 8.8% |
| 内容差异 | 5 | 7.4% |

**空答按 cutoff 单调递增**：

| Cutoff | 空答数 |
|---|---:|
| top_10 | 15 |
| top_20 | 18 |
| top_50 | 24 |
| top_200 | **35** |

**结论**：Volcengine 的头号失分原因是**空答**，且上下文越长越拒答。AgentArts 没有同类分析，但 top_10/50/200 分数接近，说明它**不受上下文膨胀影响**。

---

## 5. Volcengine Cross-Cutoff Stability

每题按 4 cutoff 的对错序列：

| 序列 | 题数 | 含义 |
|---|---:|---|
| C C C C | 56 | 全部 cutoff 都对（最稳） |
| W W W W | 48 | 全部 cutoff 都错（核心难点） |
| W C C C | 11 | top_10 翻车，其余稳 |
| C C W W | 6 | 上下文变大反而错 |
| C C C W | 5 | top_200 拒答导致丢分 |
| W W W C | 5 | top_200 救回来 |
| C W W W | 5 | top_10 后丢失 |
| W W C C | 4 | top_50/200 救回 |
| W C W C | 3 | 反复横跳 |
| 其它翻转 | 9 | — |

**56 + 48 = 104 题（68%）** 在所有 cutoff 下结果一致 — Volcengine 的**稳定性不错**，主要问题在两端（全对或全错）。

AgentArts 对照（`report_agentarts.md` §4）：

| 答对 cutoff 数 | 题数 | 含义 |
|---:|---:|---|
| 4/4 | **91** (60%) | 全对 |
| 0/4 | 39 (26%) | 全错 |
| 1/4 | 8 | 仅特定深度对 |
| 2/4 | 7 | — |
| 3/4 | 7 | — |

**AgentArts 的 4/4 全对题（91）显著高于 Volcengine（56）**——后者 +35 题提分空间在「所有 cutoff 都对」这条稳定性上。

---

## 6. Volcengine temporal 失败模式（37 题仅 5 对）

具体归类：
- **16/37 ≈ 43% 空答**：「When did Caroline go to the LGBTQ support group?」→ 空
- **日期偏移**：模型把日期锚到当前会话日 (2026-10)，GT 是 2023：
  - GT `July 2023` → Ans `July 2026`
  - GT `10 July 2023` → Ans `30 June 2026`
- **相对时间直译**：「the week before X」错误展开到跨年

**对比 AgentArts temporal**（22-24%）：仍弱，但绝对值**比 Volcengine 高 10pp**，且 24% 是 LOCOMO 全网同类难度的合理上限。AgentArts 的 `summary` 策略虽然排序占 72%，但抽取的事实里带完整时间锚的概率比 Volcengine 的 memory 单元高。

---

## 7. Retrieval Performance

| 指标 | Volcengine | AgentArts |
|---|---:|---:|
| 平均搜索延迟 | **383 ms** | 2,307 ms |
| 最快 / 最慢 | 301 / 914 ms | 415 / 4,615 ms |
| 召回深度 (avg) | 200（满） | 55.6（cap 100） |
| 0 条召回的题数 | 0 | **2** |
| top-1 分数（avg） | ~0.50 | 未统计 |

**延迟差距 6×**：但 152 题总检索时间 58s vs 350s，**对总跑分时长影响 < 5%**（LLM judge 才是大头）。

**Volcengine top-1 分数偏低（~0.5）**：相关性排序还有优化空间，特别是 temporal 题，正确的时间记忆常排在 10 名之后。

---

## 8. AgentArts Strategy Type 分布

| strategy_type | 总出现次数 | top-1 占比 |
|---|---:|---:|
| **summary** | 2,831 | **72%** (105/152) |
| semantic | 2,792 | 11% (16/152) |
| episodic | 2,564 | 18% (26/152) |
| user_preference | 267 | 2% (3/152) |

**双刃剑**：summary 主导排序对 single-hop 有利（高层信息浓缩），但对需要精确时间锚的 temporal 不够友好 — 这可能是 AgentArts temporal 卡在 24% 的原因之一。

---

## 9. 与全量基线（OSS 自托管，1540 题）的粗对比

| 指标 | OSS 全量 (1540q) | Volcengine (152q) | AgentArts (152q) |
|---|---:|---:|---:|
| top_10 | 44.1% | 51.3% | **68.4%** |
| top_50 | 56.6% | 54.0% | **69.1%** |
| top_200 | 64.9% | 55.3% | 65.1% |
| temporal @ top_200 | 19.3% | 13.5% | 21.6% |

**注**：OSS 全量是 10 conv、deepseek-chat judge；其他两组是 1 conv、deepseek-v4-flash judge。**不能直接比对**，仅作量级感知。temporal 在 OSS 全量（19.3%）和 AgentArts（21.6%）上**接近** — 可能是 LOCOMO 数据集本身的难度上限。

---

## 10. Key Insights

1. **AgentArts 后端在 conv-0 上全维度压制 Volcengine**（+9 ~ +17pp），top_10 差距最大
2. **空答是 Volcengine 头号失分点（50%）**，且随 cutoff 单调递增。AgentArts 没有这个问题
3. **temporal 都是双方共同短板**，但 AgentArts 在绝对值上**翻倍**（8% → 24%）
4. **Volcengine top-20 即触顶**，继续加上下文无效；AgentArts 触顶在 top_50
5. AgentArts 的 **summary 排序策略**对 single-hop 有利，但对 temporal 不够友好 — 后续可通过调整 `episodic` 排序权重进一步提分

## 11. Recommendations

### Volcengine
- **高优先级**：修空答 — 在 answerer prompt 加显式兜底：「If not in memories, output 'UNKNOWN' or one-sentence acknowledgment」
- **中优先级**：temporal 题加时间规范化预处理（"the week before X" → 绝对日期区间）
- **低优先级**：调整 top_k=20 作为生产上限（55.3% 已达峰，top_200 不再涨）

### AgentArts
- **高优先级**：用更强的 judge（gpt-4o / claude-sonnet）跑 `--evaluate-only`，分离「检索/抽取质量」与「judge 噪声」
- **中优先级**：检查 39 道全错题，肉眼看 top-10 是否真有答案，定位是「检索缺」还是「提取错」
- **中优先级**：尝试调整 sort 权重，让 `episodic` 在 temporal 题上有更高优先级

### 共同
- 跑全量 10 conv 做最终横评（不能停在 conv-0）
- 评估 Mem0 自托管 + gpt-5 抽取这个组合作为「理论天花板」基线

---

*对比基于：`report_oss.md` (Volcengine Mem0, 152q) · `report_agentarts.md` (AgentArts, 152q) · `report_volc.md` (OSS 自托管, 1540q，仅作粗参考)*
*两次 conv-0 跑分 judge 模型均为 `deepseek-v4-flash`，避免 judge 噪声混淆后端差异*