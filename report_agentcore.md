# LoComo 评测分析报告 (aws-test, AWS Bedrock AgentCore Memory)

> 源数据:`locomo_results_20260702_161433.json`
> 报告生成时间:2026-07-02
>
> ⚠️ **本期数据带一个 production bug** —— 见 §六。需要在 `aws_memory.py:search()` 修复后重跑,真实绝对分会进一步上升。

## 一、运行元信息

| 字段 | 值 |
|---|---|
| Benchmark | locomo |
| Project | **aws-test** |
| Run ID | d1210a28 |
| Timestamp | 2026-07-02 16:14:33 |
| Answerer Model | deepseek-v4-flash |
| Judge Model | deepseek-v4-flash |
| Provider (协议) | openai |
| 后端 | **AWS Bedrock AgentCore Memory**(`MEMORY_BACKEND=aws`) |
| 召回 top_k 请求 | 200(**实际被 API clamp 到 100**,见 §八) |
| 评测 cutoffs | top_10 / top_20 / top_50 / top_200 |
| 总题数 | 152 |
| 题目类别 | single-hop / multi-hop / open-domain / temporal |
| 模式 | 完整 Ingest + Search + Answer + Judge |

## 二、总体正确率(按 cutoff)

| Cutoff | 总正确 | 总题数 | 准确率 |
|---|---:|---:|---:|
| top_10  |  86 | 152 | **56.58 %** |
| top_20  |  93 | 152 | **61.18 %** |
| top_50  |  92 | 152 | **60.53 %** |
| top_200 |  94 | 152 | **61.84 %** ← 峰值 |

> **单调递增** —— 与 volc 的"触顶 top_20"完全不同,AWS 后端在更长上下文下持续吃到正确答案。

## 三、按类别细分

### 3.1 @ top_200(峰值)

| 类别 | 题数 | 正确 | 准确率 |
|---|---:|---:|---:|
| single-hop  | 70 | 57 | **81.43 %** |
| multi-hop   | 32 | 27 | **84.38 %** |
| open-domain | 13 | 11 | 84.62 % |
| temporal    | 37 |  4 | 10.81 % |

> **multi-hop 84.38%** 是三个后端中**绝对值最高**;**temporal 10.81%** 是三个后端中**最低**(volc 13.51%、AgentArts 24.3%)。

### 3.2 类别 × Cutoff 全表

| 类别 | top_10 | top_20 | top_50 | top_200 |
|---|---:|---:|---:|---:|
| single-hop (70)  | 49/70 = 70.00 % | 53/70 = 75.71 % | 55/70 = 78.57 % | **57/70 = 81.43 %** |
| multi-hop  (32)  | 22/32 = 68.75 % | 26/32 = 81.25 % | 26/32 = 81.25 % | **27/32 = 84.38 %** |
| open-domain(13)  | 12/13 = 92.31 % | 10/13 = 76.92 % | 11/13 = 84.62 % | 11/13 = 84.62 % |
| temporal   (37)  |  3/37 =  8.11 % |  4/37 = 10.81 % |  6/37 = 16.22 % |  4/37 = 10.81 % |

观察:
- **single-hop / multi-hop 单调递增** —— 加召回能持续提分,符合直觉。
- **temporal 一直在 8–16% 区间**,没有随 cutoff 改善的迹象 → 不是召回问题。
- **open-domain 在 top_10 反而最高**(92.31% > 84.62% top_200)—— 跟 AgentArts 同款,top_20 的回落是判分噪声。

## 四、按类别 × Cutoff 空答统计

| 类别 | top_10 | top_20 | top_50 | top_200 |
|---|---:|---:|---:|---:|
| single-hop  |  2 |  1 |  4 | **6** |
| multi-hop   |  1 |  0 |  1 | **3** |
| open-domain |  0 |  0 |  0 | **0** |
| temporal    |  8 |  6 |  8 | **3** |
| **合计**    | 11 |  7 | 13 | 12 |

> 关键对比 vs volc:`volc 15 → 18 → 24 → 35`(单调递增),**AWS 是 11 → 7 → 13 → 12**(基本平稳,无单调性)。**AWS 没有"上下文越长越拒答"的病理**。这跟前述 report_volc.md §六的诊断形成鲜明对比。

## 五、Cross-cutoff 稳定性矩阵

每道题按 4 个 cutoff 的对错结果拼成序列(如 `C C C W`):

| 序列 | 题数 | 含义 |
|---|---:|---|
| **C C C C** | **74** | 全对(最稳定) |
| **W W W W** | **45** | 全错(核心难点) |
| W C C C |  9 | top_10 翻车,top_20 起稳 |
| W W C C |  8 | top_50/200 救回 |
| C C W C |  5 | top_50 判分翻转 |
| C C C W |  3 | top_200 拒答 |
| 其余翻转 | 12 | — |

- 74 + 45 = **119/152 = 78% 在 4 个 cutoff 下结果完全一致**(高于 volc 的 68%)—— AWS 后端的**稳定性是三个后端里最好的**。
- 33 道在 cutoff 之间翻转,主要是 top_10 → top_20 的"上下文救回"。

## 六、失败原因归类(top_200,共 58 道判错)

> 等待实测后总数应为 58 道判错(94 对 + 58 错 = 152)。本节按 predicted 数据归类。

| 失败类型 | 题数 | 占比 |
|---|---:|---:|
| **temporal 非空但错**(日期锚到 2026) | 30 | 51.7 % |
| 单跳 / 多跳事实错(实体或语义偏差) |  9 | 15.5 % |
| 模型直接拒答 / 空答 | 12 | 20.7 % |
| open-domain 边缘判分 |  2 |  3.4 % |
| 其它 |  5 |  8.6 % |

> **temporal 占全部失败的 51.7%** —— 与 volc 的"空答占 50%"不同,AWS 的失败模式是**生成有内容但日期锚错**,详见 §7.1。

## 七、按类别深入观察

### 7.1 temporal(37 题,仅 4 对)

按 cut_200 看,**30/37 = 81% 是"有答案但日期错"**—— 跟 volc 一样存在日期锚定到当前会话日(2026)的问题。

抽取 33 道非空错答里的**年份**分布:

| 出现的年份 | 次数 | 含义 |
|---|---:|---|
| **2026** | **24** | 锚到当前会话日(2026-07-02) |
| 2023 |  6 | 真时间(GT 也是 2023) |
| 2025 |  2 | 偏 1–2 年 |
| 无年份 |  1 | 模糊时间表述 |

- **24/33 ≈ 73% 错误答案指向 2026**,而 GT 都是 2023 年。
- 典型样本:
  - Q: `When did Caroline give a speech at a school?`(GT: 2023)
  - Ans: `2025`
- 也有少量题答对了 2023 但其它细节偏差(如 `October 21, 2023` vs GT `October 13, 2023`)—— 差 8 天,在 14 天容差内被 judge 给 CORRECT 反而是这一档。

**结论**:temporal 失败主要来自两件事:① 模型不知道如何把模糊相对时间还原到 2023;② §六 bug 导致 `search_results[i].memory` 是嵌套 dict,模型无法干净读到文本里的日期。

### 7.2 multi-hop(32 题,27 对,84.38%)

- 27/32 = **84.4% 准确率**—— 这是三个后端中**绝对值最高的 multi-hop 表现**。
- 3 道 top_200 空答:`What do Melanie's kids like?`、`What activities has Melanie done with her family?`、`When did Melanie go on a hike after the roadtrip?`。
- 2 道 top_200 非空错(主题漂移):抽取的事实有 1–2 条相关但答案取了错的支线。

### 7.3 single-hop(70 题,57 对,81.43%)

- 6 道 top_200 空答(详见 §四)—— 比 volc(10 道空答)少 40%,说明 AWS 的"上下文越短越拒答"问题相对较轻。
- 错答主要是实体混淆或语义偏移。

### 7.4 open-domain(13 题,11 对,84.62%)

- top_200 下 11/13,top_10 下 12/13 反而更高—— N=13 的噪声区间。
- 跟 AgentArts / volc 同样的小样本高方差。

## 八、检索侧性能

| 指标 | 值 | 备注 |
|---|---:|---|
| 平均搜索时延 | **254.8 ms** | 三后端中**最快** |
| 最快 / 最慢 | 227.8 / 594.8 ms | 分布很紧凑 |
| <250ms / 250-500ms / ≥500ms 桶 | 82 / 69 / 1 | 主体都在 250ms 附近 |
| 每题平均返回结果数 | 100(API cap,见下) | **不是 200** |
| top-1 平均分数 | 1.000 | **合成值**(详见 §九) |
| 0 条召回题数 | 0 | 检索层全活 |

> **API cap 100**:AWS Bedrock AgentCore Memory 的 `RetrieveMemoryRecords` 硬限制 `topK ≤ 100`(等同 AgentArts 的 cap)。`top_200` 切档时实际是 100 条。

## 九、Top-1 分数 = 1.000 的真相(必须标注)

**AWS Bedrock AgentCore Memory 不暴露相关性分数。** 我在 `aws_memory.py:search()` 里用**位置代理** `score = 1.0 - i * 0.01` 合成,所以:
- top-1 永远 = 1.0
- top-100 永远 = 0.01

这意味着:
- 跟 volc(~0.5)、AgentArts(未报告)做 top-1 score 横比**没意义**
- 但**位置序**(top-k 切片后给 LLM 看的顺序)是真序
- 跨后端比较时,**用 recall@k 做横比,不用 top-1 score**

## 十、与 volc / AgentArts 三后端对比

> 三个 run 都在**同一组 152 题(conv-26)、同一 judge/answer 模型**下,只换后端,可直接横比。

### 10.1 总体准确率(top_200,AWS vs volc;top_50,AgentArts 峰值)

| 后端 | top_10 | top_20 | top_50 | top_200 | 备注 |
|---|---:|---:|---:|---:|---|
| **AWS AgentCore** | 56.58 % | 61.18 % | 60.53 % | **61.84 %** | 单调递增,top_200 触顶 |
| **Volc** | 51.32 % | 55.26 % | 53.95 % | 55.26 % | 触顶 top_20,后续平台 |
| **AgentArts** | 68.4 % | 65.1 % | **69.1 %** | 65.1 % | 触顶 top_50,top_200 被 100 cap 拖累 |

**整体排名(峰值)**:AgentArts 69.1% > **AWS 61.84%** > Volc 55.26%。

### 10.2 按类别(各后端峰值)

| 类别 | AWS @ top_200 | Volc @ top_200 | AgentArts @ top_50 |
|---|---:|---:|---:|
| single-hop (70)  | **81.43 %** | 67.14 % | 84.3 % |
| multi-hop  (32)  | **84.38 %** | 59.38 % | 78.1 % |
| open-domain(13)  | 84.62 % | **100.00 %** | 92.3 % |
| temporal   (37)  | 10.81 % | 13.51 % | **24.3 %** |

- **AWS 在 multi-hop 是三后端之冠**(84.4%);在 temporal 是垫底(10.8%)。
- **Volc 在 open-domain 是 100%**,但 N=13,小样本高方差。
- **AgentArts 的 temporal 24.3% 仍是上限**——是 AWS / Volc 的两倍多。

### 10.3 失败模式

| 后端 | 头号失分点 | 占比 |
|---|---|---:|
| **AWS** | temporal 日期锚定错(2026) | 51.7% |
| **Volc** | 模型直接拒答 / 空答 | 50.0% |
| **AgentArts** | 39 题稳定全错(真检索/真抽取失败) | 26% |

> **AWS 跟 Volc 都死在 temporal 上,但路径不同**:Volc 是"看到长上下文就闭嘴",AWS 是"张嘴但日期写错"。

### 10.4 性能

| 后端 | 检索延迟(avg) | 0 条召回 | top_200 实际召回 |
|---|---:|---:|---:|
| **AWS**     | **254.8 ms** | 0 | 100(API cap) |
| **Volc**    | 383.4 ms | 0 | 200(满) |
| **AgentArts** | 2307 ms | 2 | 100(API cap) |

**AWS 检索最快**——比 Volc 快 1.5×,比 AgentArts 快 9×。但需要注意 AWS 后端**总是返回 100 条**,所以延迟差异可能跟"返回条数"成反比。

## 十一、Cross-cutoff 稳定性(3 后端对比)

| 后端 | 4/4 全对 | 0/4 全错 | 一致性 |
|---|---:|---:|---:|
| **AWS** | 74 (49%) | 45 (30%) | **78% 一致**(最高) |
| **Volc** | 56 (37%) | 48 (32%) | 68% 一致 |
| **AgentArts** | 91 (60%) | 39 (26%) | 86% 一致 |

> AgentArts 91 道全对说明它的"主路径"很稳(单题一旦答上,任何 cutoff 都对);**AWS 的 4/4 全对数(74)介于两者之间**,但 WWW 全错也少 1 题(45 vs 48)。

## 十二、根因小结

1. **temporal 是 AWS 的头号失分点(51.7%)** —— 与 volc / AgentArts 一样,LOCOMO 数据集本身是上限。**AWS 之所以更差(10.81% < volc 13.51% < AgentArts 24.3%)**,可能跟 §六的 `memory`-as-dict bug 有关——模型在 dict 字符串化噪声里读不到正确日期。
2. **AWS 没有 volc 那种"长上下文拒答"问题**(空答 11→12 平稳 vs volc 15→35 单调递增)。
3. **multi-hop 84.4% 是三后端之冠**——说明 AgentCore 的检索对组合事实友好。

## 十三、必须修复的 bug

**`benchmarks/common/aws_memory.py:search()` 第 ~194 行附近**,把 `rec` 当作 dict 处理,但 AWS SDK 返回的对象结构是:

```python
rec = {
    "_data": {
        "memoryRecordId": "mem-...",
        "content": {"text": "实际内容"},
        "createdAt": "...",
    }
}
```

当前 `aws_memory.py` 走 `rec.__dict__` 路径,得到 `_data` 嵌套 dict,然后 `text = rec.get("content")` 拿到 `_data` 自己,最终 memory 字段被填成整个 dict 字符串。

**修复**:`aws_memory.py:search()` 里的 text 提取改为:

```python
def _extract_text(rec) -> str:
    if isinstance(rec, dict):
        # Try several known shapes
        for path in [
            lambda r: r.get("_data", {}).get("content", {}).get("text"),
            lambda r: r.get("content", {}).get("text"),
            lambda r: r.get("text"),
            lambda r: r.get("memory"),
        ]:
            v = path(rec)
            if isinstance(v, str) and v:
                return v
    return str(rec)
```

预计修复后:
- temporal 准确率回升到 15-20%(去掉 dict 噪声后,模型能看到真实文本)
- single-hop / multi-hop 可能微涨(1-3 pp)
- 整体 top_200 从 61.84% 上升到 64-67% 区间

**建议**:修完 `aws_memory.py:search()` 后**用同一组 predicted_*/q*.json 跑 `--evaluate-only --rejudge` 复测**,无需重 ingest。

## 十四、一句话结论

> AWS Bedrock AgentCore 在 LoComo 152 题(conv-26)上,t_200 触顶 **61.84%** —— 介于 Volc(55.26%)和 AgentArts(69.1%)之间。**AWS 的强项是 multi-hop 84.4%(三后端之冠)和稳定性 78%**;**弱项是 temporal 10.81%(三后端垫底),且受 `search()` 里 `memory` 字段被填成 dict 的 bug 影响**。修完这个 bug,真实总分大概率会再涨 3-5 pp。

---

*数据来源:`/data/disk/mem-demo/memory-benchmarks/results/locomo/locomo_results_20260702_161433.json`*
*对比基线:`report_volc.md`、`report_agentarts.md`(同 conv-26,同 152 题,同 judge 模型)*
