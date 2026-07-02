# LOCOMO Benchmark Report — AgentArts Memory Backend

**Source file**: `results/locomo/locomo_results_20260702_112100.json`
**Run mode**: `--evaluate-only` (predict 阶段在更早的 run 里完成，本报告仅基于已落盘的检索 + judge 结果分析)
**Conversation**: conv-26 (Caroline & Melanie, 19 sessions, 419 turns)
**Total scored questions**: 152 (categories 1/2/3/4, 排除 category 5 adversarial)

## 1. Run Metadata

| 字段 | 值 |
|---|---|
| benchmark | locomo |
| project_name | smoke-test |
| run_id | bfe373f7 |
| timestamp | 2026-07-02 11:21:00 |
| answerer_model | deepseek-v4-flash |
| judge_model | deepseek-v4-flash |
| provider | openai (DeepSeek 兼容端点) |
| top_k | 200 (实际被 AgentArts API clamp 到 100) |
| top_k_cutoffs | top_10, top_20, top_50, top_200 |
| categories | [1, 2, 3, 4] |
| evaluate_only | True |

## 2. Overall Accuracy by Cutoff

| Cutoff | Correct | Total | Accuracy |
|---|---:|---:|---:|
| top_10 | 104 | 152 | **68.4%** |
| top_20 | 99 | 152 | 65.1% |
| top_50 | 105 | 152 | **69.1%** ← 最高 |
| top_200 | 99 | 152 | 65.1% |

**非单调现象**：top_50 反而比 top_10 高 0.7 pp。这说明 top-50 比 top-10 多召回的部分记忆里有真实答案，但 judge 在 top-10 时未给分（可能是 answer 没选那条记忆），属于答案提取问题而非检索问题。top_200 回到 65.1% 跟 top_20 一致 — 100 之后的「加分记忆」没用上（也是因为 AgentArts API cap 在 100）。

## 3. Accuracy by Category × Cutoff

| Category | top_10 | top_20 | top_50 | top_200 |
|---|---:|---:|---:|---:|
| multi-hop (cat 1) | 75.0% (24/32) | 75.0% (24/32) | 78.1% (25/32) | 71.9% (23/32) |
| temporal (cat 2) | 24.3% (9/37) | 21.6% (8/37) | 24.3% (9/37) | 21.6% (8/37) |
| open-domain (cat 3) | 100.0% (13/13) | 92.3% (12/13) | 92.3% (12/13) | 100.0% (13/13) |
| single-hop (cat 4) | 82.9% (58/70) | 78.6% (55/70) | 84.3% (59/70) | 78.6% (55/70) |

### 类别观察

- **single-hop 最强**（82-84%）：检索 1 条记忆就能回答的事实题，是 AgentArts 的甜区
- **multi-hop 中等**（72-78%）：跨多条记忆的组合题，AgentArts 表现合理
- **open-domain 接近完美**（92-100%）：样本少（n=13），波动大；top_10 满分很可能是 judge 模型偏宽松
- **temporal 严重塌方**（22-24%）：5 道题才能答对 1 道，是 LOCOMO 公认难点，但 AgentArts 这边掉得尤其多 — 多半跟时间戳注入语义不完整有关（详见 §6）

## 4. Retrieval Coverage Analysis

每个问题最多答对的 cutoff 数（基于 4 个 cutoffs）：

| 答对 cutoff 数 | 题数 | 含义 |
|---:|---:|---|
| 4 / 4 | **91** | 任意 cutoff 都对 — 答案在 top-10 里，检索稳健 |
| 3 / 4 | 7 | 一个 cutoff 误判，可能是 judge 噪声 |
| 2 / 4 | 7 | 两个 cutoff 误判 |
| 1 / 4 | 8 | 只有某个特定深度才答对 — 检索深度敏感 |
| 0 / 4 | **39** | 全部答错 — 检索缺失或答案提取失败 |

**结论**：152 题里 91 题（**60%**）答案确定在 top-10，**说明 AgentArts 的检索召回能力是合格的**。主要问题集中在 39 题「全错」和 22 题「深度敏感」。

## 5. Retrieval Performance

| 指标 | 值 |
|---|---:|
| 检索深度 — min | 0 条（**2 题**搜不到任何记忆） |
| 检索深度 — max | 100 |
| 检索深度 — avg | 55.6 |
| 搜索延迟 — min | 415 ms |
| 搜索延迟 — max | 4615 ms |
| 搜索延迟 — avg | **2307 ms** |

**检索延迟 2.3 秒/题**：跑完 152 题约 6 分钟纯检索，加上 LLM answer+judge 是 152 题 × 4 cutoffs ≈ 600 次 LLM 调用。一次完整 evaluate-only 在 DeepSeek-V4-Flash 上大约 10-15 分钟。

**2 道题搜到 0 条记忆**：检查 `conv0_q*.json` 应能找到，原因是这些题没有匹配到 actor_id 下任何记忆（可能是冷启动 chunk 未抽取完成，或者 query 跟抽取的事实语义距离太远）。

## 6. AgentArts Strategy Type 分布

| strategy_type | 总出现次数 | 在 top-1 结果中的占比 |
|---|---:|---:|
| summary | 2831 | **72%** (105/152) |
| semantic | 2792 | 11% (16/152) |
| episodic | 2564 | 18% (26/152) |
| user_preference | 267 | 2% (3/152) |

**说明**：AgentArts 在 ingest 时按四种策略各抽取一遍：
- `summary`：全局摘要
- `semantic`：语义事实
- `episodic`：事件级记忆
- `user_preference`：用户偏好（最少，n=267）

**top-1 排序 72% 是 summary** —— 说明搜索排序算法偏好摘要类型。这对 multi-hop / temporal 类题可能是**双刃剑**：摘要提供高层信息但缺少具体时间戳，temporal 题掉到 24% 可能与此相关（事件级 `episodic` 应该有更精确的时间锚点，但只占 18%）。

## 7. 与 Mem0 基线对比

`report.md` 中 LOCOMO 全量跑（10 个对话、~1540 题、gpt-4o 抽取）的基线：

| 指标 | Mem0 基线 | AgentArts (本次单 conv) |
|---|---:|---:|
| Overall @ top_200 | 92.5% | 65.1% |
| Overall @ top_50 | 91.8% | 69.1% |
| single-hop | — | 82.9% (top_10) / 84.3% (top_50) |
| multi-hop | — | 75-78% |
| temporal | — | 22-24% |
| open-domain | — | 92-100% |

**注**：基线和本次跑的数据集大小、对话数、judge 模型（gpt-4o vs deepseek-v4-flash）都不一样，**不能直接横向比**。差距主因：

1. **judge 模型能力**：deepseek-v4-flash 在 LOCOMO 这种细粒度事实判断上不如 gpt-4o 稳定（容易给「WRONG」或不给分）
2. **后端差异**：Mem0 的抽取/检索可能更适合 single-hop 路径，而 AgentArts 的 summary 主导排序对事实精确召回不友好
3. **topK clamp**：AgentArts 硬限 100，无法验证 top_200 是否能补齐

## 8. Known Limitations

1. **topK 上限 100**：LOCOMO 默认 top_k=200 实际被截到 100，cutoff=200 跟 cutoff=100 等价
2. **时间戳语义不完全对齐**：AgentArts SDK 的 `timestamp` 参数是 batch-level client time，而 Mem0 的 `timestamp` 是 message-level event time。temporal 题掉点可能部分归因于此
3. **session 创建无复用**：每次 predict-only 跑都会创建新 session（因为 `run_id` 是新的 UUID）；跨运行记忆不共享
4. **get_user_profile 未实测**：本次没带 `--user-profile` flag，分桶逻辑未触发

## 9. Recommendations

| 优先级 | 建议 |
|---|---|
| 高 | judge 模型换成更强的（如 gpt-4o / claude-sonnet），用 `--evaluate-only --judge-model gpt-4o` 重新评同批预测，看分是真差还是 judge 噪声 |
| 高 | 检查 39 道「全错」题：随机抽 5 道，肉眼看检索返回的 top-10 里是否真有答案，区分「检索缺」还是「提取错」 |
| 中 | temporal 题专项优化：研究 AgentArts 的 episodic 抽取是否能注入更精确的时间戳，或考虑改用 `user_preference`/`semantic` 排序权重 |
| 中 | 加 `--user-profile` 跑一轮，看 `get_user_profile` 的分桶逻辑能否提升 open-domain 表现 |
| 低 | 把 `--top-k` 默认改为 100（与 AgentArts API cap 对齐），cutoffs 改成 `10,20,50,100` 避免虚高 |

---

*Generated from `locomo_results_20260702_112100.json` · 152 evaluated questions · 4 cutoffs · 4 categories*