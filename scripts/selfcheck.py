from __future__ import annotations

import csv
import sys
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.admission import compute_admission
from app.config import DAYS, PROGRAMS
from app.importer import import_day, reset_db
from app.db import SessionLocal
from app.models import ApplicationSnapshot, Program, Snapshot
from app.report import generate_report
from scripts.generate_data import DAY_FOLDERS, DAY_SPECS, generate
from pypdf import PdfReader

DATA_DIR = ROOT / "data"
REPORT_DIR = ROOT / "reports"


def load_day_program(day: str, program: str):
    path = DATA_DIR / DAY_FOLDERS[day] / f"{program}.csv"
    rows = []
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)
    return rows


def check_files() -> None:
    expected = []
    for day in DAYS:
        folder = DATA_DIR / DAY_FOLDERS[day]
        for program in PROGRAMS:
            expected.append(folder / f"{program}.csv")
    missing = [str(p) for p in expected if not p.exists()]
    if missing:
        raise AssertionError(f"Missing files: {missing}")


def check_sizes() -> None:
    for day, spec in DAY_SPECS.items():
        for program, expected_size in spec["sizes"].items():
            rows = load_day_program(day, program)
            if len(rows) != expected_size:
                raise AssertionError(
                    f"Size mismatch {day} {program}: {len(rows)} != {expected_size}"
                )


def compute_sets(day: str):
    sets = {}
    for program in PROGRAMS:
        rows = load_day_program(day, program)
        sets[program] = {int(r["applicant_id"]) for r in rows}
    return sets


def check_intersections() -> None:
    for day, spec in DAY_SPECS.items():
        sets = compute_sets(day)
        # pairs
        for (a, b), expected in spec["pairs"].items():
            got = len(sets[a] & sets[b])
            if got != expected:
                raise AssertionError(f"Pair intersection {day} {a}-{b}: {got} != {expected}")
        # triples
        for (a, b, c), expected in spec["triples"].items():
            got = len(sets[a] & sets[b] & sets[c])
            if got != expected:
                raise AssertionError(
                    f"Triple intersection {day} {a}-{b}-{c}: {got} != {expected}"
                )
        # quad
        all_set = sets["PM"] & sets["IVT"] & sets["ITSS"] & sets["IB"]
        if len(all_set) != spec["quad"]:
            raise AssertionError(
                f"Quad intersection {day}: {len(all_set)} != {spec['quad']}"
            )


def check_updates() -> None:
    for prev_day, day in zip(DAYS[:-1], DAYS[1:]):
        prev_sets = compute_sets(prev_day)
        cur_sets = compute_sets(day)

        # Per program
        for program in PROGRAMS:
            prev_set = prev_sets[program]
            cur_set = cur_sets[program]
            removed = len(prev_set - cur_set)
            added = len(cur_set - prev_set)
            base = len(prev_set)
            removed_pct = removed / base
            added_pct = added / base
            if not (0.05 <= removed_pct <= 0.10):
                raise AssertionError(
                    f"Update removal {prev_day}->{day} {program}: {removed_pct:.2%}"
                )
            if not (added_pct >= 0.10):
                raise AssertionError(
                    f"Update addition {prev_day}->{day} {program}: {added_pct:.2%}"
                )

        # Global summary as average across programs
        removed_avg = 0.0
        added_avg = 0.0
        for program in PROGRAMS:
            prev_set = prev_sets[program]
            cur_set = cur_sets[program]
            removed_avg += len(prev_set - cur_set) / len(prev_set)
            added_avg += len(cur_set - prev_set) / len(prev_set)
        removed_avg /= len(PROGRAMS)
        added_avg /= len(PROGRAMS)
        if not (0.05 <= removed_avg <= 0.10):
            raise AssertionError(
                f"Global removal avg {prev_day}->{day}: {removed_avg:.2%}"
            )
        if not (added_avg >= 0.10):
            raise AssertionError(
                f"Global addition avg {prev_day}->{day}: {added_avg:.2%}"
            )


def check_cutoffs() -> None:
    reset_db()
    results = {}
    for day in DAYS:
        import_day(day, data_dir=str(DATA_DIR))
        results[day] = compute_admission(day)

    # Day 1: all NEDOBOR
    for code, res in results[DAYS[0]].items():
        if res.cutoff is not None:
            raise AssertionError(f"Expected NEDOBOR on {DAYS[0]} for {code}")

    # Day 2: all have cutoff
    for code, res in results[DAYS[1]].items():
        if res.cutoff is None:
            raise AssertionError(f"Expected cutoff on {DAYS[1]} for {code}")

    # Day 3 dynamics
    for code in ["PM", "IVT"]:
        if results[DAYS[2]][code].cutoff <= results[DAYS[1]][code].cutoff:
            raise AssertionError(f"Expected increase on {DAYS[2]} for {code}")
    for code in ["ITSS", "IB"]:
        if results[DAYS[2]][code].cutoff >= results[DAYS[1]][code].cutoff:
            raise AssertionError(f"Expected decrease on {DAYS[2]} for {code}")

    # Day 4 dynamics and ordering
    for code in PROGRAMS:
        if results[DAYS[3]][code].cutoff <= results[DAYS[2]][code].cutoff:
            raise AssertionError(f"Expected increase on {DAYS[3]} for {code}")

    order = ["PM", "IB", "IVT", "ITSS"]
    for a, b in zip(order, order[1:]):
        if results[DAYS[3]][a].cutoff <= results[DAYS[3]][b].cutoff:
            raise AssertionError(f"Ordering failed on {DAYS[3]}: {a} !> {b}")

    # Day 4 consent counts > seats
    for code, res in results[DAYS[3]].items():
        if res.consent_count <= PROGRAMS[code]["seats"]:
            raise AssertionError(f"Consent count too low on {DAYS[3]} for {code}")


def check_pdf() -> None:
    REPORT_DIR.mkdir(exist_ok=True)
    for day in DAYS:
        path = REPORT_DIR / f"report_{day}.pdf"
        generate_report(day, str(path))
        if not path.exists() or path.stat().st_size == 0:
            raise AssertionError(f"PDF not generated for {day}")
        data = path.read_bytes()
        # Simple heuristic: at least one page and an embedded image (chart)
        if b"/Type /Page" not in data:
            raise AssertionError(f"PDF missing page object for {day}")
        if b"/Subtype /Image" not in data:
            raise AssertionError(f"PDF missing image object for {day}")
        # Try to verify key sections via text extraction, fallback to marker bytes
        text = ""
        try:
            reader = PdfReader(str(path))
            text = "\n".join((page.extract_text() or "") for page in reader.pages)
        except Exception:
            text = ""
        tokens = ["Отчет о поступлении", "Проходные", "Списки зачисленных", "Статистика"]
        if text:
            missing = [t for t in tokens if t not in text]
            if missing:
                raise AssertionError(f"PDF missing sections for {day}: {missing}")
        else:
            marker = b"SECTION_MARKER: REPORT CUTOFFS ADMITTED STATISTICS"
            if marker not in data:
                raise AssertionError(f"PDF missing section marker for {day}")


def check_stats_nonzero() -> None:
    reset_db()
    for day in DAYS:
        import_day(day, data_dir=str(DATA_DIR))

        with SessionLocal() as db:
            snap = (
                db.execute(
                    select(Snapshot)
                    .where(Snapshot.day == day)
                    .order_by(Snapshot.imported_at.desc())
                )
                .scalars()
                .first()
            )
            apps = db.execute(
                select(ApplicationSnapshot).where(ApplicationSnapshot.snapshot_id == snap.id)
            ).scalars().all()

            programs = {p.id: p.code for p in db.execute(select(Program)).scalars().all()}
            stats = {
                code: {"total": 0, "priority": {1: 0, 2: 0, 3: 0, 4: 0}}
                for code in PROGRAMS
            }
            priority_lookup = {}
            for app in apps:
                code = programs[app.program_id]
                stats[code]["total"] += 1
                stats[code]["priority"][app.priority] += 1
                priority_lookup[(app.applicant_id, code)] = app.priority

            admission = compute_admission(day, db=db)
            admitted_priority = {code: {1: 0, 2: 0, 3: 0, 4: 0} for code in PROGRAMS}
            for code, res in admission.items():
                for aid, _total in res.admitted:
                    p = priority_lookup.get((aid, code))
                    if p is not None:
                        admitted_priority[code][p] += 1

            for code in PROGRAMS:
                if stats[code]["total"] == 0:
                    raise AssertionError(f"Zero total stats for {day} {code}")
                for p in (1, 2, 3, 4):
                    if stats[code]["priority"][p] == 0:
                        raise AssertionError(f"Zero priority stats for {day} {code} P{p}")
                    if admitted_priority[code][p] == 0:
                        raise AssertionError(
                            f"Zero admitted priority stats for {day} {code} AdmP{p}"
                        )


def main() -> None:
    generate(output_dir=str(DATA_DIR))

    checks = [
        ("Files present", check_files),
        ("Sizes", check_sizes),
        ("Intersections", check_intersections),
        ("Updates", check_updates),
        ("Cutoffs", check_cutoffs),
        ("Statistics non-zero", check_stats_nonzero),
        ("PDF", check_pdf),
    ]

    all_ok = True
    for name, fn in checks:
        try:
            fn()
            print(f"[OK] {name}")
        except Exception as exc:
            all_ok = False
            print(f"[FAIL] {name}: {exc}")

    if not all_ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
