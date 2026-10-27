"""Usage:
    python -m sorter dummy [--out dummy_data]     # make fake input files
    python -m sorter run [--config config.toml]   # sort using the files named in the config
    python -m sorter run --data data              # sort whatever CSVs are in data/
    add --anonymize to replace names with codes (key saved next to the output)
"""
import argparse
import csv
import re
import sys
from pathlib import Path

from . import dummy, loader, optimize, report


def main(argv=None):
    ap = argparse.ArgumentParser(prog="sorter")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("dummy", help="generate fake input data")
    d.add_argument("--out", default="dummy_data")
    d.add_argument("--seed", type=int, default=7)
    r = sub.add_parser("run", help="select projects and sort students")
    r.add_argument("--config", default="config.toml")
    r.add_argument("--data", help="folder with the CSV files; found by file name")
    r.add_argument("--anonymize", action="store_true",
                   help="replace student names with codes and leave out comments")
    args = ap.parse_args(argv)

    if args.cmd == "dummy":
        print(f"Wrote fake inputs to {dummy.generate(args.out, args.seed)}/")
        return 0

    cfg = loader.load_config(args.config)
    if args.data:
        try:
            use_folder(cfg, Path(args.data))
        except SystemExit as e:
            print(e)
            return 1
    projects = loader.load_projects(cfg)
    students, excluded, problems = loader.load_students(cfg, projects)
    if args.anonymize:
        anonymize(cfg, students, excluded)
    asg, dem, notes, scorer = optimize.run(cfg, projects, students)
    out, sheets = report.build(cfg, asg, dem, notes, scorer, projects, students,
                               excluded, problems)

    print(f"{len(students)} students sorted, {len(excluded)} excluded, "
          f"{len(asg.running)} projects running.\n")
    for row in sheets["Stats"]:
        print("  " + "  ".join(f"{k}: {v}" for k, v in row.items()))
    print()
    for row in sheets["Projects"]:
        flag = f"  <- {row['Flags']}" if row["Flags"] else ""
        print(f"  {row['Project']:32} {row['Week']:7} {row['Students']:>3} students "
              f"(M {row['M']}, F {row['F']}){flag}")
    for n in notes + problems:
        print(f"  note: {n}")
    print(f"\nWrote {out}")
    return 0


def use_folder(cfg, folder):
    """Point the config at the CSVs in a folder, recognized by file name:
    a grade word (senior/junior/sophomore) -> that grade's responses; otherwise
    'roster', 'last', 'exclu'/'leader'/'trip', 'project'."""
    if not folder.is_dir():
        raise SystemExit(f"Folder {folder} not found.")
    files = sorted(folder.glob("*.csv"))
    inputs = cfg["inputs"]
    inputs.update({"responses": [], "roster": "", "last_year": "", "exclusions": ""})
    projects = None
    for f in files:
        low = f.stem.lower()
        # Grade words first; numbers (10/11/12) only if there is no grade word,
        # so a date like 2026-10-12 in the name can't decide the grade.
        words = re.findall(r"[a-z]+", low) + re.findall(r"\d+", low)
        grade = next((g for w in words if (g := loader.grade_of(cfg, w))), None)
        if grade:
            inputs["responses"].append({"file": str(f.resolve()), "grade": grade})
        elif "roster" in low or "gender" in low:
            inputs["roster"] = str(f.resolve())
        elif "last" in low:
            inputs["last_year"] = str(f.resolve())
        elif "exclu" in low or "leader" in low or "trip" in low:
            inputs["exclusions"] = str(f.resolve())
        elif "project" in low:
            projects = str(f.resolve())
        else:
            print(f"  ignored {f.name} (name doesn't say what it is)")
    if not inputs["responses"]:
        raise SystemExit(f"No response sheets in {folder}/. Their file names need "
                         "'seniors', 'juniors' or 'sophomores'.")
    if not projects:
        raise SystemExit(f"No project list in {folder}/ (a CSV with 'project' in its name).")
    inputs["projects"] = projects
    for r in inputs["responses"]:
        print(f"  {r['grade']:9} <- {Path(r['file']).name}")
    for key in ("projects", "roster", "last_year", "exclusions"):
        print(f"  {key:9} <- {Path(inputs[key]).name if inputs[key] else '(none)'}")


def anonymize(cfg, students, excluded):
    """Names become codes in the output; the key goes to a separate file next
    to it, so real names can be put back later."""
    out = Path(cfg["_base"]) / cfg["inputs"]["output_dir"]
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "name_key.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Code", "Name", "Email"])
        for k, s in enumerate(sorted(students, key=lambda s: s.name.lower()), 1):
            code = f"Student {k:03d}"
            w.writerow([code, s.name, s.id])
            s.name, s.comments = code, ""
        for k, (name, sid, reason) in enumerate(list(excluded), 1):
            w.writerow([f"Excluded {k:03d}", name, sid])
            excluded[k - 1] = (f"Excluded {k:03d}", "", reason)


if __name__ == "__main__":
    sys.exit(main())
