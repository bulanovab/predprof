from __future__ import annotations

from pathlib import Path
import time
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func

from .admission import compute_admission
from .config import DAYS, PROGRAMS, PROGRAM_ORDER
from .db import SessionLocal
from .importer import import_day, reset_db, init_db
from .models import ApplicationSnapshot, Program, Snapshot
from .report import generate_report

app = FastAPI(title="Анализ поступления")

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

PAGE_SIZE = 200


def _latest_imported_day(db) -> Optional[str]:
    snap = (
        db.execute(select(Snapshot).order_by(Snapshot.imported_at.desc())).scalars().first()
    )
    return snap.day if snap else None


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    day: Optional[str] = None,
    program: Optional[str] = None,
    page: int = 1,
):
    with SessionLocal() as db:
        if day is None:
            day = _latest_imported_day(db)
        if day is None:
            return TEMPLATES.TemplateResponse(
                "index.html",
                {
                    "request": request,
                    "days": DAYS,
                    "selected_day": None,
                    "programs": PROGRAM_ORDER,
                    "selected_program": program or PROGRAM_ORDER[0],
                    "program_rows": [],
                    "unified_rows": [],
                    "cutoff_rows": [],
                    "page": 1,
                    "page_count": 1,
                    "page_size": PAGE_SIZE,
                    "total_count": 0,
                    "message": "Нет загруженных данных. Используйте /api/import/{day}.",
                },
            )

        if program is None or program not in PROGRAMS:
            program = PROGRAM_ORDER[0]

        if page < 1:
            page = 1

        snapshot = (
            db.execute(
                select(Snapshot)
                .where(Snapshot.day == day)
                .order_by(Snapshot.imported_at.desc())
                .limit(1)
            )
            .scalars()
            .first()
        )
        if snapshot is None:
            program_rows = []
            unified_rows = []
            cutoff_rows = []
            total_count = 0
            page_count = 1
        else:
            programs = {p.id: p for p in db.execute(select(Program)).scalars().all()}
            code_by_id = {p.id: p.code for p in programs.values()}
            id_by_code = {p.code: p.id for p in programs.values()}

            # Program table
            total_count = (
                db.execute(
                    select(func.count())
                    .select_from(ApplicationSnapshot)
                    .where(
                        ApplicationSnapshot.snapshot_id == snapshot.id,
                        ApplicationSnapshot.program_id == id_by_code[program],
                    )
                )
                .scalar_one()
            )
            page_count = max(1, (total_count + PAGE_SIZE - 1) // PAGE_SIZE)
            if page > page_count:
                page = page_count
            offset = (page - 1) * PAGE_SIZE
            rows = (
                db.execute(
                    select(ApplicationSnapshot)
                    .where(
                        ApplicationSnapshot.snapshot_id == snapshot.id,
                        ApplicationSnapshot.program_id == id_by_code[program],
                    )
                    .order_by(
                        ApplicationSnapshot.total.desc(),
                        ApplicationSnapshot.applicant_id.asc(),
                    )
                    .limit(PAGE_SIZE)
                    .offset(offset)
                )
                .scalars()
                .all()
            )
            program_rows = [
                {
                    "applicant_id": r.applicant_id,
                    "consent": r.consent,
                    "priority": r.priority,
                    "physics_ikt": r.physics_ikt,
                    "russian": r.russian,
                    "math": r.math,
                    "achievements": r.achievements,
                    "total": r.total,
                }
                for r in rows
            ]

            # Unified list
            all_rows = (
                db.execute(
                    select(ApplicationSnapshot).where(ApplicationSnapshot.snapshot_id == snapshot.id)
                )
                .scalars()
                .all()
            )
            by_applicant = {}
            for r in all_rows:
                by_applicant.setdefault(r.applicant_id, []).append(
                    (r.priority, code_by_id[r.program_id])
                )
            unified_rows = []
            for aid, items in by_applicant.items():
                items.sort(key=lambda x: x[0])
                chain = ", ".join(f"{code}({prio})" for prio, code in items)
                unified_rows.append({"applicant_id": aid, "chain": chain})
            unified_rows.sort(key=lambda x: x["applicant_id"])

            # Cutoffs
            admission = compute_admission(day, db=db)
            cutoff_rows = []
            for code in PROGRAM_ORDER:
                res = admission[code]
                cutoff_rows.append(
                    {
                        "program": code,
                        "seats": PROGRAMS[code]["seats"],
                        "consent": res.consent_count,
                        "cutoff": res.cutoff if res.cutoff is not None else "НЕДОБОР",
                    }
                )

        return TEMPLATES.TemplateResponse(
            "index.html",
            {
                "request": request,
                "days": DAYS,
                "selected_day": day,
                "programs": PROGRAM_ORDER,
                "selected_program": program,
                "program_rows": program_rows,
                "unified_rows": unified_rows,
                "cutoff_rows": cutoff_rows,
                "page": page,
                "page_count": page_count,
                "page_size": PAGE_SIZE,
                "total_count": total_count,
                "message": None,
            },
        )


@app.post("/api/import/{day}")
def api_import(day: str):
    started = time.perf_counter()
    snapshot_id = import_day(day)
    duration_ms = int((time.perf_counter() - started) * 1000)
    print(f"[import] day={day} duration_ms={duration_ms}")
    return JSONResponse(
        {"status": "ok", "snapshot_id": snapshot_id, "duration_ms": duration_ms}
    )


@app.post("/api/reset")
def api_reset():
    reset_db()
    return JSONResponse({"status": "ok"})


@app.get("/api/report/{day}.pdf")
def api_report(day: str):
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    path = reports_dir / f"report_{day}.pdf"
    started = time.perf_counter()
    generate_report(day, str(path))
    duration_ms = int((time.perf_counter() - started) * 1000)
    print(f"[report] day={day} duration_ms={duration_ms}")
    response = FileResponse(path, media_type="application/pdf", filename=path.name)
    response.headers["X-Report-Gen-Ms"] = str(duration_ms)
    return response
