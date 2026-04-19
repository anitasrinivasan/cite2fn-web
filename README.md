# cite2fn

Convert hyperlinked citations in a Word document to properly formatted Bluebook or APA footnotes, endnotes, or a reference list — in the browser, no install.

Drop a `.docx` with links to your sources; cite2fn detects every citation, pulls metadata from each URL, formats it in your chosen style, lets you review any flagged items, and gives you back a cited document.

## What&rsquo;s in this repo

```
cite2fn-web/
├── core/   — the citation-conversion library (Python, pip-installable)
├── api/    — FastAPI service that exposes the library over HTTP
├── web/    — Next.js frontend (the website you&rsquo;re probably thinking of)
├── scripts/— dev harness for E2E testing without the LLM
└── README.md
```

- **[`core/`](core/)** — pure library. Detects citations in a `.docx`, fetches URL metadata, cleans up the body text, inserts footnotes, and handles Bluebook short forms like *supra* / *Id.* No web dependencies — reusable from a CLI, notebook, or other service.
- **[`api/`](api/)** — FastAPI service. Accepts uploads, orchestrates the pipeline (`detect → fetch → format → review → assemble`), and calls the user&rsquo;s chosen LLM backend (Claude via user-supplied key, or free fallback via Groq). Job state in SQLite; uploads auto-deleted after 24 h.
- **[`web/`](web/)** — Next.js single-page UI. Upload form, live progress with time estimate, review table with editable citations, download. Plus static pages for how-it-works, terms, privacy.
- **[`scripts/harness.py`](scripts/harness.py)** — local harness that runs the real pipeline against a real `.docx` with a *mocked* LLM so body-placement bugs surface without burning API quota.

## Local development

Prereqs: Python 3.11+ and Node 22+.

```bash
# Install the core library and the API (shared venv)
cd core && python -m venv .venv && source .venv/bin/activate
pip install -e .
pip install -e ../api[dev]

# Boot the API (optional: set GROQ_API_KEY for the free fallback)
cd ..
GROQ_API_KEY=... uvicorn api.main:app --port 8000

# In another terminal, boot the web UI
cd web
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

Open <http://localhost:3000>.

## Deployment

Both `api/` and `web/` ship with `Dockerfile`s designed for a minimal production image. See each sub-directory&rsquo;s README for the env vars you need to set (`GROQ_API_KEY`, `STORAGE_DIR`, `CORS_ORIGINS`, `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_BUG_REPORT_URL`).

## Tech stack

Python 3.12 / FastAPI / python-docx / pymupdf / Anthropic SDK / OpenAI SDK (for Groq&rsquo;s OpenAI-compatible endpoint) · Next.js 15 / React 19 / TypeScript / Tailwind 4 · SQLite.

## Tests

```bash
# Python (core + api): 40+ unit tests
cd core && source .venv/bin/activate
pytest core/tests api/tests -q

# Type + build check (web)
cd ../web && npm run typecheck && npm run build

# End-to-end body-placement harness (no LLM required)
python scripts/harness.py path/to/your.docx /tmp/out.docx
```

## License

MIT — see [LICENSE](LICENSE).

Built by [Anita Srinivasan](https://www.anitasrinivasan.com).
