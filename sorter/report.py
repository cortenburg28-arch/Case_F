"""Turn an assignment into the master spreadsheet, rosters and summary."""
from collections import Counter, defaultdict
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

ORDINAL = ["1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th"]


def rationale(cfg, scorer, s, pid, running_ids, other_slots=()):
    """One line a human can read and check."""
    p = scorer.by_id[pid]
    bits = []
    if pid in s.choices:
        if cfg["columns"].get("choices_ranked", True):
            bits.append(f"{ORDINAL[min(s.choices.index(pid), 7)]} choice")
        else:
            bits.append("picked it")
    else:
        gone = [scorer.by_id[c].name for c in s.choices if c not in running_ids]
        blocked = [scorer.by_id[c].name for c in s.choices if scorer.blocked(s, c)]
        if not s.choices:
            bits.append("named no projects in their track")
        else:
            bits.append("none of their picks")
            why = []
            if gone:
                why.append(f"not running: {', '.join(gone)}")
            if blocked:
                why.append(f"done last year: {', '.join(blocked)}")
            used = [scorer.by_id[c].name for c in s.choices if c in other_slots]
            if used:
                why.append(f"already placed in {', '.join(used)}")
            if len(why) < 1:
                why.append("picks were full with higher-priority students")
            bits[-1] += f" ({'; '.join(why)})"
    t = sorted(set(s.types) & p.types)
    g = sorted(set(s.sdgs) & p.sdgs)
    if t:
        bits.append(f"matches {'/'.join(t)}")
    if g:
        bits.append(f"SDG {', '.join(map(str, g))}")
    if not t and not g and pid not in s.choices:
        bits.append("placed where there was room")
    if s.last_year == pid and s.last_year_leader:
        bits.append("repeat allowed (leader last year)")
    return "; ".join(bits)


TRACK_PREFIX = {"major": "MAJ-", "minor": "MIN-"}


def build(cfg, asg, dem, notes, scorer, projects, students, excluded, problems):
    """Everything goes into one Excel file, laid out like last year's roster
    document: project overview, student list, one sheet per project, then the
    sheets that explain the result."""
    out = Path(cfg["_base"]) / cfg["inputs"]["output_dir"]
    out.mkdir(parents=True, exist_ok=True)
    running_ids = set(asg.running)
    gorder = {g: v["order"] for g, v in cfg["grades"].items()}
    ranked = cfg["columns"].get("choices_ranked", True)
    size = cfg["size"]

    per_student = defaultdict(list)
    for i, (s, slot) in enumerate(asg.units):
        per_student[s.id].append(asg.where[i])

    def faculty(p):
        return ", ".join(p.faculty)

    # --- Students: the roster list, plus why ------------------------------
    details, student_rows = [], []
    for s in sorted(students, key=lambda s: (gorder[s.grade], s.name.lower())):
        gids = per_student[s.id]
        pids = [asg.groups[g].project.id if g else None for g in gids]
        names = [TRACK_PREFIX[s.track] + scorer.by_id[p].name if p else "UNASSIGNED"
                 for p in pids]
        if s.track == "major":                  # majors fill both columns, as last year
            names, pids = names * 2, pids * 2
        ranks = []
        for p in pids[:len(gids)]:
            if p not in s.choices:
                ranks.append("not picked")
            else:
                ranks.append(str(s.choices.index(p) + 1) if ranked else "picked")
        why = " | ".join(rationale(cfg, scorer, s, p, running_ids,
                                   [q for q in pids if q != p]) if p else "no room"
                         for p in pids[:len(gids)])
        if s.single_pick:
            why += " | named only one project, so not prioritized"
        if s.warnings:
            why += " | note: " + "; ".join(s.warnings)
        student_rows.append((s.grade, [
            s.name, names[0], faculty(scorer.by_id[pids[0]]) if pids[0] else "",
            names[1], faculty(scorer.by_id[pids[1]]) if pids[1] else "", why]))
        details.append({
            "Grade": s.grade.capitalize(), "Name": s.name, "Gender": s.gender,
            "Track": s.track.capitalize(),
            "Project": " + ".join(scorer.by_id[p].name for p in pids[:len(gids)] if p),
            "Choice": ", ".join(ranks),
            "Picks": ", ".join(scorer.by_id[c].name for c in s.choices),
            "Last year": scorer.by_id[s.last_year].name if s.last_year in scorer.by_id
            else s.last_year,
            "Rationale": why, "Comments / friends": s.comments,
            "Celebration of Learning": s.celebration,
        })

    # --- per project ------------------------------------------------------
    summary, rosters = [], []
    by_project = defaultdict(list)
    for g in asg.groups.values():
        by_project[g.project.id].append(g)
    ordered = sorted(asg.running.values(), key=lambda p: (p.track, p.name.lower()))
    for p in ordered:
        groups = sorted(by_project[p.id], key=lambda g: g.week or 0)
        blocks = []
        for g in groups:
            mem = sorted(asg.members[g.id], key=lambda i: (gorder[asg.units[i][0].grade],
                                                         asg.units[i][0].name.lower()))
            blocks.append((g, [asg.units[i][0] for i in mem]))
            sts = [asg.units[i][0] for i in mem]
            gen = Counter(x.gender for x in sts)
            gr = Counter(x.grade for x in sts)
            flags = []
            if len(sts) < size["min"]:
                flags.append("under minimum (must-run)")
            elif len(sts) > size["hard_max"]:
                flags.append("ABOVE HARD MAXIMUM")
            elif len(sts) > size["target_max"]:
                flags.append("above target size")
            if gen.get("M") and gen.get("F") and min(gen["M"], gen["F"]) < 3:
                flags.append("gender rule not met")
            summary.append({
                "Project": TRACK_PREFIX[p.track] + p.name,
                "Week": f"week {g.week}" if g.week else "both",
                "Must run": "yes" if p.must_run else "", "Students": len(sts),
                "M": gen.get("M", 0), "F": gen.get("F", 0),
                "Seniors": gr.get("senior", 0), "Juniors": gr.get("junior", 0),
                "Sophomores": gr.get("sophomore", 0),
                "Picked it": sum(1 for x in sts if p.id in x.choices),
                "Demand score": round(dem[p.id], 1), "Flags": ", ".join(flags),
            })
        rosters.append((p, blocks))

    overview = []
    for k, p in enumerate(ordered, 1):
        sizes = " / ".join(str(len(asg.members[g.id]))
                           for g in sorted(by_project[p.id], key=lambda g: g.week or 0))
        overview.append([k, TRACK_PREFIX[p.track] + p.name, p.location,
                         *(p.faculty + ["", "", ""])[:3], sizes])

    not_run = [{"Project": TRACK_PREFIX[p.track] + p.name,
                "Demand score": round(dem[p.id], 1)}
               for p in sorted(projects, key=lambda p: -dem[p.id]) if p.id not in running_ids]

    # Satisfaction per grade, counted per assignment unit.
    stats = []
    for grade in sorted(cfg["grades"], key=lambda g: gorder[g]):
        units = [(s, asg.project_of(i)) for i, (s, _) in enumerate(asg.units)
                 if s.grade == grade]
        n = len(units)
        if not n:
            continue
        if ranked:
            counts = {
                "1st choice": sum(1 for s, p in units if s.choices[:1] == [p]),
                "Top 3": sum(1 for s, p in units if p in s.choices[:3]),
            }
        else:
            counts = {"Picked + type match": sum(
                1 for s, p in units if p in s.choices and set(s.types) & scorer.by_id[p].types)}
        anyc = sum(1 for s, p in units if p in s.choices)
        counts.update({"Picked it": anyc, "Not picked": n - anyc})
        stats.append({"Grade": grade.capitalize(), "Placements": n,
                      **{k: f"{v} ({v / n:.0%})" for k, v in counts.items()}})

    tables = {
        "Details": details,
        "Group sizes": summary,
        "Stats": stats,
        "Not running": not_run or [{"Project": "(all projects run)"}],
        "Excluded": [{"Name": n, "Reason": r} for n, _, r in excluded]
        or [{"Name": "(none)"}],
        "Notes": [{"Note": x} for x in notes + problems] or [{"Note": "none"}],
    }
    path = out / cfg["inputs"].get("output_file", "Project_Pomfret_Rosters.xlsx")
    write_workbook(path, overview, student_rows, rosters, tables, cfg)
    return path, {"Stats": stats, "Projects": summary, "Master": details}


HEAD = PatternFill("solid", fgColor="DDE5F0")
BAND = PatternFill("solid", fgColor="F3F6FA")
BOLD = Font(bold=True)
TITLE = Font(bold=True, size=14)


def _header(ws, values):
    ws.append(values)
    for c in ws[ws.max_row]:
        c.font, c.fill = BOLD, HEAD


def _widths(ws, widths):
    for k, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(k)].width = w


def _landscape(ws):
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True


def _sheet_name(name, used):
    clean = "".join(ch for ch in name if ch not in '[]:*?/\\')[:31].strip()
    base, n = clean, 2
    while clean.lower() in used:
        clean = f"{base[:28]} {n}"
        n += 1
    used.add(clean.lower())
    return clean


def write_workbook(path, overview, student_rows, rosters, tables, cfg):
    wb = Workbook()
    ws = wb.active
    ws.title = "Projects"
    _header(ws, ["#", "Project", "Location", "Faculty 1", "Faculty 2", "Faculty 3",
                       "Students"])
    for row in overview:
        ws.append(row)
    _widths(ws, [5, 38, 18, 18, 18, 18, 12])
    ws.freeze_panes = "A2"
    _landscape(ws)

    ws = wb.create_sheet("Students")
    labels = {g: v.get("label", g.capitalize() + "s") for g, v in cfg["grades"].items()}
    current = None
    for grade, row in student_rows:
        if grade != current:
            if current is not None:
                ws.append([])
            ws.append([labels[grade].upper()])
            ws.cell(ws.max_row, 1).font = TITLE
            _header(ws, ["Name", "Project #1", "Project Faculty", "Project #2",
                               "Project Faculty", "Why"])
            current = grade
        ws.append(row)
        ws.cell(ws.max_row, 6).font = Font(size=9, color="555555")
    _widths(ws, [26, 32, 26, 32, 26, 90])
    _landscape(ws)

    used = {"projects", "students"} | {t.lower() for t in tables}
    for p, blocks in rosters:
        ws = wb.create_sheet(_sheet_name(p.name, used))
        ws.append([TRACK_PREFIX[p.track] + p.name])
        ws.cell(1, 1).font = TITLE
        for g, sts in blocks:
            ws.append([])
            if g.week:
                ws.append([f"GROUP {g.week} (week {g.week})"])
                ws.cell(ws.max_row, 1).font = BOLD
            _header(ws, ["Student", "Grade", "Faculty", "Location",
                               "Celebration of Learning", "Comments / friends"])
            for k, st in enumerate(sts):
                ws.append([st.name, st.grade.capitalize(),
                           ", ".join(p.faculty) if k == 0 else "",
                           p.location if k == 0 else "", st.celebration, st.comments])
            total = f"TOTAL - {len(sts)} Students"
            ws.append([f"GROUP {g.week} {total}" if g.week else total])
            ws.cell(ws.max_row, 1).font = BOLD
        _widths(ws, [28, 12, 30, 16, 28, 50])
        _landscape(ws)

    for title, rows in tables.items():
        ws = wb.create_sheet(title)
        rows = rows or [{"": "(empty)"}]
        cols = list(rows[0].keys())
        _header(ws, cols)
        for r in rows:
            ws.append([r.get(c, "") for c in cols])
        for k, c in enumerate(cols, 1):
            width = max(len(str(c)), *(len(str(r.get(c, ""))) for r in rows))
            ws.column_dimensions[get_column_letter(k)].width = min(width + 2, 90)
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        ws.sheet_properties.tabColor = "999999"
    wb.save(path)
