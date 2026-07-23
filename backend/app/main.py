from __future__ import annotations

import csv
import io
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session, selectinload

from app.db import Base, engine, get_db
from app.models import SessionRow, SummaryRow, TrialRow
from app.schemas import (
    CompleteOut,
    SessionCreate,
    SessionOut,
    SummaryOut,
    TrialBatchIn,
    TrialOut,
)
from app.scoring import compute_summary, flag_trial
from app.tmb_adapt import flatten_tmb_trials, task_id_from_referer

app = FastAPI(
    title="trialspine",
    description="Cognitive-task sessions: trials, summaries, CSV. Optional TMB HTML via POST /run.",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_HERE = Path(__file__).resolve().parent
_ROOT_CANDIDATES = [
    _HERE.parent.parent,  # repo root (backend/app -> trialspine)
    Path("/app"),
]
REPO_ROOT = next(
    (p for p in _ROOT_CANDIDATES if (p / "tasks" / "simple_rt").exists() or (p / "backend").exists()),
    _ROOT_CANDIDATES[0],
)
SIMPLE_RT_DIR = REPO_ROOT / "tasks" / "simple_rt"
if not SIMPLE_RT_DIR.exists():
    SIMPLE_RT_DIR = Path("/app/tasks/simple_rt")

TMB_REPO_PATH = Path(os.getenv("TMB_REPO_PATH", "/tmb"))


def _ensure_schema() -> None:
    Base.metadata.create_all(bind=engine)
    # Additive columns for upgrades from 0.1 volume
    insp = inspect(engine)
    if "sessions" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("sessions")}
    alters = []
    if "source" not in cols:
        alters.append("ALTER TABLE sessions ADD COLUMN source VARCHAR(32) DEFAULT 'simple_rt'")
    if "referer" not in cols:
        alters.append("ALTER TABLE sessions ADD COLUMN referer TEXT")
    if "client_score" not in cols:
        alters.append("ALTER TABLE sessions ADD COLUMN client_score FLOAT")
    if "raw_data_json" not in cols:
        alters.append("ALTER TABLE sessions ADD COLUMN raw_data_json TEXT")
    if "raw_outcomes_json" not in cols:
        alters.append("ALTER TABLE sessions ADD COLUMN raw_outcomes_json TEXT")
    trial_cols = {c["name"] for c in insp.get_columns("trials")} if "trials" in insp.get_table_names() else set()
    if "raw_json" not in trial_cols and "trials" in insp.get_table_names():
        alters.append("ALTER TABLE trials ADD COLUMN raw_json TEXT")
    with engine.begin() as conn:
        for stmt in alters:
            conn.execute(text(stmt))


@app.on_event("startup")
def on_startup() -> None:
    _ensure_schema()


def _page(title: str, body: str, *, active: str = "") -> HTMLResponse:
    def nav_cls(key: str) -> str:
        return ' class="active"' if active == key else ""

    html = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700&family=Source+Sans+3:wght@400;500;600&display=swap" rel="stylesheet"/>
<style>
:root{{
  --bg0:#f0f6fc; --bg1:#e8f1fa; --ink:#1a2b3c; --muted:#5a6f82;
  --card:#ffffff; --line:#c5d8eb; --accent:#2b6cb0; --accent-soft:#d6e8f7;
}}
*{{box-sizing:border-box}}
body{{
  font-family:"Source Sans 3",system-ui,sans-serif;
  max-width:920px;margin:0 auto;padding:0 1.25rem 3rem;
  line-height:1.5;color:var(--ink);
  background:linear-gradient(165deg,var(--bg0) 0%,#fff 42%,var(--bg1) 100%);
  min-height:100vh;
}}
.site-header{{
  display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:.75rem 1.25rem;
  padding:1.1rem 0 1rem;margin-bottom:1.5rem;
  border-bottom:1px solid var(--line);
}}
.brand{{
  font-family:Outfit,system-ui,sans-serif;font-weight:700;font-size:1.25rem;
  color:#163a5f;text-decoration:none;letter-spacing:-.02em;
}}
.brand:hover{{text-decoration:none;color:var(--accent)}}
.site-nav{{display:flex;flex-wrap:wrap;gap:.35rem .15rem}}
.site-nav a{{
  color:var(--muted);text-decoration:none;font-weight:500;font-size:.95rem;
  padding:.35rem .7rem;border-radius:8px;
}}
.site-nav a:hover{{color:var(--accent);background:rgba(43,108,176,.08);text-decoration:none}}
.site-nav a.active{{color:var(--accent);background:var(--accent-soft)}}
h1,h2{{font-family:Outfit,system-ui,sans-serif;font-weight:600;letter-spacing:-.02em}}
h1{{margin:0 0 .4rem;font-size:1.85rem;color:#163a5f}}
h2{{margin:1.4rem 0 .55rem;font-size:1.15rem;color:#1e4a73}}
.section-label{{
  font-family:Outfit,system-ui,sans-serif;font-size:.75rem;font-weight:600;
  text-transform:uppercase;letter-spacing:.06em;color:var(--accent);margin:1.75rem 0 .5rem;
}}
a{{color:var(--accent);text-decoration:none;font-weight:500}}
a:hover{{text-decoration:underline}}
.muted{{color:var(--muted);font-size:.92rem}}
.lede{{font-size:1.05rem;max-width:38rem;margin:0 0 1rem}}
.card{{
  border:1px solid var(--line);border-radius:12px;padding:1.15rem 1.35rem;margin:1.1rem 0;
  background:var(--card);box-shadow:0 1px 2px rgba(43,108,176,.06),0 8px 24px rgba(43,108,176,.05);
}}
.card h2{{margin-top:.15rem}}
.card-grid{{display:grid;gap:1rem;margin:1rem 0}}
@media(min-width:640px){{.card-grid.two{{grid-template-columns:1fr 1fr}}}}
.btn{{
  display:inline-block;margin-top:.55rem;padding:.5rem .95rem;border-radius:8px;
  background:var(--accent);color:#fff!important;font-weight:600;text-decoration:none!important;
}}
.btn:hover{{filter:brightness(1.06);text-decoration:none!important}}
.btn-ghost{{
  display:inline-block;margin-top:.55rem;margin-left:.35rem;padding:.5rem .95rem;border-radius:8px;
  background:transparent;color:var(--accent)!important;border:1px solid var(--line);font-weight:600;
  text-decoration:none!important;
}}
.btn-ghost:hover{{background:var(--accent-soft);text-decoration:none!important}}
.test-list{{list-style:none;padding:0;margin:.5rem 0 0;columns:1}}
@media(min-width:640px){{.test-list{{columns:2;column-gap:1.5rem}}}}
.test-list li{{
  break-inside:avoid;padding:.45rem .55rem;margin:0 0 .35rem;
  border:1px solid transparent;border-radius:8px;
}}
.test-list li:hover{{background:#f7fbfe;border-color:var(--line)}}
.test-list a{{font-weight:600}}
table{{border-collapse:collapse;width:100%;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}}
th,td{{border-bottom:1px solid #e4eef7;padding:.55rem .55rem;text-align:left;font-size:.92rem}}
thead th{{background:var(--accent-soft);color:#1e4a73;font-weight:600;font-size:.82rem;text-transform:uppercase;letter-spacing:.03em}}
tbody tr:hover{{background:#f7fbfe}}
tbody tr:last-child td{{border-bottom:0}}
pre{{background:#f5f9fc;border:1px solid var(--line);border-radius:8px;padding:.85rem;overflow:auto;font-size:.82rem}}
code{{background:var(--accent-soft);color:#1e4a73;padding:.05rem .35rem;border-radius:4px;font-size:.9em}}
ul{{padding-left:1.2rem}}
li{{margin:.25rem 0}}
.score-hero{{font-size:1.75rem;margin:.15rem 0 .6rem;color:#163a5f}}
.site-footer{{margin-top:2.5rem;padding-top:1rem;border-top:1px solid var(--line);font-size:.85rem;color:var(--muted)}}
</style></head><body>
<header class="site-header">
  <a class="brand" href="/">trialspine</a>
  <nav class="site-nav" aria-label="Primary">
    <a href="/"{nav_cls("tests")}>Tests</a>
    <a href="/dashboard"{nav_cls("dashboard")}>Dashboard</a>
    <a href="/docs"{nav_cls("docs")}>API docs</a>
  </nav>
</header>
{body}
<footer class="site-footer">Not affiliated with The Many Brains Project or TestMyBrain.</footer>
</body></html>"""
    return HTMLResponse(html)


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "tmb_repo_mounted": (TMB_REPO_PATH / "TMB_Tests").is_dir(),
        "tmb_repo_path": str(TMB_REPO_PATH),
    }


@app.get("/", response_class=HTMLResponse)
def hub() -> HTMLResponse:
    tmb_ok = (TMB_REPO_PATH / "TMB_Tests").is_dir()
    tmb_links = []
    if tmb_ok:
        for folder in sorted((TMB_REPO_PATH / "TMB_Tests").iterdir()):
            if not folder.is_dir() or not folder.name.startswith("TMB_"):
                continue
            src = folder / "src"
            if not src.is_dir():
                continue
            htmls = sorted(src.glob("*Main*.html")) or sorted(src.glob("*.html"))
            if not htmls:
                continue
            rel = htmls[0].relative_to(TMB_REPO_PATH).as_posix()
            label = folder.name.removeprefix("TMB_")
            tmb_links.append(
                f'<li><a href="/tmb/{rel}?demo=true">{label}</a> '
                f'<span class="muted">{htmls[0].name}</span></li>'
            )

    catalog = (
        f'<ul class="test-list">{"".join(tmb_links)}</ul>'
        if tmb_links
        else '<p class="muted">Open-test repo not mounted — set <code>TMB_REPO_PATH</code>.</p>'
    )

    body = f"""
    <h1>trialspine</h1>
    <p class="lede">Run cognitive tasks in the browser. Sessions land in Postgres with trial rows,
    summaries, and CSV export.</p>

    <p class="section-label">Tasks</p>
    <div class="card-grid two">
      <div class="card">
        <h2>Simple RT</h2>
        <p>Built-in reaction-time task. Server scoring, QC flags, CSV.</p>
        <a class="btn" href="/tasks/simple_rt/">Start</a>
      </div>
      <div class="card">
        <h2>Open TMB tests</h2>
        <p>HTML/JS from the sibling TestMyBrain checkout. Completions post to <code>/run</code>.</p>
        <p class="muted">{"Mounted at " + str(TMB_REPO_PATH) if tmb_ok else "Set TMB_REPO_PATH — repo not found."}</p>
      </div>
    </div>

    <div class="card">
      <h2>Catalog</h2>
      {catalog}
    </div>

    <p class="section-label">Data</p>
    <div class="card">
      <p><a href="/dashboard">Dashboard</a> lists all sessions.
         REST API: <a href="/docs">/docs</a> (<code>/v1/sessions</code>, <code>POST /run</code>).</p>
      <a class="btn" href="/dashboard">Dashboard</a>
      <a class="btn-ghost" href="/docs">API docs</a>
    </div>
    """
    return _page("trialspine", body, active="tests")


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(db: Session = Depends(get_db)) -> HTMLResponse:
    rows = db.scalars(select(SessionRow).order_by(SessionRow.created_at.desc()).limit(100)).all()
    trs = []
    for s in rows:
        trs.append(
            "<tr>"
            f"<td><a href='/dashboard/sessions/{s.id}'>{str(s.id)[:8]}…</a></td>"
            f"<td>{s.source}</td><td>{s.task_id}</td><td>{s.status}</td>"
            f"<td>{s.client_score if s.client_score is not None else ''}</td>"
            f"<td>{s.created_at}</td>"
            f"<td><a href='/v1/sessions/{s.id}/export.csv'>csv</a></td>"
            "</tr>"
        )
    body = f"""
    <h1>Dashboard</h1>
    <p class="muted">Sessions from all tasks.</p>
    <table>
      <thead><tr><th>id</th><th>source</th><th>task</th><th>status</th><th>client_score</th><th>created</th><th></th></tr></thead>
      <tbody>{"".join(trs) if trs else '<tr><td colspan="7" class="muted">No sessions yet</td></tr>'}</tbody>
    </table>
    """
    return _page("Dashboard", body, active="dashboard")



@app.get("/dashboard/sessions/{session_id}", response_class=HTMLResponse)
def dashboard_session(session_id: uuid.UUID, db: Session = Depends(get_db)) -> HTMLResponse:
    session = db.scalar(
        select(SessionRow)
        .where(SessionRow.id == session_id)
        .options(selectinload(SessionRow.trials), selectinload(SessionRow.summary))
    )
    if not session:
        raise HTTPException(404, "session not found")

    summary_pre = ""
    if session.summary:
        summary_pre = json.dumps(
            {
                "score": session.summary.score,
                "mean_rt_ms": session.summary.mean_rt_ms,
                "median_rt_ms": session.summary.median_rt_ms,
                "n_test_trials": session.summary.n_test_trials,
                "n_valid_trials": session.summary.n_valid_trials,
                "n_flagged_trials": session.summary.n_flagged_trials,
                "qc_flag_any": session.summary.qc_flag_any,
                "qc_notes": session.summary.qc_notes,
            },
            indent=2,
        )

    outcomes_obj: dict = {}
    outcomes_pre = session.raw_outcomes_json or ""
    try:
        if outcomes_pre:
            outcomes_obj = json.loads(outcomes_pre)
            outcomes_pre = json.dumps(outcomes_obj, indent=2, ensure_ascii=False)[:8000]
    except json.JSONDecodeError:
        pass

    outcome_rows = "".join(
        f"<tr><th>{k}</th><td>{outcomes_obj[k]}</td></tr>"
        for k in (
            "score",
            "accuracy",
            "meanRTc",
            "medianRTc",
            "sdRTc",
            "responseDevice",
            "testVersion",
            "flag_any",
            "flag_accuracy",
            "flag_medianRTc",
        )
        if k in outcomes_obj
    )
    outcome_table = (
        f"<table><tbody>{outcome_rows}</tbody></table>" if outcome_rows else ""
    )

    trial_preview = []
    for t in sorted(session.trials, key=lambda x: x.trial_index)[:40]:
        trial_preview.append(
            "<tr>"
            f"<td>{t.trial_index}</td><td>{t.trial_type}</td>"
            f"<td>{t.response or ''}</td><td>{t.correct if t.correct is not None else ''}</td>"
            f"<td>{t.rt_ms if t.rt_ms is not None else ''}</td>"
            f"<td>{'⚠' if t.flagged else ''}</td>"
            "</tr>"
        )
    more = (
        f"<p class='muted'>Showing {min(40, len(session.trials))} of {len(session.trials)} trials. "
        f"<a href='/v1/sessions/{session.id}/export.csv'>Full CSV</a></p>"
        if session.trials
        else "<p class='muted'>No trials stored.</p>"
    )

    body = f"""
    <p class="muted"><a href="/dashboard">← All sessions</a></p>
    <h1>Session</h1>
    <p class="muted"><code>{session.id}</code></p>
    <div class="card">
    <ul>
      <li>source: <code>{session.source}</code></li>
      <li>task_id: <code>{session.task_id}</code></li>
      <li>status: {session.status}</li>
      <li>client_score: <strong>{session.client_score if session.client_score is not None else "—"}</strong></li>
      <li>trials stored: {len(session.trials)}</li>
      <li>referer: <span class="muted">{session.referer or ""}</span></li>
    </ul>
    <p><a href="/v1/sessions/{session.id}/export.csv">Download CSV</a></p>
    </div>
    {"<h2>Client outcomes</h2><div class='card'>" + outcome_table + "</div>" if outcome_table else ""}
    <h2>Summary</h2>
    <pre>{summary_pre or "(none)"}</pre>
    <h2>Trials</h2>
    {more}
    {"<table><thead><tr><th>#</th><th>type</th><th>resp</th><th>correct</th><th>rt_ms</th><th></th></tr></thead><tbody>" + "".join(trial_preview) + "</tbody></table>" if trial_preview else ""}
    <h2>Raw outcomes</h2>
    <pre>{outcomes_pre or "(none)"}</pre>
    """
    return _page(f"Session {session.id}", body, active="dashboard")


@app.post("/v1/sessions", response_model=SessionOut)
def create_session(body: SessionCreate, db: Session = Depends(get_db)) -> SessionRow:
    row = SessionRow(
        task_id=body.task_id,
        device_info=body.device_info,
        status="active",
        source="simple_rt",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@app.get("/v1/sessions/{session_id}", response_model=SessionOut)
def get_session(session_id: uuid.UUID, db: Session = Depends(get_db)) -> SessionRow:
    row = db.get(SessionRow, session_id)
    if not row:
        raise HTTPException(404, "session not found")
    return row


@app.post("/v1/sessions/{session_id}/trials", response_model=list[TrialOut])
def post_trials(
    session_id: uuid.UUID, body: TrialBatchIn, db: Session = Depends(get_db)
) -> list[TrialRow]:
    session = db.get(SessionRow, session_id)
    if not session:
        raise HTTPException(404, "session not found")
    if session.status != "active":
        raise HTTPException(409, f"session is {session.status}")

    created: list[TrialRow] = []
    for item in body.trials:
        flagged, reason = flag_trial(item.rt_ms, item.response)
        trial = TrialRow(
            session_id=session_id,
            trial_index=item.trial_index,
            trial_type=item.trial_type,
            stimulus_id=item.stimulus_id,
            response=item.response,
            correct=item.correct if item.correct is not None else (item.response is not None),
            rt_ms=item.rt_ms,
            flagged=flagged,
            flag_reason=reason,
            client_ts=item.client_ts,
        )
        db.add(trial)
        created.append(trial)

    db.commit()
    for t in created:
        db.refresh(t)
    return created


@app.post("/v1/sessions/{session_id}/complete", response_model=CompleteOut)
def complete_session(session_id: uuid.UUID, db: Session = Depends(get_db)) -> CompleteOut:
    session = db.scalar(
        select(SessionRow)
        .where(SessionRow.id == session_id)
        .options(selectinload(SessionRow.trials), selectinload(SessionRow.summary))
    )
    if not session:
        raise HTTPException(404, "session not found")

    stats = compute_summary(list(session.trials))
    if session.summary:
        summary = session.summary
        for k, v in stats.items():
            setattr(summary, k, v)
    else:
        summary = SummaryRow(session_id=session.id, **stats)
        db.add(summary)

    session.status = "complete" if stats["n_test_trials"] > 0 else "incomplete"
    session.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session)
    db.refresh(summary)

    return CompleteOut(session=SessionOut.model_validate(session), summary=SummaryOut.model_validate(summary))


@app.get("/v1/sessions/{session_id}/summary", response_model=SummaryOut)
def get_summary(session_id: uuid.UUID, db: Session = Depends(get_db)) -> SummaryRow:
    summary = db.scalar(select(SummaryRow).where(SummaryRow.session_id == session_id))
    if not summary:
        raise HTTPException(404, "summary not found; call /complete first")
    return summary


@app.get("/v1/sessions/{session_id}/export.csv")
def export_csv(session_id: uuid.UUID, db: Session = Depends(get_db)) -> StreamingResponse:
    session = db.scalar(
        select(SessionRow)
        .where(SessionRow.id == session_id)
        .options(selectinload(SessionRow.trials), selectinload(SessionRow.summary))
    )
    if not session:
        raise HTTPException(404, "session not found")

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "record_type",
            "session_id",
            "source",
            "task_id",
            "session_status",
            "trial_index",
            "trial_type",
            "stimulus_id",
            "response",
            "correct",
            "rt_ms",
            "flagged",
            "flag_reason",
            "score",
            "mean_rt_ms",
            "median_rt_ms",
            "sd_rt_ms",
            "accuracy",
            "n_test_trials",
            "n_valid_trials",
            "n_flagged_trials",
            "qc_flag_any",
            "qc_notes",
        ]
    )

    for t in sorted(session.trials, key=lambda x: x.trial_index):
        writer.writerow(
            [
                "trial",
                str(session.id),
                session.source,
                session.task_id,
                session.status,
                t.trial_index,
                t.trial_type,
                t.stimulus_id,
                t.response,
                t.correct,
                t.rt_ms,
                t.flagged,
                t.flag_reason,
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
            ]
        )

    s = session.summary
    if s:
        writer.writerow(
            [
                "summary",
                str(session.id),
                session.source,
                session.task_id,
                session.status,
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                s.score,
                s.mean_rt_ms,
                s.median_rt_ms,
                s.sd_rt_ms,
                s.accuracy,
                s.n_test_trials,
                s.n_valid_trials,
                s.n_flagged_trials,
                s.qc_flag_any,
                s.qc_notes,
            ]
        )

    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="session_{session_id}.csv"'},
    )


@app.post("/run", response_class=HTMLResponse)
async def tmb_run(
    request: Request,
    data: str = Form(...),
    score: str = Form(...),
    outcomes: str = Form(""),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Accept TMB form fields: data, score, outcomes."""
    try:
        trials_raw = json.loads(data) if data else []
    except json.JSONDecodeError as exc:
        raise HTTPException(400, f"invalid data JSON: {exc}") from exc

    try:
        outcomes_obj = json.loads(outcomes) if outcomes else {}
    except json.JSONDecodeError:
        outcomes_obj = {"raw": outcomes}

    try:
        score_val = float(score) if score not in ("", None) else None
    except ValueError:
        score_val = None

    referer = request.headers.get("referer")
    task_id = task_id_from_referer(referer)

    session = SessionRow(
        task_id=task_id,
        source="tmb_run",
        status="complete",
        referer=referer,
        client_score=score_val,
        raw_data_json=json.dumps(trials_raw, ensure_ascii=False),
        raw_outcomes_json=json.dumps(outcomes_obj, ensure_ascii=False),
        device_info=request.headers.get("user-agent"),
        completed_at=datetime.now(timezone.utc),
    )
    db.add(session)
    db.flush()

    flat = flatten_tmb_trials(trials_raw)
    trial_rows: list[TrialRow] = []
    for item in flat:
        flagged, reason = flag_trial(item.get("rt_ms"), item.get("response"))
        if item.get("rt_ms") is None and item.get("response") is None:
            flagged, reason = False, None
        tr = TrialRow(
            session_id=session.id,
            trial_index=item["trial_index"],
            trial_type=item["trial_type"],
            stimulus_id=item["stimulus_id"],
            response=item.get("response"),
            correct=item.get("correct"),
            rt_ms=item.get("rt_ms"),
            flagged=flagged,
            flag_reason=reason,
            raw_json=item.get("raw_json"),
        )
        db.add(tr)
        trial_rows.append(tr)

    stats = compute_summary(trial_rows)
    if score_val is not None:
        stats["score"] = score_val
    if score_val is None and stats["n_valid_trials"] == 0:
        stats["qc_flag_any"] = True

    summary = SummaryRow(session_id=session.id, **stats)
    db.add(summary)
    db.commit()
    db.refresh(session)

    outcome_bits = []
    for key in ("accuracy", "meanRTc", "medianRTc", "sdRTc", "responseDevice", "testVersion"):
        if isinstance(outcomes_obj, dict) and key in outcomes_obj:
            outcome_bits.append(f"<li>{key}: <strong>{outcomes_obj[key]}</strong></li>")
    outcomes_list = "".join(outcome_bits)

    body = f"""
    <h1>Test results</h1>
    <div class="card">
      <p class="score-hero">Score: <strong>{score_val if score_val is not None else "—"}</strong></p>
      <ul>
        <li>session: <a href="/dashboard/sessions/{session.id}"><code>{session.id}</code></a></li>
        <li>task_id: <code>{task_id}</code></li>
        <li>trials: {len(flat)}</li>
        {outcomes_list}
      </ul>
      <a class="btn" href="/dashboard/sessions/{session.id}">View session</a>
      <a class="btn-ghost" href="/v1/sessions/{session.id}/export.csv">Download CSV</a>
    </div>
    """
    return _page("Test results", body, active="dashboard")


BRIDGE_JS = _HERE / "static" / "tmb_submit_bridge.js"
BRIDGE_TAG = '<script src="/static/tmb_submit_bridge.js"></script>\n'


@app.get("/static/tmb_submit_bridge.js")
def tmb_submit_bridge() -> FileResponse:
    if not BRIDGE_JS.is_file():
        raise HTTPException(404, "bridge not found")
    return FileResponse(BRIDGE_JS, media_type="application/javascript")


def _inject_tmb_bridge(html: str) -> str:
    if "tmb_submit_bridge.js" in html:
        return html
    lower = html.lower()
    idx = lower.rfind("</head>")
    if idx != -1:
        return html[:idx] + BRIDGE_TAG + html[idx:]
    return BRIDGE_TAG + html


@app.get("/tmb/{file_path:path}")
def serve_tmb(file_path: str):
    """Serve TMB checkout files; inject submit bridge into HTML."""
    root = TMB_REPO_PATH.resolve()
    if not (root / "TMB_Tests").is_dir():
        raise HTTPException(404, "TMB repo not mounted")
    target = (root / file_path).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise HTTPException(404, "not found") from exc
    if not target.is_file():
        raise HTTPException(404, "not found")

    suffix = target.suffix.lower()
    if suffix in {".html", ".htm"}:
        text = target.read_text(encoding="utf-8", errors="replace")
        return HTMLResponse(_inject_tmb_bridge(text))

    media = {
        ".js": "application/javascript",
        ".css": "text/css",
        ".json": "application/json",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".svg": "image/svg+xml",
        ".woff": "font/woff",
        ".woff2": "font/woff2",
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
    }.get(suffix)
    return FileResponse(target, media_type=media)


# --- static mounts (order matters: specific routes already registered) ---
if SIMPLE_RT_DIR.is_dir():
    app.mount("/tasks/simple_rt", StaticFiles(directory=str(SIMPLE_RT_DIR), html=True), name="simple_rt")
    # Keep /static for existing simple_rt asset URLs in index.html
    app.mount("/static", StaticFiles(directory=str(SIMPLE_RT_DIR)), name="static")