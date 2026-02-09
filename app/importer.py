from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List

from sqlalchemy import select

from .config import DAY_FOLDERS, DAYS, PROGRAMS
from .db import Base, SessionLocal, engine
from .models import Applicant, Application, ApplicationSnapshot, Program, Snapshot


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        existing = {p.code for p in db.execute(select(Program)).scalars().all()}
        for code, info in PROGRAMS.items():
            if code not in existing:
                db.add(Program(code=code, name=info["name"], seats=info["seats"]))
        db.commit()


def reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    init_db()


def _parse_consent(value: str) -> bool:
    v = value.strip().lower()
    return v in {"1", "true", "yes", "y"}


def _load_day_rows(day: str, data_dir: str = "data") -> List[Dict]:
    if day not in DAY_FOLDERS:
        raise ValueError(f"Unknown day: {day}")

    folder = Path(data_dir) / DAY_FOLDERS[day]
    rows: List[Dict] = []

    for code in PROGRAMS.keys():
        path = folder / f"{code}.csv"
        if not path.exists():
            raise FileNotFoundError(str(path))
        with path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                rows.append(
                    {
                        "program_code": code,
                        "applicant_id": int(r["applicant_id"]),
                        "consent": _parse_consent(r["consent"]),
                        "priority": int(r["priority"]),
                        "physics_ikt": int(r["physics_ikt"]),
                        "russian": int(r["russian"]),
                        "math": int(r["math"]),
                        "achievements": int(r["achievements"]),
                        "total": int(r["total"]),
                    }
                )
    return rows


def import_day(day: str, data_dir: str = "data") -> int:
    if day not in DAYS:
        raise ValueError(f"Unknown day: {day}")

    init_db()
    rows = _load_day_rows(day, data_dir)

    with SessionLocal() as db:
        program_map = {p.code: p for p in db.execute(select(Program)).scalars().all()}

        snapshot = Snapshot(day=day, imported_at=datetime.utcnow())
        db.add(snapshot)
        db.flush()

        applicant_ids = {r["applicant_id"] for r in rows}
        if applicant_ids:
            existing_ids = set(
                db.execute(select(Applicant.id).where(Applicant.id.in_(applicant_ids))).scalars().all()
            )
        else:
            existing_ids = set()

        new_applicants = [Applicant(id=aid) for aid in applicant_ids if aid not in existing_ids]
        if new_applicants:
            db.bulk_save_objects(new_applicants)
            db.flush()

        snapshot_rows = []
        for r in rows:
            program = program_map[r["program_code"]]
            snapshot_rows.append(
                ApplicationSnapshot(
                    snapshot_id=snapshot.id,
                    applicant_id=r["applicant_id"],
                    program_id=program.id,
                    consent=r["consent"],
                    priority=r["priority"],
                    physics_ikt=r["physics_ikt"],
                    russian=r["russian"],
                    math=r["math"],
                    achievements=r["achievements"],
                    total=r["total"],
                )
            )
        if snapshot_rows:
            db.bulk_save_objects(snapshot_rows)

        existing_apps = {
            (a.applicant_id, a.program_id): a
            for a in db.execute(select(Application)).scalars().all()
        }

        new_keys = set()
        for r in rows:
            program = program_map[r["program_code"]]
            key = (r["applicant_id"], program.id)
            new_keys.add(key)
            if key in existing_apps:
                app = existing_apps[key]
                app.consent = r["consent"]
                app.priority = r["priority"]
                app.physics_ikt = r["physics_ikt"]
                app.russian = r["russian"]
                app.math = r["math"]
                app.achievements = r["achievements"]
                app.total = r["total"]
                app.day = day
            else:
                db.add(
                    Application(
                        applicant_id=r["applicant_id"],
                        program_id=program.id,
                        consent=r["consent"],
                        priority=r["priority"],
                        physics_ikt=r["physics_ikt"],
                        russian=r["russian"],
                        math=r["math"],
                        achievements=r["achievements"],
                        total=r["total"],
                        day=day,
                    )
                )

        if existing_apps:
            to_delete = [
                app for key, app in existing_apps.items() if key not in new_keys
            ]
            for app in to_delete:
                db.delete(app)

        db.commit()
        return snapshot.id


def available_days(data_dir: str = "data") -> List[str]:
    days = []
    base = Path(data_dir)
    for day in DAYS:
        folder = base / DAY_FOLDERS[day]
        if folder.exists():
            days.append(day)
    return days