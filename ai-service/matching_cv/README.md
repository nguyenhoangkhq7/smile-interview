# AI Inference Service

FastAPI service for analyzing a candidate CV against a job description. The supported product endpoint is `POST /api/v1/pipeline/analyze`.

## Request flow

The analyze pipeline parses both documents, extracts explicit and implicit skills, encodes skills with the configured Sentence Transformer, reasons over candidate skill pairs, builds a paper-aligned graph, and runs GNN inference when a verified checkpoint is available. The response follows the `standardized-output-v1` contract.

Known documents may reuse extraction records from `data/cache`. On a cache miss, skill extraction and reasoning require an OpenRouter API key. The embedding model is downloaded from Hugging Face when it is not cached locally.

## Project layout

```text
app/
├── api/v1/endpoints/pipeline.py   # Analyze and health endpoints
├── core/                          # Settings and model loading
├── schemas/                       # API and pipeline data contracts
└── services/                      # Parsing, extraction, embeddings, reasoning, graph, and inference
research/
├── data/canonical_skill_normalizer.py
├── paper_aligned_gnn/             # Graph builder and inference architecture used by analyze
└── skill_importance/              # JD skill importance used by analyze
data/
├── cache/                         # Reusable CV/JD extraction records
└── checkpoints/paper_aligned_gnn/ # Active PaperAligned GNN checkpoint
tests/                             # Analyze pipeline and direct component tests
docs/unified_pipeline_api.md       # Request and response contract
```

## Run locally

Use Python 3.10 or newer. In PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

To install the test tools as well, use `pip install -r requirements-dev.txt`.

Set `OPENROUTER_API_KEY` in `ai-service/.env` if requests may need live LLM extraction or reasoning. `DEVICE` accepts `auto`, `cpu`, or `cuda`. The pinned embedding model and revision are configured by `STAGE3_MODEL_NAME` and `STAGE3_MODEL_REVISION`.

From the parent `ai-service` directory, start the standalone research API:

```powershell
python -m uvicorn matching_cv.app.main:app --reload --host 127.0.0.1 --port 8000
```

OpenAPI docs are at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs); liveness is available at `GET /health`.

The Smile Interview app calls `matching_cv.app.container.match_documents(cv_text, jd_text)` in process. That entry point builds the shared `Module1Output` for skill gap analysis. The standalone research API continues to expose `standardized-output-v1`.

## Analyze a CV and job description

Upload one PDF or TXT file for each side:

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/pipeline/analyze" \
  -F "cv_file=@candidate.pdf" \
  -F "jd_file=@job-description.pdf" \
  -F "graph_mode=similarity_enriched" \
  -F "top_k=5"
```

`graph_mode` accepts `verified_equivalence`, `similarity_enriched`, `llm_enriched`, `evidence_only`, `paper_cosine_08`, or `canonical_only`. The API returns cleaned document text, skill-gap input, proficiency input, status, and `match_score`. The score is `null` when a verified trained GNN checkpoint cannot produce it; the service does not substitute a heuristic score.

See [the analyze API contract](docs/unified_pipeline_api.md) for the response fields and supported parameters.
