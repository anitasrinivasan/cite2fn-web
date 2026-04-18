# cite2fn-web (frontend)

Single-page Next.js app that uploads a `.docx` to the `cite2fn` API, polls job
status, lets the user review formatted citations, and downloads the result.

## Install

```bash
cd web
npm install
```

## Run (dev)

```bash
# Point at a running api/ service (default is http://localhost:8000)
export NEXT_PUBLIC_API_URL=http://localhost:8000

npm run dev
# -> http://localhost:3000
```

## Environment variables

| Var | Default | Purpose |
| --- | --- | --- |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Base URL of the `api/` service. Public — embedded in the bundle at build time. |
| `NEXT_PUBLIC_BUG_REPORT_URL` | GitHub issue URL | Where the "Report a bug" link points. |

## Architecture

**Single page, state transitions.** The page at `/` cycles through four states
driven by the job's `status`:

1. **Idle** — landing copy + `UploadZone` with style/format/LLM selectors.
2. **Processing** — `ProgressPanel` shows the current phase. `fetching` and
   `formatting` render an `X / Y` progress bar; other phases show a spinner.
3. **Review** — `ReviewTable` with every detected citation as an editable
   textarea. `needs_review` items are highlighted in amber.
4. **Done** — `DonePanel` with a download button and an expandable report.

The active `jobId` is kept in the URL hash (`#abc123…`). Refreshing during
processing returns to the same job instead of starting over.

## State flow

```
 [no hash]                  -> Landing (UploadZone)
 POST /api/jobs (upload)    -> set hash, start polling
 GET /api/jobs/:id (poll)   -> ProgressPanel
   status = awaiting_review -> ReviewTable
 POST /api/jobs/:id/review  -> resume polling
   status = done            -> DonePanel
   status = error           -> ErrorPanel
```

`useJob` (in `lib/`) polls `GET /api/jobs/:id` every 2s while the job is in
an active state and stops once it reaches a terminal state.

## Build

```bash
npm run build     # static + server components
npm run start     # production server on 3000
npm run typecheck # TypeScript only
```

## Docker

```bash
# From repo root — the build context must include the web/ directory
docker build -f web/Dockerfile -t cite2fn-web .
docker run --rm -p 3000:3000 -e NEXT_PUBLIC_API_URL=http://api:8000 cite2fn-web
```

Next's `output: "standalone"` means the image is minimal — just the built
server bundle, not the full workspace.

## Styling

Tailwind v4 via `@tailwindcss/postcss`. No component library, no UI kit —
plain Tailwind classes throughout. Restrained palette: slate for neutrals,
emerald for success, amber for review flags, red for errors.
