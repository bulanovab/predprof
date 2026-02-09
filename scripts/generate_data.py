from __future__ import annotations

import csv
import math
import random
from pathlib import Path
from typing import Dict, List, Tuple

SEED = 20250801

PROGRAMS = ["PM", "IVT", "ITSS", "IB"]
PROGRAM_BITS = {"PM": 1, "IVT": 2, "ITSS": 4, "IB": 8}
BITS_PROGRAM = {v: k for k, v in PROGRAM_BITS.items()}
PROGRAM_ORDER = ["PM", "IVT", "ITSS", "IB"]

DAYS = [
    "2025-08-01",
    "2025-08-02",
    "2025-08-03",
    "2025-08-04",
]
DAY_FOLDERS = {
    "2025-08-01": "day_01",
    "2025-08-02": "day_02",
    "2025-08-03": "day_03",
    "2025-08-04": "day_04",
}

DAY_SPECS = {
    "2025-08-01": {
        "sizes": {"PM": 60, "IVT": 100, "ITSS": 50, "IB": 70},
        "pairs": {
            ("PM", "IVT"): 22,
            ("PM", "ITSS"): 17,
            ("PM", "IB"): 20,
            ("IVT", "ITSS"): 19,
            ("IVT", "IB"): 22,
            ("ITSS", "IB"): 17,
        },
        "triples": {
            ("PM", "IVT", "ITSS"): 5,
            ("PM", "IVT", "IB"): 5,
            ("IVT", "ITSS", "IB"): 5,
            ("PM", "ITSS", "IB"): 5,
        },
        "quad": 3,
    },
    "2025-08-02": {
        "sizes": {"PM": 380, "IVT": 370, "ITSS": 350, "IB": 260},
        "pairs": {
            ("PM", "IVT"): 190,
            ("PM", "ITSS"): 190,
            ("PM", "IB"): 150,
            ("IVT", "ITSS"): 190,
            ("IVT", "IB"): 140,
            ("ITSS", "IB"): 120,
        },
        "triples": {
            ("PM", "IVT", "ITSS"): 70,
            ("PM", "IVT", "IB"): 70,
            ("IVT", "ITSS", "IB"): 70,
            ("PM", "ITSS", "IB"): 70,
        },
        "quad": 50,
    },
    "2025-08-03": {
        "sizes": {"PM": 1000, "IVT": 1150, "ITSS": 1050, "IB": 800},
        "pairs": {
            ("PM", "IVT"): 760,
            ("PM", "ITSS"): 600,
            ("PM", "IB"): 410,
            ("IVT", "ITSS"): 750,
            ("IVT", "IB"): 460,
            ("ITSS", "IB"): 500,
        },
        "triples": {
            ("PM", "IVT", "ITSS"): 500,
            ("PM", "IVT", "IB"): 260,
            ("IVT", "ITSS", "IB"): 300,
            ("PM", "ITSS", "IB"): 250,
        },
        "quad": 200,
    },
    "2025-08-04": {
        "sizes": {"PM": 1240, "IVT": 1390, "ITSS": 1240, "IB": 1190},
        "pairs": {
            ("PM", "IVT"): 1090,
            ("PM", "ITSS"): 1110,
            ("PM", "IB"): 1070,
            ("IVT", "ITSS"): 1050,
            ("IVT", "IB"): 1040,
            ("ITSS", "IB"): 1090,
        },
        "triples": {
            ("PM", "IVT", "ITSS"): 1020,
            ("PM", "IVT", "IB"): 1020,
            ("IVT", "ITSS", "IB"): 1000,
            ("PM", "ITSS", "IB"): 1040,
        },
        "quad": 1000,
    },
}

TARGET_CUTOFFS = {
    "2025-08-01": {"PM": 200, "IVT": 195, "ITSS": 190, "IB": 195},
    "2025-08-02": {"PM": 235, "IVT": 230, "ITSS": 210, "IB": 220},
    "2025-08-03": {"PM": 245, "IVT": 240, "ITSS": 200, "IB": 210},
    "2025-08-04": {"PM": 255, "IVT": 245, "ITSS": 235, "IB": 250},
}

CONSENT_TARGETS = {
    "2025-08-01": {"PM": 20, "IVT": 25, "ITSS": 15, "IB": 10},
    "2025-08-02": {"PM": 60, "IVT": 70, "ITSS": 45, "IB": 30},
    "2025-08-03": {"PM": 70, "IVT": 80, "ITSS": 50, "IB": 35},
    "2025-08-04": {"PM": 90, "IVT": 110, "ITSS": 70, "IB": 80},
}


def popcount(x: int) -> int:
    return bin(x).count("1")


def compute_region_counts(spec: Dict) -> Dict[int, int]:
    A, B, C, D = "PM", "IVT", "ITSS", "IB"
    sizes = spec["sizes"]
    pairs = spec["pairs"]
    triples = spec["triples"]
    Q = spec["quad"]

    E_ABC = triples[(A, B, C)] - Q
    E_ABD = triples[(A, B, D)] - Q
    E_ACD = triples[(A, C, D)] - Q
    E_BCD = triples[(B, C, D)] - Q

    E_AB = pairs[(A, B)] - triples[(A, B, C)] - triples[(A, B, D)] + Q
    E_AC = pairs[(A, C)] - triples[(A, B, C)] - triples[(A, C, D)] + Q
    E_AD = pairs[(A, D)] - triples[(A, B, D)] - triples[(A, C, D)] + Q
    E_BC = pairs[(B, C)] - triples[(A, B, C)] - triples[(B, C, D)] + Q
    E_BD = pairs[(B, D)] - triples[(A, B, D)] - triples[(B, C, D)] + Q
    E_CD = pairs[(C, D)] - triples[(A, C, D)] - triples[(B, C, D)] + Q

    E_A = sizes[A] - (E_AB + E_AC + E_AD) - (E_ABC + E_ABD + E_ACD) - Q
    E_B = sizes[B] - (E_AB + E_BC + E_BD) - (E_ABC + E_ABD + E_BCD) - Q
    E_C = sizes[C] - (E_AC + E_BC + E_CD) - (E_ABC + E_ACD + E_BCD) - Q
    E_D = sizes[D] - (E_AD + E_BD + E_CD) - (E_ABD + E_ACD + E_BCD) - Q

    counts = {
        1: E_A,
        2: E_B,
        4: E_C,
        8: E_D,
        3: E_AB,
        5: E_AC,
        9: E_AD,
        6: E_BC,
        10: E_BD,
        12: E_CD,
        7: E_ABC,
        11: E_ABD,
        13: E_ACD,
        14: E_BCD,
        15: Q,
    }
    return counts


def assign_new_day(
    prev_assignments: Dict[int, int],
    target_counts: Dict[int, int],
    next_id: int,
    seed_base: int,
) -> Tuple[Dict[int, int], int]:
    bits = [1, 2, 4, 8]
    prev_ids = list(prev_assignments.keys())
    prev_ids.sort()

    sizes = {b: 0 for b in bits}
    for mask in prev_assignments.values():
        for b in bits:
            if mask & b:
                sizes[b] += 1

    min_remove = {b: math.ceil(0.05 * sizes[b]) for b in bits}
    max_remove = {b: math.floor(0.10 * sizes[b]) for b in bits}
    total_slots = sum(target_counts.values())
    new_count = total_slots - len(prev_ids)
    if new_count < 0:
        raise RuntimeError("Target slots less than previous applicants")

    for attempt in range(25):
        rng = random.Random(seed_base + attempt)

        # Build applicants list (prev + new)
        new_ids = list(range(next_id, next_id + new_count))
        app_ids = prev_ids + new_ids
        app_prev_mask = [prev_assignments[aid] for aid in prev_ids] + [0] * new_count

        slots: List[int] = []
        for mask, count in target_counts.items():
            slots.extend([mask] * count)

        # Initial assignment: sort by popcount
        app_order = sorted(
            range(len(app_ids)),
            key=lambda i: (-popcount(app_prev_mask[i]), app_ids[i]),
        )
        slot_order = sorted(range(len(slots)), key=lambda i: -popcount(slots[i]))
        slot_to_app = [0] * len(slots)
        app_to_slot = [0] * len(app_ids)
        for app_idx, slot_idx in zip(app_order, slot_order):
            slot_to_app[slot_idx] = app_idx
            app_to_slot[app_idx] = slot_idx

        removed = {b: 0 for b in bits}
        for slot_idx, app_idx in enumerate(slot_to_app):
            prev_mask = app_prev_mask[app_idx]
            slot_mask = slots[slot_idx]
            for b in bits:
                if prev_mask & b and not (slot_mask & b):
                    removed[b] += 1

        def penalty(rem: Dict[int, int]) -> int:
            return sum(
                max(0, min_remove[b] - rem[b]) + max(0, rem[b] - max_remove[b]) for b in bits
            )

        pen = penalty(removed)
        if pen == 0:
            if any(removed[b] < min_remove[b] or removed[b] > max_remove[b] for b in bits):
                continue
            assignments = {app_ids[slot_to_app[i]]: slots[i] for i in range(len(slots))}
            return assignments, next_id + new_count

        slots_with = {b: [i for i, m in enumerate(slots) if m & b] for b in bits}
        slots_without = {b: [i for i, m in enumerate(slots) if not (m & b)] for b in bits}

        max_iters = 30000
        for _ in range(max_iters):
            if pen == 0:
                break

            # choose program with largest violation
            def violation(b: int) -> int:
                if removed[b] < min_remove[b]:
                    return min_remove[b] - removed[b]
                if removed[b] > max_remove[b]:
                    return removed[b] - max_remove[b]
                return 0

            b = max(bits, key=violation)
            if violation(b) == 0:
                break

            need_more = removed[b] < min_remove[b]
            candidates_a = slots_with[b] if need_more else slots_without[b]
            candidates_b = slots_without[b] if need_more else slots_with[b]

            best_swap = None
            best_pen = pen

            for _t in range(60):
                sa = rng.choice(candidates_a)
                sb = rng.choice(candidates_b)
                if sa == sb:
                    continue
                app_a = slot_to_app[sa]
                app_b = slot_to_app[sb]
                prev_a = app_prev_mask[app_a]
                prev_b = app_prev_mask[app_b]
                # Ensure swap can influence program b
                if need_more and not (prev_a & b):
                    continue
                if not need_more and not (prev_a & b):
                    continue

                # compute new removed counts
                new_removed = removed.copy()
                for bit in bits:
                    old = 0
                    new = 0
                    if prev_a & bit and not (slots[sa] & bit):
                        old += 1
                    if prev_b & bit and not (slots[sb] & bit):
                        old += 1
                    if prev_a & bit and not (slots[sb] & bit):
                        new += 1
                    if prev_b & bit and not (slots[sa] & bit):
                        new += 1
                    new_removed[bit] = new_removed[bit] - old + new

                new_pen = penalty(new_removed)
                if new_pen < best_pen:
                    best_pen = new_pen
                    best_swap = (sa, sb, new_removed)
                    if best_pen == 0:
                        break

            if best_swap is None:
                # random swap to escape
                sa = rng.randrange(len(slots))
                sb = rng.randrange(len(slots))
                if sa != sb:
                    app_a = slot_to_app[sa]
                    app_b = slot_to_app[sb]
                    new_removed = removed.copy()
                    for bit in bits:
                        old = 0
                        new = 0
                        if app_prev_mask[app_a] & bit and not (slots[sa] & bit):
                            old += 1
                        if app_prev_mask[app_b] & bit and not (slots[sb] & bit):
                            old += 1
                        if app_prev_mask[app_a] & bit and not (slots[sb] & bit):
                            new += 1
                        if app_prev_mask[app_b] & bit and not (slots[sa] & bit):
                            new += 1
                        new_removed[bit] = new_removed[bit] - old + new
                    slot_to_app[sa], slot_to_app[sb] = app_b, app_a
                    removed = new_removed
                    pen = penalty(removed)
            else:
                sa, sb, new_removed = best_swap
                app_a = slot_to_app[sa]
                app_b = slot_to_app[sb]
                slot_to_app[sa], slot_to_app[sb] = app_b, app_a
                removed = new_removed
                pen = best_pen

        if pen == 0:
            if any(removed[b] < min_remove[b] or removed[b] > max_remove[b] for b in bits):
                continue
            assignments = {app_ids[slot_to_app[i]]: slots[i] for i in range(len(slots))}
            return assignments, next_id + new_count

    raise RuntimeError("Failed to assign applicants within constraints")


def assign_consents(
    applicant_programs: Dict[int, List[str]],
    day: str,
) -> Tuple[Dict[int, str], Dict[Tuple[int, str], int], Dict[str, List[int]]]:
    targets = CONSENT_TARGETS[day]
    remaining = targets.copy()
    consent_of: Dict[int, str] = {}
    forced_priorities: Dict[Tuple[int, str], int] = {}
    forced_top: Dict[str, List[int]] = {p: [] for p in PROGRAMS}

    degrees = {aid: len(progs) for aid, progs in applicant_programs.items()}
    candidates_by_program = {
        p: sorted([aid for aid, progs in applicant_programs.items() if p in progs])
        for p in PROGRAMS
    }

    assigned = set()

    # Ensure each program gets applicants with higher degree for priority mix (2/3/4)
    for program in PROGRAM_ORDER:
        for desired in (4, 3, 2):
            if remaining[program] <= 0:
                continue
            candidate = None
            for aid in candidates_by_program[program]:
                if aid in assigned:
                    continue
                if degrees[aid] >= desired:
                    candidate = aid
                    break
            if candidate is None:
                for aid in candidates_by_program[program]:
                    if aid in assigned:
                        continue
                    candidate = aid
                    break
            if candidate is not None:
                consent_of[candidate] = program
                assigned.add(candidate)
                remaining[program] -= 1
                forced_priorities[(candidate, program)] = desired
                forced_top[program].append(candidate)

    rng = random.Random(SEED + DAYS.index(day) * 1000 + 77)
    ids = sorted(applicant_programs.keys())
    rng.shuffle(ids)

    for aid in ids:
        if aid in assigned:
            continue
        choices = [p for p in applicant_programs[aid] if remaining[p] > 0]
        if not choices:
            continue
        choices.sort(key=lambda p: (-remaining[p], PROGRAM_ORDER.index(p)))
        chosen = choices[0]
        consent_of[aid] = chosen
        assigned.add(aid)
        remaining[chosen] -= 1
        if all(v == 0 for v in remaining.values()):
            break

    if any(v > 0 for v in remaining.values()):
        raise RuntimeError(f"Not enough applicants to assign consent for {day}: {remaining}")

    return consent_of, forced_priorities, forced_top


def assign_priorities(
    applicant_programs: Dict[int, List[str]],
    consent_of: Dict[int, str],
    day: str,
    priority_overrides: Dict[Tuple[int, str], int] | None = None,
) -> Dict[Tuple[int, str], int]:
    priorities: Dict[Tuple[int, str], int] = {}
    day_idx = DAYS.index(day)
    overrides = priority_overrides or {}

    for aid, programs in applicant_programs.items():
        programs = list(programs)
        rng = random.Random(SEED + day_idx * 100000 + aid)
        if aid in consent_of:
            consent_program = consent_of[aid]
            remaining = [p for p in programs if p != consent_program]
            rng.shuffle(remaining)
            desired = overrides.get((aid, consent_program))
            if desired is not None and 1 <= desired <= len(programs):
                pos = desired - 1
                ordered = remaining[:pos] + [consent_program] + remaining[pos:]
            else:
                ordered = [consent_program] + remaining
        else:
            rng.shuffle(programs)
            ordered = programs
        for i, p in enumerate(ordered, start=1):
            priorities[(aid, p)] = i
        if aid in consent_of and (aid, consent_of[aid]) in overrides:
            desired = overrides[(aid, consent_of[aid])]
            if 1 <= desired <= 4:
                priorities[(aid, consent_of[aid])] = desired
    return priorities


def split_total(total: int, rng: random.Random) -> Tuple[int, int, int, int]:
    achievements = total % 11
    rem = total - achievements
    extra = rem - 150
    extras = [0, 0, 0]
    for i in range(3):
        max_add = min(50, extra)
        add = rng.randint(0, max_add) if max_add > 0 else 0
        extras[i] = add
        extra -= add
    i = 0
    while extra > 0:
        if extras[i] < 50:
            extras[i] += 1
            extra -= 1
        i = (i + 1) % 3
    physics = 50 + extras[0]
    russian = 50 + extras[1]
    math = 50 + extras[2]
    return physics, russian, math, achievements


def total_for_rank(rank: int, seats: int, cutoff: int, min_total: int = 160) -> int:
    if rank <= seats:
        return cutoff + (seats - rank)
    return max(cutoff - 1 - (rank - seats - 1), min_total)


def generate_day_csvs(day: str, assignments: Dict[int, int], output_dir: str) -> None:
    folder = Path(output_dir) / DAY_FOLDERS[day]
    folder.mkdir(parents=True, exist_ok=True)

    program_applicants: Dict[str, List[int]] = {p: [] for p in PROGRAMS}
    applicant_programs: Dict[int, List[str]] = {}

    for aid, mask in assignments.items():
        programs = []
        for p, bit in PROGRAM_BITS.items():
            if mask & bit:
                programs.append(p)
                program_applicants[p].append(aid)
        applicant_programs[aid] = programs

    consent_of, forced_priorities, forced_top = assign_consents(applicant_programs, day)
    priorities = assign_priorities(
        applicant_programs, consent_of, day, priority_overrides=forced_priorities
    )

    day_idx = DAYS.index(day)

    for program in PROGRAMS:
        seats = {"PM": 40, "IVT": 50, "ITSS": 30, "IB": 20}[program]
        cutoff = TARGET_CUTOFFS[day][program]
        applicants = sorted(program_applicants[program])
        consented = [aid for aid in applicants if consent_of.get(aid) == program]
        non_consented = [aid for aid in applicants if consent_of.get(aid) != program]
        consented.sort()
        forced = sorted(forced_top.get(program, []))
        if forced:
            forced_set = set(forced)
            consented = forced + [aid for aid in consented if aid not in forced_set]
        non_consented.sort()
        ranked = consented + non_consented

        scores_by_applicant: Dict[int, Tuple[int, int, int, int, int]] = {}
        for idx, aid in enumerate(ranked, start=1):
            total = total_for_rank(idx, seats, cutoff)
            rng = random.Random(SEED + day_idx * 100000 + PROGRAM_ORDER.index(program) * 1000 + aid)
            physics, russian, math, achievements = split_total(total, rng)
            scores_by_applicant[aid] = (physics, russian, math, achievements, total)

        path = folder / f"{program}.csv"
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "applicant_id",
                    "consent",
                    "priority",
                    "physics_ikt",
                    "russian",
                    "math",
                    "achievements",
                    "total",
                ]
            )
            for aid in applicants:
                physics, russian, math, achievements, total = scores_by_applicant[aid]
                consent = 1 if consent_of.get(aid) == program else 0
                priority = priorities[(aid, program)]
                writer.writerow(
                    [aid, consent, priority, physics, russian, math, achievements, total]
                )


def generate(output_dir: str = "data") -> None:
    day_regions = {day: compute_region_counts(spec) for day, spec in DAY_SPECS.items()}

    assignments_by_day: Dict[str, Dict[int, int]] = {}
    next_id = 100000

    # Day 1
    day1 = DAYS[0]
    assignments: Dict[int, int] = {}
    for mask, count in sorted(day_regions[day1].items()):
        for _ in range(count):
            assignments[next_id] = mask
            next_id += 1
    assignments_by_day[day1] = assignments

    # Subsequent days
    for day in DAYS[1:]:
        prev_day = DAYS[DAYS.index(day) - 1]
        prev_assignments = assignments_by_day[prev_day]
        seed_base = SEED + DAYS.index(day) * 10000 + 123
        assignments, next_id = assign_new_day(
            prev_assignments, day_regions[day], next_id, seed_base
        )
        assignments_by_day[day] = assignments

    for day, assignments in assignments_by_day.items():
        generate_day_csvs(day, assignments, output_dir)


def main() -> None:
    generate()
    print("Data generated in ./data")


if __name__ == "__main__":
    main()
