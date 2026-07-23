# trialspine

**Live demo:** [https://trialspine.fly.dev/](https://trialspine.fly.dev/)

The name is a hint: a lightweight backbone for cognitive tasks—sessions, trial rows, summaries, and CSV export.

Demo backend for browser cognitive tasks: Postgres holds sessions, trial rows, summaries, QC flags, and CSV export.

Built-in task: **simple reaction time** at `/tasks/simple_rt/`. Optionally mount [open TestMyBrain](https://github.com/manybrainsproject/TestMyBrainCodeRepo) HTML tests and take their `POST /run` submissions.

Independent demo — not affiliated with The Many Brains Project or testmybrain.org. Not for clinical use.

## What's here

- **simple_rt** — static page plus `/v1/sessions` API (create → append trials → complete → export). Scoring: [SCORING.md](SCORING.md).
- **Open TMB (optional)** — serve upstream HTML from `/tmb/…`; store `data` / `score` / `outcomes` on `POST /run`. Tables: [data_dictionary.md](data_dictionary.md).
- **UI** — `/` hub, `/dashboard` list and session detail.

## Requirements

- Docker and Docker Compose v2
- Open TMB only: git clone of [TestMyBrainCodeRepo](https://github.com/manybrainsproject/TestMyBrainCodeRepo)

## Quick start

```bash
git clone https://github.com/haowu0802/trialspine.git
cd trialspine
docker compose up --build
```

http://localhost:8000

| URL | |
|-----|---|
| `/` | Hub |
| `/tasks/simple_rt/` | Simple RT |
| `/dashboard` | Sessions |
| `/docs` | OpenAPI |

## Optional: open TestMyBrain tests

`docker-compose.tmb.yml` bind-mounts your clone read-only at `/tmb` in the API container.

```bash
git clone https://github.com/manybrainsproject/TestMyBrainCodeRepo.git vendor/TestMyBrainCodeRepo
docker compose -f docker-compose.yml -f docker-compose.tmb.yml up --build
```

The hub links to `/tmb/…` with `?demo=true` (upstream short run — a few trials).

Upstream posts to `/run` when URL params `showresults`, `autosave`, and `filename` are **not** set; those params switch to local CSV/download instead. Some tests stop at a “Test complete!” alert without calling `tmbSubmitToServer`; HTML from `/tmb/` gets `tmb_submit_bridge.js` injected to POST anyway.

Other clone path: copy `.env.example` to `.env`, set `TMB_HOST_PATH`.

## Configuration

| Variable | Default | |
|----------|---------|---|
| `DATABASE_URL` | in `docker-compose.yml` | Postgres |
| `TMB_REPO_PATH` | `/tmb` | Path inside container |
| `TMB_HOST_PATH` | `./vendor/TestMyBrainCodeRepo` | Host mount (overlay compose only) |

## API (essentials)

**simple_rt**

- `POST /v1/sessions`
- `POST /v1/sessions/{id}/trials`
- `POST /v1/sessions/{id}/complete` — `scoring.py` → summary row
- `GET /v1/sessions/{id}/export.csv`

Also `GET /v1/sessions/{id}`, `GET /v1/sessions/{id}/summary`, `GET /health`.

**TMB submit**

- `POST /run` — form: `data` (JSON array), `score`, optional `outcomes` (JSON). Client `score` is stored; trials are flattened in `tmb_adapt.py` (best-effort, not the same path as simple_rt scoring).

## Layout

```text
backend/app/       FastAPI, models, scoring, TMB adapter
tasks/simple_rt/   built-in task
docker-compose.yml
docker-compose.tmb.yml
```

## Development

Compose bind-mounts `backend/app` and `tasks/`. After edits:

```bash
docker compose restart api
```

Rebuild the image if `requirements.txt` or the Dockerfile changes.

## License

MIT — [LICENSE](LICENSE). Mounting TestMyBrain tests is optional; they stay under their upstream licenses in your clone.
