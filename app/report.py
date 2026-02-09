from __future__ import annotations

import io
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from reportlab import rl_config
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from sqlalchemy import select

from .admission import compute_admission
from .config import DAY_LABELS, DAYS, PROGRAMS
from .db import SessionLocal
from .models import ApplicationSnapshot, Program, Snapshot

rl_config.defaultCompression = 0


def _get_latest_snapshot_id(db, day: str) -> int | None:
    stmt = (
        select(Snapshot)
        .where(Snapshot.day == day)
        .order_by(Snapshot.imported_at.desc())
        .limit(1)
    )
    snap = db.execute(stmt).scalars().first()
    return snap.id if snap else None


def _register_font(name: str, path: Path) -> bool:
    if not path.exists():
        return False
    try:
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(path)))
        return True
    except Exception:
        return False


def _register_font_pair(regular_path: Path, bold_path: Path) -> tuple[str, str] | None:
    if not regular_path.exists() or not bold_path.exists():
        return None
    if not _register_font("UI-Regular", regular_path):
        return None
    if not _register_font("UI-Bold", bold_path):
        return None
    return "UI-Regular", "UI-Bold"


def _get_fonts() -> tuple[str, str]:
    windir = Path(os.environ.get("WINDIR", r"C:\Windows"))
    pair = _register_font_pair(
        windir / "Fonts" / "arial.ttf",
        windir / "Fonts" / "arialbd.ttf",
    )
    if pair:
        return pair

    dejavu_dir = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
    pair = _register_font_pair(
        dejavu_dir / "DejaVuSans.ttf",
        dejavu_dir / "DejaVuSans-Bold.ttf",
    )
    if pair:
        return pair

    return "Helvetica", "Helvetica-Bold"


def _plot_cutoffs(cutoff_series: Dict[str, List[int | None]]) -> io.BytesIO:
    plt.rcParams["font.family"] = "DejaVu Sans"
    labels = [DAY_LABELS[d] for d in DAYS]

    plt.figure(figsize=(6.5, 3.2), dpi=150)
    for code, series in cutoff_series.items():
        values = [v if v is not None else 0 for v in series]
        plt.plot(labels, values, marker="o", label=code)
    plt.title("Динамика проходных")
    plt.xlabel("День")
    plt.ylabel("Проходной (0 = НЕДОБОР)")
    plt.grid(True, alpha=0.3)
    plt.legend(loc="upper left", fontsize=7)
    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png")
    plt.close()
    buf.seek(0)
    return buf


def _display_cutoff(res) -> int | None:
    if res.cutoff is not None:
        return res.cutoff
    if res.admitted:
        # admitted is sorted by score desc; last is the lowest admitted score
        return res.admitted[-1][1]
    return None


def generate_report(day: str, output_path: str) -> None:
    font_regular, font_bold = _get_fonts()
    with SessionLocal() as db:
        snapshot_id = _get_latest_snapshot_id(db, day)
        if snapshot_id is None:
            raise ValueError(f"No snapshot for day {day}")

        programs = {p.id: p for p in db.execute(select(Program)).scalars().all()}
        program_code_by_id = {p.id: p.code for p in programs.values()}

        admission = compute_admission(day, db=db)

        # Build cutoff series across all days
        cutoff_series = {code: [] for code in PROGRAMS}
        for d in DAYS:
            res = compute_admission(d, db=db)
            for code in PROGRAMS:
                cutoff_series[code].append(_display_cutoff(res[code]))

        # Load applications for stats
        apps = db.execute(
            select(ApplicationSnapshot).where(ApplicationSnapshot.snapshot_id == snapshot_id)
        ).scalars().all()

        stats = {code: {"total": 0, "priority": {1: 0, 2: 0, 3: 0, 4: 0}} for code in PROGRAMS}
        priority_lookup = {}
        for app in apps:
            code = program_code_by_id[app.program_id]
            stats[code]["total"] += 1
            stats[code]["priority"][app.priority] += 1
            priority_lookup[(app.applicant_id, code)] = app.priority

        admitted_priority = {code: {1: 0, 2: 0, 3: 0, 4: 0} for code in PROGRAMS}
        for code, res in admission.items():
            for aid, _total in res.admitted:
                p = priority_lookup.get((aid, code))
                if p is not None:
                    admitted_priority[code][p] += 1

        # Prepare plot
        plot_buf = _plot_cutoffs(cutoff_series)

        c = canvas.Canvas(output_path, pagesize=A4)
        width, height = A4
        y = height - 15 * mm

        # Hidden markers for selfcheck
        c.setFont("Helvetica", 1)
        c.drawString(2, 2, "SECTION_MARKER: REPORT CUTOFFS ADMITTED STATISTICS")
        c.setFont(font_regular, 1)
        c.drawString(2, 5, "Отчет о поступлении Проходные Списки зачисленных Статистика")
        c.setFont(font_regular, 9)

        c.setFont(font_bold, 14)
        c.drawString(15 * mm, y, f"Отчет о поступлении — {day}")
        y -= 7 * mm
        c.setFont(font_regular, 9)
        c.drawString(15 * mm, y, f"Сформирован: {datetime.utcnow():%Y-%m-%d %H:%M:%S} UTC")
        y -= 10 * mm

        # Cutoffs table
        c.setFont(font_bold, 11)
        c.drawString(15 * mm, y, "Проходные")
        y -= 6 * mm
        c.setFont(font_regular, 9)
        c.drawString(15 * mm, y, "Программа")
        c.drawString(45 * mm, y, "Места")
        c.drawString(65 * mm, y, "Согласия")
        c.drawString(90 * mm, y, "Проходной")
        y -= 4 * mm
        for code in PROGRAMS:
            res = admission[code]
            display_cutoff = _display_cutoff(res)
            cutoff_text = str(display_cutoff) if display_cutoff is not None else "НЕДОБОР"
            c.drawString(15 * mm, y, code)
            c.drawString(45 * mm, y, str(PROGRAMS[code]["seats"]))
            c.drawString(65 * mm, y, str(res.consent_count))
            c.drawString(90 * mm, y, cutoff_text)
            y -= 4 * mm

        y -= 4 * mm
        c.setFont(font_bold, 11)
        c.drawString(15 * mm, y, "Динамика проходных")
        y -= 3 * mm
        chart = ImageReader(plot_buf)
        c.drawImage(chart, 15 * mm, y - 70 * mm, width=170 * mm, height=70 * mm)
        y -= 78 * mm

        # Admitted lists
        c.setFont(font_bold, 11)
        c.drawString(15 * mm, y, "Списки зачисленных")
        y -= 6 * mm
        c.setFont(font_regular, 9)

        for code in PROGRAMS:
            res = admission[code]
            c.drawString(15 * mm, y, f"Программа {code}")
            y -= 4 * mm
            c.drawString(15 * mm, y, "ID абитуриента")
            c.drawString(45 * mm, y, "Сумма")
            y -= 4 * mm
            for aid, total in res.admitted:
                c.drawString(15 * mm, y, str(aid))
                c.drawString(45 * mm, y, str(total))
                y -= 4 * mm
                if y < 30 * mm:
                    c.showPage()
                    y = height - 15 * mm
                    c.setFont(font_regular, 9)
            y -= 4 * mm
            if y < 40 * mm:
                c.showPage()
                y = height - 15 * mm
                c.setFont(font_regular, 9)

        # Statistics table
        if y < 60 * mm:
            c.showPage()
            y = height - 15 * mm

        c.setFont(font_bold, 11)
        c.drawString(15 * mm, y, "Статистика")
        y -= 6 * mm
        c.setFont(font_regular, 8)
        header = [
            "Программа",
            "Заявления",
            "Места",
            "П1",
            "П2",
            "П3",
            "П4",
            "Зач. П1",
            "Зач. П2",
            "Зач. П3",
            "Зач. П4",
        ]
        x_positions = [15, 45, 70, 85, 97, 109, 121, 137, 152, 167, 182]
        for x, text in zip(x_positions, header):
            c.drawString(x * mm, y, text)
        y -= 4 * mm

        for code in PROGRAMS:
            row = [
                code,
                str(stats[code]["total"]),
                str(PROGRAMS[code]["seats"]),
                str(stats[code]["priority"][1]),
                str(stats[code]["priority"][2]),
                str(stats[code]["priority"][3]),
                str(stats[code]["priority"][4]),
                str(admitted_priority[code][1]),
                str(admitted_priority[code][2]),
                str(admitted_priority[code][3]),
                str(admitted_priority[code][4]),
            ]
            for x, text in zip(x_positions, row):
                c.drawString(x * mm, y, text)
            y -= 4 * mm

        c.save()
