# Memory Benchmarks

Open-source evaluation suite for memory-augmented LLM systems. Run standard benchmarks against [Mem0](https://github.com/mem0ai/mem0) to measure memory recall, extraction quality, and retrieval accuracy.

## Benchmarks

| Benchmark | Dataset | Questions | What it tests |
|-----------|---------|-----------|---------------|
| **LOCOMO** | 10 multi-session dialogues | ~300 | Factual recall, temporal reasoning, multi-hop inference |
| **LongMemEval** | 500 diverse questions, 6 types | 500 | Long-term memory across information extraction, temporal, and multi-session reasoning |
| **BEAM** | 100 conversations per size bucket (100K–10M tokens) | 2,000+ | Real-world memory retrieval across 10 memory ability types |

## Quick Start

### 1. Prerequisites

- Docker and Docker Compose
- Python 3.10+
- An OpenAI API key (or see [Custom Models](#custom-models) for alternatives)

### 2. Start Mem0

```bash
git clone https://github.com/mem0ai/memory-benchmarks.git
cd memory-benchmarks

cp .env.example .env
# Edit .env and add your OPENAI_API_KEY

docker compose up -d
# Mem0 server: http://localhost:8888
# Qdrant:      http://localhost:6333
```

This starts the full Mem0 system — semantic search, BM25 keyword search, entity extraction and linking — backed by Qdrant.

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Run a benchmark

```bash
# LOCOMO (fastest — ~300 questions, 10 conversations)
python -m benchmarks.locomo.run --project-name my-first-test

# LongMemEval (500 questions)
python -m benchmarks.longmemeval.run --project-name my-first-test --all-questions

# BEAM (configurable size)
python -m benchmarks.beam.run --project-name my-first-test --chat-sizes 100K --conversations 0-9
```

### 5. View results in the UI

```bash
npm install
npm run dev -- -p 3001
# Open http://localhost:3001
```

The web UI lets you browse results, inspect per-question evaluations with retrieval details, view logs, and compare runs.

## How It Works

Each benchmark script runs a three-stage pipeline:

```
Ingest → Search → Evaluate
```

1. **Ingest**: Conversations are chunked and added to Mem0. The system extracts facts, embeds them, and builds entity links.
2. **Search**: For each question, the system queries Mem0. Results are scored using semantic similarity + BM25 + entity boost.
3. **Evaluate**: An LLM generates an answer from retrieved memories, then a judge LLM scores correctness against ground truth.

## Configuration

### Benchmark options

All benchmarks accept these common flags:

```
--project-name NAME        Run identifier (required)
--answerer-model MODEL     LLM for answer generation (default: gpt-4o)
--judge-model MODEL        LLM for judging (default: gpt-4o)
--provider PROVIDER        LLM provider: openai, anthropic, azure (default: openai)
--top-k N                  Retrieved memories count (default: 200)
--top-k-cutoffs LIST       Evaluate at multiple cutoffs (default: 10,20,50,200)
--predict-only             Stop after search, skip answer+judge
--evaluate-only            Skip ingest+search, evaluate existing results
--resume                   Resume from checkpoint
--backend oss|cloud        Mem0 backend (default: oss)
--mem0-host URL            Mem0 server URL (default: http://localhost:8888)
```

### Custom Models

By default, the Mem0 server uses OpenAI for fact extraction (`gpt-4o-mini`) and embeddings (`text-embedding-3-small`). You can change this by mounting a custom config file.

**Step 1**: Copy an example config:

```bash
cp configs/azure-openai.yaml mem0-config.yaml
# or: cp configs/ollama.yaml mem0-config.yaml
```

**Step 2**: Edit `mem0-config.yaml` with your model details.

**Step 3**: Uncomment the volume mount in `docker-compose.yml`:

```yaml
volumes:
  - mem0_history:/app/history
  - ./mem0-config.yaml:/app/config.yaml:ro   # <-- uncomment this line
```

**Step 4**: Restart:

```bash
docker compose down && docker compose up -d
```

See `configs/` for examples:
- `configs/openai.yaml` — OpenAI (default)
- `configs/azure-openai.yaml` — Azure OpenAI
- `configs/ollama.yaml` — Fully local with Ollama (no API keys)

### Using Mem0 Cloud

To benchmark against the hosted Mem0 platform instead of self-hosted:

```bash
python -m benchmarks.locomo.run \
  --project-name cloud-test \
  --backend cloud \
  --mem0-api-key m0-your-key \
  --mem0-host https://api.mem0.ai
```

## A Note on Benchmark Scores

**Benchmark scores are not absolute numbers.** They depend heavily on:

- **Embedding model quality** — A larger, more capable embedding model will produce better retrieval, directly improving scores. The default `text-embedding-3-small` (1536 dims) is cost-efficient but not state-of-the-art.
- **LLM capability** — Both the fact extraction model (used during ingestion) and the judge model (used during evaluation) affect results. A stronger extraction model captures more nuanced facts; a stronger judge is more accurate in its verdicts.
- **Retrieval depth** — Higher `top-k` values give the system more chances to find relevant memories, but may also introduce noise.

When comparing configurations, keep all other variables constant and change only what you're testing. The default OpenAI setup provides a reproducible baseline — your scores will likely improve with stronger models.

## Project Structure

```
memory-benchmarks/
├── benchmarks/              Python evaluation scripts
│   ├── common/              Shared: Mem0 client, LLM client, metrics, utils
│   ├── locomo/              LOCOMO benchmark
│   ├── longmemeval/         LongMemEval benchmark
│   └── beam/                BEAM benchmark
├── configs/                 Example Mem0 server configs
├── docker/mem0/             Mem0 server (Dockerfile + FastAPI app)
├── docker-compose.yml       One-command setup: Mem0 + Qdrant
├── src/                     Next.js frontend
│   ├── app/                 Pages + API routes
│   ├── components/          UI components
│   └── lib/                 Database, adapters, executor
├── results/                 Benchmark output (gitignored)
└── datasets/                Auto-downloaded datasets (gitignored)
```

## License

MIT
