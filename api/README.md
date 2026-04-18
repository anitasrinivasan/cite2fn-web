# cite2fn-api

FastAPI service that accepts `.docx` uploads, orchestrates the `cite2fn` core library, and returns a cited document.

## Install (local dev)

```bash
# From repo root
python -m venv .venv
source .venv/bin/activate
pip install -e ./core
pip install -e './api[dev]'
```

`core` must be installed before `api` because `api` imports `cite2fn` directly.

## Run

```bash
# Optional: provide a service-owned Groq key so the free fallback works
export GROQ_API_KEY=gsk_...

uvicorn api.main:app --reload
```

The app binds to `http://localhost:8000`. Health check:

```bash
curl http://localhost:8000/health
```

## Environment variables

| Var | Default | Purpose |
| --- | --- | --- |
| `STORAGE_DIR` | `./data` | Job artifacts (uploads, outputs, citations JSON) and SQLite DB live here |
| `GROQ_API_KEY` | — | Service-owned Groq key for the free fallback LLM path. If unset, users must supply their own Claude key. |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq-hosted OSS model id |
| `CLAUDE_MODEL` | `claude-sonnet-4-6` | Anthropic model id when the user supplies their own key |
| `CORS_ORIGINS` | `*` | Comma-separated origins allowed to call the API |
| `MAX_UPLOAD_MB` | `25` | Upload size cap |
| `JOB_TTL_HOURS` | `24` | Hours to retain job artifacts (cleanup cron, not yet implemented) |

## Routes

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/jobs` | Upload `.docx` + options (multipart). Returns job id + initial status. |
| `GET`  | `/api/jobs/{id}` | Status + progress. When `status=awaiting_review`, response includes the `citations` payload for user review. |
| `POST` | `/api/jobs/{id}/review` | Accept user edits to formatted citations, trigger assembly. |
| `GET`  | `/api/jobs/{id}/download` | Stream the output `.docx`. |
| `GET`  | `/health` | Liveness + whether the Groq fallback is configured. |

### Upload form fields

| Field | Required | Values |
| --- | --- | --- |
| `file` | yes | `.docx` under `MAX_UPLOAD_MB` |
| `style` | yes | `bluebook` \| `apa` |
| `output_format` | yes | `footnotes` \| `endnotes` \| `references` |
| `llm_backend` | yes | `claude` (needs `claude_api_key`) \| `groq` (free, server-configured) |
| `claude_api_key` | when `llm_backend=claude` | User's own Anthropic key. Held in memory for the job's lifetime only. |
| `keep_references` | no | `true` \| `false` (default `false`) |

## Job lifecycle

```
pending -> detecting -> fetching -> formatting -> awaiting_review
                                                      |
                                    POST /review -> assembling -> done
```

`error` is reachable from any state. Progress updates emit a `progress` object:

```json
{"phase": "fetching", "done": 5, "total": 12}
```

## Tests

```bash
pytest
```

## Docker

```bash
# From repo root — context must include both core/ and api/
docker build -f api/Dockerfile -t cite2fn-api .
docker run --rm -p 8000:8000 -e GROQ_API_KEY=$GROQ_API_KEY -v $(pwd)/data:/data cite2fn-api
```

## Architecture notes

- **Job execution** uses `asyncio.create_task()` (fire-and-forget on the FastAPI event loop). In-flight jobs are lost on restart — v1 intentionally accepts this; production would move to Celery/RQ.
- **User's Claude API key** is held in an in-memory dict (`api/jobs.py:_api_keys`), never written to SQLite or disk, and scrubbed when the job terminates (including on error).
- **Formatter batches** citations in chunks of 10 to the LLM for incremental progress and smaller JSON payloads. Chunks run concurrently via `asyncio.as_completed`.
- **Claude driver** uses Anthropic prompt caching on the long system prompt. **Groq driver** uses a lean system prompt (Groq has no prompt caching) and OpenAI-compatible JSON mode.
