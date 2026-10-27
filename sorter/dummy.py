"""Generate fake input files in the same format as the real Google Form exports.

Names are "Student 001" style and emails end in @example.org, so nothing here
can be mistaken for real student data.
"""
import csv
import random
from pathlib import Path

PROJECTS = [
    # name, track, types, sdgs, must_run
    ("Community Garden", "Major", "hands;heart", "2;15", "yes"),
    ("River Restoration", "Major", "hands;feet", "6;14;15", "yes"),
    ("Habitat Build", "Major", "hands", "1;11", "yes"),
    ("Food Pantry Partnership", "Major", "heart;hands", "1;2", ""),
    ("Elementary Reading Buddies", "Major", "heart;head", "4", ""),
    ("Solar Audit", "Major", "head", "7;13", ""),
    ("Trail Maintenance", "Major", "feet;hands", "15;3", ""),
    ("Senior Center Visits", "Major", "heart", "3;10", ""),
    ("Water Quality Lab", "Major", "head;feet", "6;14", ""),
    ("Refugee Welcome Kits", "Major", "heart;hands", "10;16", ""),
    ("Local History Podcast", "Major", "head", "4;11", ""),
    ("Bike Repair Shop", "Major", "hands", "11;12", ""),
    ("Youth Soccer Coaching", "Major", "feet;heart", "3;4", ""),
    ("Composting Program", "Major", "hands;head", "12;13", ""),
    ("Climate Policy Brief", "Major", "head", "13;16", ""),
    ("Animal Shelter Support", "Major", "heart;hands", "15", ""),
    ("Farm-to-Table Kitchen", "Major", "hands;heart", "2;12", ""),
    ("Coding for Nonprofits", "Major", "head", "9;17", ""),
    ("Mural Project", "Major", "hands;heart", "11", ""),
    ("Invasive Species Survey", "Major", "feet;head", "15", ""),
    ("Tutoring Center", "Minor", "head;heart", "4", "yes"),
    ("Recycling Audit", "Minor", "head;hands", "12", ""),
    ("Blood Drive", "Minor", "heart", "3", ""),
    ("Pollinator Garden", "Minor", "hands", "15", ""),
    ("Fundraising 5K", "Minor", "feet", "3;17", ""),
    ("Letter Writing", "Minor", "heart", "10;16", ""),
    ("Campus Energy Watch", "Minor", "head", "7", ""),
    ("Clothing Drive", "Minor", "hands;heart", "1;12", ""),
    ("Bird Count", "Minor", "feet;head", "15", ""),
    ("Story Time Recording", "Minor", "heart;head", "4", ""),
]

GRADES = [("sophomores", "10", 80), ("juniors", "11", 80), ("seniors", "12", 80)]
CHOICE_COLS = ["1st choice", "2nd choice", "3rd choice", "4th choice", "5th choice"]


def generate(out_dir, seed=7):
    rng = random.Random(seed)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    with open(out / "projects.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Project ID", "Project", "Major/Minor", "Type tags", "SDG tags", "Must run"])
        for k, (name, track, types, sdgs, must) in enumerate(PROJECTS, 1):
            w.writerow([f"P{k:02d}", name, track, types.replace(";", ", "),
                        sdgs.replace(";", ", "), must])

    majors = [p for p in PROJECTS if p[1] == "Major"]
    minors = [p for p in PROJECTS if p[1] == "Minor"]
    # Some projects are clearly more popular than others, like in real life.
    pop = {p[0]: rng.uniform(0.2, 3.0) for p in PROJECTS}
    pop["Habitat Build"], pop["Community Garden"], pop["Mural Project"] = 4.0, 3.5, 3.2
    pop["Climate Policy Brief"], pop["Letter Writing"] = 0.15, 0.2

    def pick(pool, k):
        pool = list(pool)
        chosen = []
        for _ in range(min(k, len(pool))):
            tot = sum(pop[p[0]] for p in pool)
            r, acc = rng.uniform(0, tot), 0
            for p in pool:
                acc += pop[p[0]]
                if acc >= r:
                    chosen.append(p)
                    pool.remove(p)
                    break
        return chosen

    everyone, n = [], 0
    for label, grade, count in GRADES:
        rows = []
        for _ in range(count):
            n += 1
            sid = f"student{n:03d}@example.org"
            track = "Minor" if rng.random() < 0.22 else "Major"
            pool = majors if track == "Major" else minors
            k = 1 if rng.random() < 0.08 else rng.choice([3, 4, 5, 5])
            picks = pick(pool, k)
            types = set()
            for p in picks[:2]:
                types |= set(p[2].split(";"))
            if rng.random() < 0.3:
                types.add(rng.choice(["hands", "feet", "head", "heart"]))
            sdgs = set()
            for p in picks[:2]:
                sdgs |= set(p[3].split(";"))
            sdgs = sorted(rng.sample(sorted(sdgs), min(len(sdgs), 2)) +
                          [str(rng.randint(1, 17))], key=int)
            comment = ""
            if rng.random() < 0.15:
                comment = f"Would like to be with Student {rng.randint(1, 240):03d}"
            row = {
                "Timestamp": "10/15/2026 9:00:00",
                "Email Address": sid,
                "Name": f"Student {n:03d}",
                "Grade": grade,
                "Gender": rng.choice(["M", "F"]),
                "Major or Minor": track,
                "Hands / Feet / Head / Heart": ", ".join(sorted(types)),
                "SDG goals": ", ".join(sdgs),
                "Comments (friends, anything else)": comment,
            }
            for col, p in zip(CHOICE_COLS, picks + [None] * 5):
                row[col] = p[0] if p else ""
            rows.append(row)
            everyone.append((sid, grade, pool))
        with open(out / f"responses_{label}.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

    # Last year's list: juniors and seniors did a project last year.
    with open(out / "last_year.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Email Address", "Project", "Role"])
        for sid, grade, pool in everyone:
            if grade in ("11", "12"):
                role = "Leader" if rng.random() < 0.05 else "Student"
                w.writerow([sid, rng.choice(pool)[0], role])

    # Leaders and trip students are taken out before sorting.
    with open(out / "exclusions.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Email Address", "Reason"])
        seniors = [e for e in everyone if e[1] == "12"]
        for sid, _, _ in rng.sample(seniors, 22):
            w.writerow([sid, "Project leader"])
        for sid, _, _ in rng.sample([e for e in everyone if e[1] != "12"], 10):
            w.writerow([sid, "Trip"])
    return out
