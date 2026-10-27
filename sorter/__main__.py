"""Usage:
    python -m sorter dummy [--out dummy_data]     # make fake input files
    python -m sorter run [--config config.toml]   # sort and write output/
"""
import argparse
import sys

from . import dummy, loader, optimize, report


def main(argv=None):
    ap = argparse.ArgumentParser(prog="sorter")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("dummy", help="generate fake input data")
    d.add_argument("--out", default="dummy_data")
    d.add_argument("--seed", type=int, default=7)
    r = sub.add_parser("run", help="select projects and sort students")
    r.add_argument("--config", default="config.toml")
    args = ap.parse_args(argv)

    if args.cmd == "dummy":
        print(f"Wrote fake inputs to {dummy.generate(args.out, args.seed)}/")
        return 0

    cfg = loader.load_config(args.config)
    projects = loader.load_projects(cfg)
    students, excluded, problems = loader.load_students(cfg, projects)
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
        print(f"  {row['Track']:5} {row['Project']:28} {row['Students']:>3} students "
              f"(M {row['M']}, F {row['F']}){flag}")
    for n in notes + problems:
        print(f"  note: {n}")
    print(f"\nWrote {out}/master.xlsx (+ master.csv, rosters.csv, projects.csv)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
