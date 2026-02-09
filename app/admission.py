from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from sqlalchemy import select

from .config import PROGRAMS
from .db import SessionLocal
from .models import ApplicationSnapshot, Program, Snapshot


@dataclass
class AdmissionResult:
    admitted: List[Tuple[int, int]]
    cutoff: int | None
    consent_count: int


def _get_latest_snapshot_id(db, day: str) -> int | None:
    stmt = (
        select(Snapshot)
        .where(Snapshot.day == day)
        .order_by(Snapshot.imported_at.desc())
        .limit(1)
    )
    snap = db.execute(stmt).scalars().first()
    return snap.id if snap else None


def compute_admission(day: str, db=None) -> Dict[str, AdmissionResult]:
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        snapshot_id = _get_latest_snapshot_id(db, day)
        if snapshot_id is None:
            return {code: AdmissionResult([], None, 0) for code in PROGRAMS}

        programs = {p.id: p for p in db.execute(select(Program)).scalars().all()}

        stmt = select(ApplicationSnapshot).where(
            ApplicationSnapshot.snapshot_id == snapshot_id,
            ApplicationSnapshot.consent == True,  # noqa: E712
        )
        apps = db.execute(stmt).scalars().all()

        # Build applicant preferences and scores
        prefs: Dict[int, List[Tuple[int, str]]] = {}
        scores: Dict[Tuple[int, str], int] = {}
        consent_count: Dict[str, int] = {code: 0 for code in PROGRAMS}

        program_code_by_id = {p.id: p.code for p in programs.values()}

        for app in apps:
            code = program_code_by_id[app.program_id]
            consent_count[code] += 1
            prefs.setdefault(app.applicant_id, []).append((app.priority, code))
            scores[(app.applicant_id, code)] = app.total

        # sort preferences by priority
        applicant_prefs: Dict[int, List[str]] = {}
        for aid, items in prefs.items():
            items.sort(key=lambda x: x[0])
            applicant_prefs[aid] = [code for _, code in items]

        capacities = {code: PROGRAMS[code]["seats"] for code in PROGRAMS}

        # Deferred acceptance with score-based ranking
        tentative: Dict[str, List[int]] = {code: [] for code in PROGRAMS}
        unassigned = set(applicant_prefs.keys())
        next_choice = {aid: 0 for aid in applicant_prefs}

        while True:
            proposals: Dict[str, List[int]] = {}
            progressed = False
            for aid in list(unassigned):
                idx = next_choice[aid]
                pref_list = applicant_prefs[aid]
                if idx >= len(pref_list):
                    unassigned.remove(aid)
                    continue
                program = pref_list[idx]
                proposals.setdefault(program, []).append(aid)
                next_choice[aid] += 1
                progressed = True

            if not progressed:
                break

            for program, new_applicants in proposals.items():
                candidates = tentative.get(program, []) + new_applicants
                candidates.sort(key=lambda a: (-scores[(a, program)], a))
                capacity = capacities[program]
                accepted = candidates[:capacity]
                tentative[program] = accepted

                rejected = set(candidates[capacity:])
                for aid in rejected:
                    unassigned.add(aid)
                for aid in accepted:
                    if aid in unassigned:
                        unassigned.remove(aid)

        results: Dict[str, AdmissionResult] = {}
        for code in PROGRAMS:
            accepted_ids = tentative.get(code, [])
            accepted_ids.sort(key=lambda a: (-scores[(a, code)], a))
            admitted = [(aid, scores[(aid, code)]) for aid in accepted_ids]
            if len(admitted) < PROGRAMS[code]["seats"]:
                cutoff = None
            else:
                cutoff = admitted[-1][1]
            results[code] = AdmissionResult(admitted, cutoff, consent_count.get(code, 0))

        return results
    finally:
        if close_db:
            db.close()