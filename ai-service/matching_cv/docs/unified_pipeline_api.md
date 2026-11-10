# Analyze API

## Endpoint

`POST /api/v1/pipeline/analyze` accepts `multipart/form-data` with a CV and a job description. Each file must be PDF or TXT and stay within the configured upload limit (15 MB by default).

| Field | Type | Default | Purpose |
|---|---|---:|---|
| `cv_file` | file | required | Candidate CV |
| `jd_file` | file | required | Job description |
| `graph_mode` | string | `similarity_enriched` | Graph policy: `verified_equivalence`, `similarity_enriched`, `llm_enriched`, `evidence_only`, `paper_cosine_08`, or `canonical_only` |
| `top_k` | integer | `5` | Candidate skill pairs to retrieve; range 1–25 |
| `include_details` | boolean | `true` | Include detailed extraction results in internal pipeline output |
| `include_embeddings` | boolean | `false` | Include embeddings in internal pipeline output |
| `include_graph` | boolean | `false` | Include graph diagnostics in internal pipeline output |
| `enable_critic` | boolean | `false` | Enable the optional LLM critic pass |
| `reasoning_max_pairs` | integer | `25` | Maximum reasoning pairs; range 1–100 |
| `reasoning_selection_strategy` | string | `balanced_coverage` | Pair selection: `balanced_coverage` or `global_top_cosine` |
| `enable_skill_importance` | boolean | configured default | Enable or disable JD skill importance estimation |

The public response remains compact even when internal detail flags are enabled.

## Example

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/pipeline/analyze" \
  -F "cv_file=@candidate.pdf" \
  -F "jd_file=@job-description.pdf" \
  -F "graph_mode=similarity_enriched" \
  -F "top_k=5"
```

## Successful response

The response uses the `standardized-output-v1` schema and includes the `X-Output-Schema-Version` header.

```json
{
  "match_score": null,
  "status": "MODEL_NOT_TRAINED",
  "cv_text": "Cleaned candidate CV text...",
  "jd_text": "Cleaned job description text...",
  "skill_gap_input": [],
  "proficiency_input": {
    "cv_skills": [],
    "jd_skills": []
  }
}
```

`match_score` is populated only when a verified trained PaperAligned GNN checkpoint successfully produces it. A missing or invalid checkpoint leaves the score `null`; the service does not replace it with a cosine or heuristic score. The response status explains whether a score was produced.

## Runtime requirements

- `OPENROUTER_API_KEY` is required when extraction or reasoning cannot be served from the local extraction caches.
- The pinned Sentence Transformer is downloaded on first use if it is not already cached by Hugging Face.
- Reusable extraction data is kept under `data/cache/stage6b3_live` and `data/cache/stage6c3b/doc_extraction`.
- The default GNN checkpoint path is `data/checkpoints/paper_aligned_gnn/paper_aligned_hybrid_gnn_v1.pt`.

`GET /health` provides service and embedding-model status. OpenAPI documentation is available at `/docs`.
