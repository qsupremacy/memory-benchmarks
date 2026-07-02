# memory-benchmarks · 系统图与时序

> 重点描述 **LOCOMO 评测流水线**(`python -m benchmarks.locomo.run …`)。  
> 内部模块、文件路径、端口号一律省去,把每个组件当黑盒看。

---

## 1. 组件图(谁跟谁说话)

```mermaid
flowchart LR
    U(["评测者 / CLI"]):::actor

    Driver["LOCOMO 驱动<br/>(locomo/run.py)"]:::proc
    LLM["LLM API<br/>(answerer + judge)"]:::ext
    Mem0["Mem0 服务<br/>(事实抽取 + 检索)"]:::svc
    Embed["Embedder<br/>(BGE)"]:::ext
    VecDB["向量库<br/>(qdrant)"]:::svc
    Disk[("结果文件<br/>results/locomo/")]:::store

    U --> Driver
    Driver -->|"answer / judge"| LLM
    Driver -->|"add / search"| Mem0
    Driver -->|"读 / 写 JSON"| Disk
    Mem0 -->|"内部抽取 LLM"| LLM
    Mem0 -->|"内部向量编码"| Embed
    Mem0 -->|"向量读写"| VecDB

    classDef actor fill:#fde68a,stroke:#b45309
    classDef proc  fill:#dbeafe,stroke:#1d4ed8
    classDef ext   fill:#fee2e2,stroke:#b91c1c
    classDef svc   fill:#dcfce7,stroke:#15803d
    classDef store fill:#e9d5ff,stroke:#6d28d9
```

**外部依赖只有 4 个**:`LLM API`(外部服务)、`Embedder`(HF BGE,只 mem0 内部用)、`Mem0` 自建服务(等价于"内嵌但独立部署的记忆后端")、`VecDB`(qdrant,Mem0 的存储后端)。Driver 不直接碰 Embed/VecDB,中间永远隔一层 Mem0。

---

## 2. 主时序(三阶段流水线)

> 入口:`async_main()` → 并发 `process_conversation()`(每 conv 一个协程,内含 Ingest → Predict → Judge)。

```mermaid
sequenceDiagram
    autonumber
    actor U as CLI
    participant Drv as LOCOMO 驱动
    participant LLM as LLM API
    participant M0 as Mem0
    participant FS as results/locomo/

    U->>Drv: python -m benchmarks.locomo.run --project-name X
    Drv->>Drv: 加载 dataset / 解析参数
    Drv->>FS: mkdir predicted_X/

    loop conv_idx ∈ conv_indices (并发)
        rect rgba(220,252,231,0.5)
            Note over Drv,M0: 阶段 A · Ingest
            loop 每个 chunk
                Drv->>M0: add(messages, user_id, ts)
                M0-->>Drv: memory_id
                Drv->>FS: 写 checkpoint
            end
        end

        rect rgba(219,234,254,0.5)
            Note over Drv,FS: 阶段 B · Predict
            loop 每个问题
                Drv->>M0: search(query, top_k)
                M0-->>Drv: memories[]
                Drv->>LLM: answer(question + memories)
                LLM-->>Drv: generated_answer
                Drv->>FS: 写 q*.json
            end
        end

        rect rgba(254,226,226,0.5)
            Note over Drv,FS: 阶段 C · Judge
            loop 每个问题 × cutoff
                Drv->>LLM: judge(answer vs gold)
                LLM-->>Drv: {correct, explanation}
                Drv->>FS: 写回 q*.json 的 cutoff_results
            end
        end
    end

    Drv->>FS: glob *.json → 聚合
    Drv->>Drv: compute_locomo_metrics
    Drv->>U: 打印结果 + 写 locomo_results_<ts>.json
```

**三个阶段共享磁盘**:
- Ingest 写 `_checkpoint_*.json`(粒度到 chunk)
- Predict 写 `convN_qM.json`(粒度到 question)
- Judge 写回 `convN_qM.json` 的 `cutoff_results[]` 字段

这意味着 `--resume` 能从任意阶段、任意粒度恢复(`existing_ids` + `Checkpoint` 双保险),而 `--predict-only` / `--evaluate-only` 切的是**整段跳过**而非更细粒度。

---

## 3. 变体模式(一张图说清两个开关)

```mermaid
flowchart LR
    Start([python -m ...]) --> Ingest[Ingest<br/>走 Mem0]
    Ingest --> Predict[Predict<br/>走 Mem0 + LLM]
    Predict --> Judge{Judge?<br/>非 --predict-only}
    Judge -->|是| Output[locomo_results_*.json]
    Judge -->|否 / --predict-only| Stop1([停在 predicted_*/])

    Output --> Rejudge{--evaluate-only<br/>重跑?}
    Rejudge -->|是| Output2[只重写 cutoff_results<br/>拒绝时需 predict 完整]
    Rejudge -->|否| End([结束])
    Output2 --> End
```

- **--predict-only**:跑完 Ingest + Predict 后退出,Judge 不跑。后续用 `--evaluate-only` 补判。
- **--evaluate-only**:**跳过 Mem0**,只读已有 `q*.json` 调 Judge,要求 predict 阶段已完整(否则直接 abort,见 `run.py:768`)。
- **--resume**:从已有 `q*.json` 重建 `existing_ids`,每题 `if qid in existing_ids: continue`。

---

## 4. 落盘 Schema

```mermaid
classDiagram
    class PerQuestion {
        +question_id
        +category
        +generated_answer
        +CutoffResult[] cutoff_results
    }
    class CutoffResult {
        +cutoff
        +correct
        +explanation
        +Memory[] memories
    }
    class Unified {
        +metadata
        +metrics_by_cutoff
        +PerQuestion[] evaluations
    }
    PerQuestion "1" --> "*" CutoffResult
    Unified   "1" --> "*" PerQuestion
```

---

## 5. 一句话总结

> **Driver** 把每段对话拆 chunk 喂给 **Mem0**(顺带让 Mem0 调 **LLM** 抽事实、存到 **qdrant**),检索时从 Mem0 取回 memories 交给 **LLM** 回答,最后再用同一个 LLM 当裁判打分——**全部 LLM 调用都在离线评测阶段**,产物按 `predicted_*/q*.json` 落盘,可被 `--resume` / `--evaluate-only` 任意续跑。
